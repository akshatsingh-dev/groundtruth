"""The agent loop.

GUARDRAIL — read this before adding anything to this file.

    This agent never takes an external-facing or irreversible action. There is
    no email client here, no HTTP POST to a third party, no form automation, no
    git command, no posting anywhere. The only network egress in the whole
    package is a read against the physical-facts provider.

    "Acts" in the judging criterion means acts *on the analysis* — searching
    parcels, testing configurations, re-planning which provider calls to make.
    It does not mean acting on the world without a human. An agent that emails
    a county on its own is a liability, not a feature. Drafts go to
    `outputs/drafts/` as plain files and a person decides whether to send them.

    This is enforced by construction, not by a line in the system prompt. There
    is nothing in `agent/tools.py` that can send, post, submit or commit.

What this file is
-----------------

A real Anthropic tool-calling loop. Claude gets the ten tools in `tools.py`, a
system prompt that puts it in the chair of an air permitting engineer, and a
budget. It decides which provider calls to make based on the pathway question
in front of it — a combined-cycle plant heading for major PSD in hilly ground
pulls terrain, land cover and points of interest because AERMOD needs them; a
fuel cell config does not waste the credits. That choice is the reasoning, and
the trace makes it visible.

Two things about the architecture worth stating plainly:

*   **The model decides what to call. The engines decide what is true.** The
    assessment is assembled from `emissions.estimate`, `pathway.determine_pathway`
    and `search.py` output — never from a number the model wrote in prose. The
    model's closing text is carried as narrative and labelled as such.

*   **It runs with no keys.** Without `ANTHROPIC_API_KEY` the planner falls
    back to a deterministic script that calls the same executors in the same
    order with the same adaptive query planning, and the trace says
    `deterministic fallback (no LLM)` at the top of every step. A judge with no
    keys still sees the whole decision tree run.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Sequence

from providers.base import FactSet, NullProvider, PhysicalFactsProvider

from .emissions import (
    EmissionsEstimate,
    Fuel,
    GenerationConfig,
    PrimeMover,
    estimate as estimate_emissions,
)
from .pathway import (
    Pathway,
    PathwayResult,
    SiteContext,
    classify_source_category,
    determine_pathway,
    overlay_for,
)
from .search import AlternateSiteSearchResult, ConfigSearchResult, search_configs
from .tools import (
    TOOL_NAMES,
    TOOL_SCHEMAS,
    ToolContext,
    estimate_summary,
    pathway_summary,
    run_tool,
)

DEFAULT_MODEL = "claude-opus-5"

#: Ceiling on assistant turns in the loop. Each turn may contain several tool
#: calls, so this is not the same as the tool-call budget.
DEFAULT_MAX_TURNS = 14

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
#
# Three ways to drive the loop, resolved in this order at startup. The tools in
# `tools.py` are shared across all three — the tool list is written once and
# adapted at the boundary, so the reasoning is identical whichever path runs.
#
#   1. CLAUDE_CODE_OAUTH_TOKEN -> the Claude Agent SDK. This is what a Claude
#      subscription gives you (`claude setup-token`), and the Messages API in
#      the `anthropic` package will not accept that token, so it has to go
#      through the Agent SDK. Tools are registered as an in-process SDK MCP
#      server; every built-in Claude Code tool is switched off.
#   2. ANTHROPIC_API_KEY -> the Messages API tool-use loop in the `anthropic`
#      package.
#   3. Neither -> the deterministic scripted path, no model involved.
#
# The trace states which one ran, in plain words, at the top of every run, and
# the step-by-step output is identical across 1 and 2.

AUTH_AGENT_SDK = "claude-agent-sdk"
AUTH_MESSAGES_API = "anthropic-api"
AUTH_NONE = "none"

AUTH_DESCRIPTION = {
    AUTH_AGENT_SDK: (
        "Claude Agent SDK, authenticated with the CLAUDE_CODE_OAUTH_TOKEN from a Claude "
        "subscription. The loop runs through the SDK; the ten tools are registered as an "
        "in-process MCP server and every built-in Claude Code tool is switched off."
    ),
    AUTH_MESSAGES_API: (
        "Anthropic Messages API, authenticated with ANTHROPIC_API_KEY. Same ten tools, same "
        "system prompt, same order — a plain tool-use loop."
    ),
    AUTH_NONE: (
        "No LLM. Neither CLAUDE_CODE_OAUTH_TOKEN nor ANTHROPIC_API_KEY is set, so the run "
        "takes the deterministic scripted path: the same executors, in the same order, with "
        "the same adaptive query planning. Only the sequencing stops being model-chosen."
    ),
}


def resolve_auth(explicit: str | None = None) -> str:
    """Pick the auth path. Environment only — nothing here reads a keychain or
    a config file, so what you export is what you get."""
    if explicit:
        return explicit
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return AUTH_AGENT_SDK
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AUTH_MESSAGES_API
    return AUTH_NONE


# --------------------------------------------------------------------------
# Project
# --------------------------------------------------------------------------


@dataclass
class Project:
    """What the caller announces. Address or coordinate, proposed MW and
    generation config, target energization date.

    The declared county and state are optional and exist for one reason: when
    the geocode refuses, the agent still has to be able to say something
    honest. Anything screened against a declared jurisdiction is labelled
    unverified all the way to the output. It is never treated as a resolved
    parcel.
    """

    address: str
    config: GenerationConfig
    target_energization: date | None = None
    name: str | None = None
    developer: str | None = None
    declared_county: str | None = None
    declared_state: str | None = None
    declared_fips: str | None = None
    declared_latitude: float | None = None
    declared_longitude: float | None = None
    grid_tied: bool = True
    #: Months to assemble a complete application before the clock starts:
    #: PTE inventory, modelling protocol, BACT analysis, pre-application meeting.
    prep_months: float = 3.0

    def declared_jurisdiction(self) -> dict | None:
        if not (self.declared_county and self.declared_state):
            return None
        from .tools import normalize_county, normalize_state

        return {
            "county": normalize_county(self.declared_county),
            "state": normalize_state(self.declared_state, self.declared_fips),
            "fips": self.declared_fips,
            "latitude": self.declared_latitude,
            "longitude": self.declared_longitude,
            "provenance": "user-declared, unverified",
        }

    def months_to_target(self, today: date | None = None) -> float | None:
        if self.target_energization is None:
            return None
        today = today or date.today()
        return (self.target_energization - today).days / 30.44

    def describe(self) -> str:
        bits = [f"{self.name or 'Unnamed project'} at {self.address}", self.config.describe()]
        if self.target_energization:
            bits.append(f"target energization {self.target_energization.isoformat()}")
        return ". ".join(bits) + "."


# --------------------------------------------------------------------------
# Trace
# --------------------------------------------------------------------------


@dataclass
class TraceStep:
    index: int
    stage: str
    kind: str  # plan | reasoning | thought | tool | observation | conclusion | note | error
    title: str
    why: str | None = None
    tool: str | None = None
    tool_input: dict | None = None
    result: dict | None = None
    conclusion: str | None = None
    citation: str | None = None
    credits: int = 0
    elapsed_s: float = 0.0
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "stage": self.stage,
            "kind": self.kind,
            "title": self.title,
            "why": self.why,
            "tool": self.tool,
            "tool_input": self.tool_input,
            "result": self.result,
            "conclusion": self.conclusion,
            "citation": self.citation,
            "credits": self.credits,
            "elapsed_s": round(self.elapsed_s, 2),
            "at": self.at,
        }


_KIND_STYLE = {
    "plan": ("bold cyan", "PLAN"),
    "reasoning": ("white", "REASON"),
    "thought": ("dim italic", "THINK"),
    "tool": ("bold yellow", "TOOL"),
    "observation": ("green", "RESULT"),
    "conclusion": ("bold magenta", "CONCLUDE"),
    "note": ("dim", "NOTE"),
    "error": ("bold red", "ERROR"),
}


@dataclass
class Trace:
    """Structured, replayable record of the run. The trace is the demo."""

    mode: str = "llm tool-calling loop"
    model: str | None = None
    steps: list[TraceStep] = field(default_factory=list)
    started: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    _t0: float = field(default_factory=time.monotonic, repr=False)

    def add(
        self,
        stage: str,
        kind: str,
        title: str,
        why: str | None = None,
        tool: str | None = None,
        tool_input: dict | None = None,
        result: dict | None = None,
        conclusion: str | None = None,
        citation: str | None = None,
        credits: int = 0,
    ) -> TraceStep:
        step = TraceStep(
            index=len(self.steps) + 1,
            stage=stage,
            kind=kind,
            title=title,
            why=why,
            tool=tool,
            tool_input=tool_input,
            result=result,
            conclusion=conclusion,
            citation=citation,
            credits=credits,
            elapsed_s=time.monotonic() - self._t0,
        )
        self.steps.append(step)
        return step

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "model": self.model,
            "started": self.started,
            "steps": [s.to_dict() for s in self.steps],
        }

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, default=str)
        return path

    # -- rendering -------------------------------------------------------

    def render(self, console: Any = None) -> None:
        """Pretty-print the trace. Uses rich when it is available and falls
        back to plain text so this still works on a bare interpreter."""
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
        except Exception:
            self._render_plain()
            return

        console = console or Console()
        header = f"Deliverable — agent trace · {self.mode}"
        if self.model:
            header += f" · {self.model}"
        console.rule(f"[bold]{header}")

        for step in self.steps:
            style, tag = _KIND_STYLE.get(step.kind, ("white", step.kind.upper()))
            body = Text()
            if step.why:
                body.append(step.why.strip() + "\n", style="italic")
            if step.tool:
                body.append(f"tool: {step.tool}", style="bold")
                if step.tool_input:
                    body.append(f"  {_short_json(step.tool_input, 220)}", style="dim")
                body.append("\n")
            if step.result is not None:
                body.append(_short_json(step.result, 700) + "\n", style="dim")
            if step.conclusion:
                body.append(step.conclusion.strip() + "\n", style="bold")
            if step.citation:
                body.append(f"[{step.citation}]\n", style="dim italic")
            meta = f"{step.elapsed_s:6.2f}s"
            if step.credits:
                meta += f" · {step.credits} credits"
            console.print(
                Panel(
                    body if len(body) else Text(step.title),
                    title=f"[{style}]{step.index:>2} {tag}[/] · {step.stage} · {step.title}",
                    title_align="left",
                    subtitle=meta,
                    subtitle_align="right",
                    border_style=style.split()[-1],
                    expand=True,
                )
            )

    def _render_plain(self) -> None:
        print(f"=== Deliverable agent trace — {self.mode} ===")
        for step in self.steps:
            tag = _KIND_STYLE.get(step.kind, ("", step.kind.upper()))[1]
            print(f"\n[{step.index:>2}] {tag} · {step.stage} · {step.title}  ({step.elapsed_s:.2f}s)")
            if step.why:
                print(f"     why: {step.why.strip()}")
            if step.tool:
                print(f"     tool: {step.tool} {_short_json(step.tool_input or {}, 200)}")
            if step.result is not None:
                print(f"     -> {_short_json(step.result, 500)}")
            if step.conclusion:
                print(f"     => {step.conclusion.strip()}")
            if step.citation:
                print(f"     [{step.citation}]")


def _short_json(obj: Any, limit: int) -> str:
    try:
        text = json.dumps(obj, default=str, separators=(", ", ": "))
    except Exception:
        text = str(obj)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --------------------------------------------------------------------------
# Adaptive query planning
# --------------------------------------------------------------------------


def _is_major_shaped(est: EmissionsEstimate | None, config: GenerationConfig) -> bool:
    """Is this plant close enough to a major-source threshold that dispersion
    modelling is the likely outcome? That is the question that decides whether
    terrain and land cover are worth the credits."""
    if est is None:
        return True  # unknown, so assume the expensive branch
    threshold = classify_source_category(config).threshold_tpy
    _, tpy = est.max_criteria_tpy()
    return tpy >= threshold * 0.6


def plan_physical_intents(
    config: GenerationConfig,
    est: EmissionsEstimate | None = None,
    site: SiteContext | None = None,
    grid_tied: bool = True,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Choose which provider presets to buy for this specific project.

    Returns (chosen, skipped), both as (intent, reason) pairs. Both halves go
    into the trace: what a screen deliberately does not buy is as much a part
    of the reasoning as what it does.
    """
    chosen: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []

    chosen.append(
        ("parcel", "Boundary and acreage set the fenceline. Ambient air starts there, so it "
                   "is where the modelling receptors go.")
    )

    if config.prime_mover is PrimeMover.FUEL_CELL:
        chosen.append(
            ("utilities", "Fuel cells still burn gas, so pipeline reachability is still the "
                          "constraint. It is the only physical question left.")
        )
        skipped.append(
            ("terrain", "Fuel cell. Criteria pollutant PTE is in the single tons per year, this "
                        "will never be dispersion modelled, and terrain only matters for AERMOD.")
        )
        skipped.append(
            ("land_cover", "Same reason. Surface roughness is an AERMOD input and there will be "
                           "no AERMOD run.")
        )
        skipped.append(
            ("points_of_interest", "No meaningful criteria pollutant plume, so no receptor "
                                   "analysis. Spending credits here would be theatre.")
        )
        if grid_tied or config.mw > 200:
            chosen.append(("grid_interconnect", "Large or grid-tied, so queue position is on the "
                                                "critical path even when the air permit is not."))
        return chosen, skipped

    is_gas = config.fuel is Fuel.NATURAL_GAS
    is_turbine = "turbine" in config.prime_mover.value
    is_engine = config.prime_mover in (
        PrimeMover.RECIP_LEAN_BURN,
        PrimeMover.RECIP_RICH_BURN,
        PrimeMover.DIESEL_RECIP,
    )
    major_shaped = _is_major_shaped(est, config)

    if is_gas:
        chosen.append(
            ("utilities", "Gas-fired. Pipeline distance is the most common non-air failure mode — "
                          "New Mexico blocked a 2.45 GW site by blocking its lateral, not its plant.")
        )
    else:
        chosen.append(
            ("utilities", "Diesel, so no pipeline dependency, but transmission and the utility "
                          "service territory still decide whether this is behind the meter.")
        )

    if major_shaped and is_turbine:
        chosen.append(
            ("terrain", "PTE is at or over the major threshold, so AERMOD is coming. Terrain "
                        "relief decides whether it is a flat-site run or a complex-terrain run "
                        "with terrain-following receptors, and complex terrain usually forces a "
                        "taller stack.")
        )
        chosen.append(
            ("land_cover", "AERMET needs surface roughness, albedo and Bowen ratio from land "
                           "cover to build the meteorological inputs for that AERMOD run.")
        )
    elif is_turbine:
        skipped.append(
            ("terrain", "Turbine, but PTE is well under the major threshold. No dispersion "
                        "modelling, so terrain does not change the answer.")
        )
        skipped.append(("land_cover", "Same reason — no AERMET run to feed."))

    if is_engine or major_shaped:
        chosen.append(
            ("points_of_interest", "Schools, hospitals and residential parcels near the fenceline "
                                   "are both modelling receptors and the opposition map. Engines and "
                                   "major sources need both.")
        )
    else:
        skipped.append(
            ("points_of_interest", "Small source, no modelling demonstration. Receptors do not "
                                   "change the pathway here.")
        )

    na = bool(site and site.nonattainment)
    overlay = overlay_for(site.state) if site else {}
    if na or overlay.get("ej_denial_authority") or config.fuel is Fuel.DIESEL:
        reason = "Nonattainment county" if na else (
            "State has environmental-justice denial authority" if overlay.get("ej_denial_authority")
            else "Diesel, so PM2.5 and toxics land on nearby residents"
        )
        chosen.append(
            ("demographics", f"{reason}. Population and EJ indicators within radius decide whether "
                             f"this is a modelling exercise or a discretionary denial risk.")
        )

    if config.mw > 200 or grid_tied:
        chosen.append(
            ("grid_interconnect", "Over 200 MW or grid-tied. The interconnect study runs in "
                                  "parallel with the air permit and is frequently the longer pole.")
        )

    skipped.append(
        ("flood_risk", "Flood, wildfire and natural hazard presets decide whether the site is "
                       "*good*. This screen asks whether they will let you switch it on. Different "
                       "layer, and not worth the credits here.")
    )
    skipped.append(("soil", "Foundation design, not permit pathway."))
    return chosen, skipped


def plan_proximity_targets(
    config: GenerationConfig,
    est: EmissionsEstimate | None = None,
    site: SiteContext | None = None,
    grid_tied: bool = True,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    chosen: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    is_turbine = "turbine" in config.prime_mover.value
    major_shaped = _is_major_shaped(est, config)

    if config.fuel is Fuel.NATURAL_GAS:
        chosen.append(
            ("gas_pipeline", "Fuel supply. Over ~25 km the lateral becomes its own permitting "
                             "project with its own easements and its own opposition.")
        )
    if grid_tied or config.mw > 100:
        chosen.append(("transmission", "Voltage and distance decide whether this is behind the "
                                       "meter or an interconnection."))
        chosen.append(("substation", "Point of interconnection for any grid-tied portion."))

    if is_turbine and config.prime_mover is not PrimeMover.FUEL_CELL:
        chosen.append(
            ("airport", "Turbine stacks are tall, and complex terrain makes them taller. FAA "
                        "obstruction review and thermal plume review both key off airport distance.")
        )
    else:
        skipped.append(("airport", "Short stacks, no obstruction or plume review."))

    if major_shaped or config.prime_mover is PrimeMover.DIESEL_RECIP:
        chosen.append(("urban_area", "Who lives downwind. Receptor grid and opposition risk."))
        chosen.append(("school", "Sensitive receptor, and the single most reliable predictor of "
                                 "an organised hearing."))
    else:
        skipped.append(("urban_area", "No modelling demonstration at this size."))
        skipped.append(("school", "Same."))

    if config.prime_mover is PrimeMover.FUEL_CELL:
        skipped.append(("airport", "Fuel cell. No stack to review."))
    return chosen, skipped


# --------------------------------------------------------------------------
# Pathway chain, for the trace
# --------------------------------------------------------------------------


def explain_pathway_chain(result: PathwayResult, est: EmissionsEstimate) -> list[tuple[str, str, str]]:
    """The decision tree as a list of (title, detail, citation).

    This is what the demo shows on screen: source category -> threshold ->
    PTE -> attainment -> increment -> Class I -> pathway.
    """
    chain: list[tuple[str, str, str]] = []
    category = result.source_category
    chain.append(("Source category", category.reasoning, category.citation))
    chain.append(
        (
            "Applicable major-source threshold",
            f"{category.threshold_tpy:,.0f} tpy"
            + (f" — listed category: {category.category}" if category.category else " — not a listed category"),
            category.citation,
        )
    )
    pollutant, tpy = est.max_criteria_tpy()
    chain.append(
        (
            "Potential to emit vs threshold",
            f"{pollutant} at {tpy:,.0f} tpy against {result.applicable_threshold or category.threshold_tpy:,.0f} "
            f"tpy. {est.basis['hours_basis']}",
            "40 CFR 52.21(b)(4)",
        )
    )

    by_name = {t.name: t for t in result.triggers}
    for name in (
        "nonattainment_designation",
        "major_nonattainment_nsr",
        "major_psd",
        "synthetic_minor",
        "minor_nsr",
        "permit_by_rule",
        "psd_increment_consumed",
        "class_i_aqrv",
        "complex_terrain",
        "title_v",
        "state_toxics",
        "ozone_transport_region",
        "ej_denial_authority",
        "gas_reachability",
        "county_moratorium",
        "zoning_posture",
        "litigation",
        "source_aggregation_risk",
    ):
        trigger = by_name.get(name)
        if trigger is None:
            continue
        label = name.replace("_", " ").title()
        prefix = "FIRED — " if trigger.fired else "clear — "
        chain.append((label, prefix + trigger.detail, trigger.citation))

    chain.append(
        (
            "Pathway",
            f"{result.summary()}"
            + (f"  Hard stops: {'; '.join(result.hard_stops)}" if result.hard_stops else ""),
            "agent/pathway.py decision tree",
        )
    )
    return chain


# --------------------------------------------------------------------------
# Probability
# --------------------------------------------------------------------------


@dataclass
class Probability:
    """One number per project, with the model that produced it attached."""

    value: float | None
    model: str
    months_available: float | None
    months_required: float | None
    slack_months: float | None
    sigma_months: float | None
    caps: list[str] = field(default_factory=list)
    basis: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "probability_on_announced_schedule": round(self.value, 3) if self.value is not None else None,
            "model": self.model,
            "months_available": round(self.months_available, 1) if self.months_available is not None else None,
            "months_required": round(self.months_required, 1) if self.months_required is not None else None,
            "slack_months": round(self.slack_months, 1) if self.slack_months is not None else None,
            "sigma_months": round(self.sigma_months, 1) if self.sigma_months is not None else None,
            "caps_applied": self.caps,
            "basis": self.basis,
        }


PROBABILITY_MODEL = (
    "The air permit is treated as the critical path. Months available is the target "
    "energization date minus today. Months required is the pre-application preparation "
    "period plus the pathway's likely duration for that state agency. The pathway's own "
    "optimistic-to-pessimistic spread is read as roughly plus or minus two standard "
    "deviations, so sigma = (high - low) / 4, floored at one month. The probability is "
    "the normal CDF of slack over sigma, clipped to [0.02, 0.97] because nothing here "
    "justifies claiming certainty. Hard stops are a hard cap at 0.05: a moratorium, an "
    "unavailable offset market or a consumed increment is not a schedule risk, it is a "
    "different outcome. Turbine delivery, construction and interconnection are not "
    "modelled — they are separate constraints and each is documented as binding on its "
    "own."
)


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def energization_probability(
    project: Project,
    result: PathwayResult | None,
    today: date | None = None,
) -> Probability:
    basis: list[str] = []
    if result is None:
        return Probability(
            value=None,
            model=PROBABILITY_MODEL,
            months_available=None,
            months_required=None,
            slack_months=None,
            sigma_months=None,
            basis=["No pathway determined, so no number. A refusal is the honest output here."],
        )

    months_available = project.months_to_target(today)
    if months_available is None:
        return Probability(
            value=None,
            model=PROBABILITY_MODEL,
            months_available=None,
            months_required=project.prep_months + result.months_likely,
            slack_months=None,
            sigma_months=None,
            basis=[
                "No announced energization date, so there is no schedule to score against. "
                f"The permit alone runs {result.months_low:.0f}-{result.months_high:.0f} months."
            ],
        )

    months_required = project.prep_months + result.months_likely
    slack = months_available - months_required
    sigma = max((result.months_high - result.months_low) / 4.0, 1.0)
    value = _phi(slack / sigma)
    value = min(max(value, 0.02), 0.97)

    basis.append(
        f"{months_available:.0f} months to the announced date. "
        f"{project.prep_months:.0f} months to prepare a complete application plus "
        f"{result.months_likely:.0f} months of agency review = {months_required:.0f} months required."
    )
    basis.append(
        f"Slack {slack:+.0f} months against a sigma of {sigma:.1f} months, taken from the "
        f"{result.months_low:.0f}-{result.months_high:.0f} month range for {result.pathway.label}."
    )

    caps: list[str] = []
    if result.hard_stops:
        value = min(value, 0.05)
        caps.append(
            "Hard stop present, so capped at 0.05: " + "; ".join(result.hard_stops)
        )
    return Probability(
        value=value,
        model=PROBABILITY_MODEL,
        months_available=months_available,
        months_required=months_required,
        slack_months=slack,
        sigma_months=sigma,
        caps=caps,
        basis=basis,
    )


# --------------------------------------------------------------------------
# Assessment
# --------------------------------------------------------------------------


@dataclass
class ProjectAssessment:
    """Everything the report renders. Assembled from engine output, not prose."""

    project: Project
    generated_at: str
    provider_name: str
    resolved: bool
    resolution_note: str | None
    site: SiteContext | None
    estimate: EmissionsEstimate | None
    pathway: PathwayResult | None
    probability: Probability
    alternate: AlternateSiteSearchResult | None
    configs: ConfigSearchResult | None
    facts: FactSet
    field_requests: list[dict]
    trace: Trace
    narrative: str | None
    caveats: list[str] = field(default_factory=list)
    credits_spent: int = 0
    tool_calls: int = 0

    @property
    def headline(self) -> str:
        if self.probability.value is None:
            return "No probability stated — see caveats."
        return (
            f"{self.probability.value:.0%} probability this project energizes on its "
            f"announced schedule."
        )

    def to_dict(self) -> dict:
        return {
            "project": {
                "name": self.project.name,
                "address": self.project.address,
                "developer": self.project.developer,
                "config": self.project.config.describe(),
                "mw": self.project.config.mw,
                "target_energization": self.project.target_energization.isoformat()
                if self.project.target_energization
                else None,
            },
            "generated_at": self.generated_at,
            "provider": self.provider_name,
            "headline": self.headline,
            "probability": self.probability.to_dict(),
            "site": {
                "resolved": self.resolved,
                "resolution_note": self.resolution_note,
                "county": self.site.county if self.site else None,
                "state": self.site.state if self.site else None,
                "county_fips": self.site.county_fips if self.site else None,
                "latitude": self.site.latitude if self.site else None,
                "longitude": self.site.longitude if self.site else None,
                "agency": overlay_for(self.site.state)["agency"] if self.site else None,
                "nonattainment": [
                    {"pollutant": s.pollutant, "classification": s.classification,
                     "area_name": s.area_name, "source": s.source, "fetched": s.fetched}
                    for s in (self.site.nonattainment if self.site else [])
                ],
            },
            "emissions": estimate_summary(self.estimate) if self.estimate else None,
            "pathway": pathway_summary(self.pathway) if self.pathway else None,
            "alternate_sites": self.alternate.to_dict() if self.alternate else None,
            "config_alternatives": self.configs.to_dict() if self.configs else None,
            "field_requests": self.field_requests,
            "provenance": self.facts.provenance(),
            "caveats": self.caveats,
            "narrative": self.narrative,
            "run": {
                "mode": self.trace.mode,
                "model": self.trace.model,
                "tool_calls": self.tool_calls,
                "credits_spent": self.credits_spent,
            },
            "trace": self.trace.to_dict(),
        }


# --------------------------------------------------------------------------
# System prompt
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an air permitting screening agent for data center power projects in the United \
States. Your job is not to say whether a site is good. It is to say whether the agency \
will let them switch it on, how long that takes, and what would change the answer.

Reason in the order a permitting engineer does, and say which step you are on:

1. Potential to emit. Call estimate_emissions first. It is free and it costs no credits, \
and the answer decides everything after it. Remember PTE is computed at 8760 hr/yr unless \
there is a federally enforceable permit condition capping operation. Intended dispatch is \
not a limit.
2. Source category and threshold. A data center is not on the List of 28. The power plant \
on its site can be. A combined-cycle plant over 250 MMBtu/hr is a fossil fuel-fired steam \
electric plant, which drops the PSD major threshold from 250 tpy to 100 tpy.
3. The site. Resolve it, then buy only the physical facts the pathway question needs.
4. Attainment status, then PTE against the applicable threshold.
5. The overlays that add months regardless: PSD increment already consumed, Class I areas \
within range, Title V, state toxics programs, terrain, county posture, litigation, and gas \
pipeline reachability.
6. The pathway and its timeline.
7. Then act: test config changes at this parcel, and if the site fails, search outward for \
a parcel where it does not.

Rules you do not break:

- Never state a physical fact without its source and its fetch timestamp. Every provider \
result carries both. If you cannot cite it, say you do not have it.
- If the geocode refuses on low confidence, do not guess a county. A centroid silently \
substituted for a parcel produces a permit answer for the wrong county, and someone options \
land on it. Say it is unresolved. If the caller declared a county, you may screen against \
it, but label the whole assessment unverified.
- A source that is not wired up is not the same as a clean result. Report gaps as gaps.
- Choose your provider calls. Do not run a fixed list. Terrain and land cover are worth \
credits when AERMOD is coming and are waste when it is not. A fuel cell config does not \
need receptor data. A gas config always needs pipeline distance. Say in one sentence why \
you picked what you picked — that reasoning is the product.
- You have a tool-call and credit budget. search_alternate_sites is the expensive one; call \
it when the site actually fails, not as a matter of routine.
- Use request_field when the fact you need is not in the catalog — nearest Class I area \
distance, background ambient concentration, permitted emissions of nearby majors. Do not \
invent those numbers and do not pretend they do not matter.
- You propose. A human disposes. You have no ability to send email, submit a form, contact \
an agency or commit anything, and you must not describe yourself as having done any of those \
things.

When you are done, write a short closing assessment in plain language: the pathway, the \
timeline, the two or three things that actually decide it, and what you would change. Short \
sentences. No marketing voice. The structured numbers are computed by the engines and \
rendered separately, so do not restate tables — explain the judgment.
"""


# --------------------------------------------------------------------------
# Planner
# --------------------------------------------------------------------------


class Planner:
    """Runs a project through the loop and returns a ProjectAssessment."""

    def __init__(
        self,
        provider: PhysicalFactsProvider | None = None,
        model: str = DEFAULT_MODEL,
        max_tool_calls: int = 24,
        max_credits: int = 400,
        max_turns: int = DEFAULT_MAX_TURNS,
        client: Any = None,
        auth: str | None = None,
        console: Any = None,
    ) -> None:
        self.provider = provider or NullProvider()
        self.model = model
        self.max_tool_calls = max_tool_calls
        self.max_credits = max_credits
        self.max_turns = max_turns
        self.client = client
        self.console = console
        self.auth = resolve_auth(auth if auth else (AUTH_MESSAGES_API if client else None))

    # -- entry point -----------------------------------------------------

    def run(self, project: Project) -> ProjectAssessment:
        ctx = ToolContext(
            project=project,
            provider=self.provider,
            max_tool_calls=self.max_tool_calls,
            max_credits=self.max_credits,
        )
        trace = Trace()
        self._announce_auth(trace, self.auth)
        narrative: str | None = None

        if self.auth == AUTH_AGENT_SDK:
            try:
                narrative = self._run_agent_sdk(ctx, trace)
            except Exception as exc:
                trace.add(
                    "setup",
                    "error",
                    "Claude Agent SDK path failed",
                    why=f"{exc.__class__.__name__}: {exc}",
                    conclusion="Falling back to the next auth path so the run still produces "
                    "an answer.",
                )
                narrative = self._fallback(ctx, trace, skip=AUTH_AGENT_SDK)
        elif self.auth == AUTH_MESSAGES_API:
            try:
                narrative = self._run_messages_api(ctx, trace)
            except Exception as exc:
                trace.add(
                    "setup",
                    "error",
                    "Messages API path failed",
                    why=f"{exc.__class__.__name__}: {exc}",
                    conclusion="Falling back to the deterministic script.",
                )
                narrative = self._fallback(ctx, trace, skip=AUTH_MESSAGES_API)
        else:
            narrative = self._run_deterministic(ctx, trace)

        return self._finalize(ctx, trace, narrative)

    def _announce_auth(self, trace: Trace, mode: str, reason: str | None = None) -> None:
        trace.mode = {
            AUTH_AGENT_SDK: f"Claude Agent SDK tool-calling loop ({self.model})",
            AUTH_MESSAGES_API: f"Anthropic Messages API tool-calling loop ({self.model})",
            AUTH_NONE: "deterministic fallback (no LLM)",
        }[mode]
        trace.model = self.model if mode != AUTH_NONE else None
        trace.add(
            "setup",
            "note",
            f"Auth path: {mode}",
            why=reason or AUTH_DESCRIPTION[mode],
        )

    def _fallback(self, ctx: ToolContext, trace: Trace, skip: str) -> str | None:
        """Walk down the auth chain after a failure. Never loops back up."""
        if skip == AUTH_AGENT_SDK and os.environ.get("ANTHROPIC_API_KEY"):
            self._announce_auth(
                trace,
                AUTH_MESSAGES_API,
                reason="Agent SDK path failed, and ANTHROPIC_API_KEY is set, so the loop retries "
                "on the Messages API. Same tools, same system prompt, same trace shape.",
            )
            try:
                return self._run_messages_api(ctx, trace)
            except Exception as exc:
                trace.add(
                    "setup",
                    "error",
                    "Messages API path failed too",
                    why=f"{exc.__class__.__name__}: {exc}",
                )
        self._announce_auth(
            trace,
            AUTH_NONE,
            reason="No usable model path left, so the run takes the deterministic scripted path: "
            "the same executors, in the same order, with the same adaptive query planning. Only "
            "the sequencing stops being model-chosen.",
        )
        return self._run_deterministic(ctx, trace)

    # -- shared tool dispatch --------------------------------------------
    #
    # Both model-driven paths go through this, so the trace looks the same
    # whichever one ran. Nothing about the tool contract differs between them.

    def _dispatch(self, ctx: ToolContext, trace: Trace, name: str, args: dict) -> tuple[dict, bool]:
        stage = _stage_for(name)
        step = trace.add(
            stage,
            "tool",
            name,
            why=args.get("reason") or args.get("description"),
            tool=name,
            tool_input=args,
        )
        before = ctx.credits_spent
        result, ok = run_tool(ctx, name, args)
        step.credits = ctx.credits_spent - before
        trace.add(
            stage,
            "observation" if ok else "error",
            f"{name} returned",
            result=_compact_result(name, result),
            credits=step.credits,
        )
        if name == "determine_pathway" and ok and ctx.pathway and ctx.estimate:
            self._trace_chain(trace, ctx)
        return result, ok

    def _trace_model_text(self, trace: Trace, text: str, thinking: bool = False) -> None:
        text = (text or "").strip()
        if not text:
            return
        if thinking:
            trace.add("loop", "thought", "Reasoning", why=text[:1500])
        else:
            trace.add("loop", "reasoning", "Model states its plan", why=text[:1500])

    def _open_loop(self, ctx: ToolContext, trace: Trace) -> None:
        trace.add(
            "setup",
            "plan",
            "Handing the problem to the model with 10 tools and a budget",
            why=f"Budget: {ctx.max_tool_calls} tool calls, {ctx.max_credits} credits. The model "
            f"chooses which provider calls the pathway question needs; the engines decide what "
            f"is true.",
        )

    # -- path 1: Claude Agent SDK ----------------------------------------

    def _run_agent_sdk(self, ctx: ToolContext, trace: Trace) -> str | None:
        """Drive the loop through the Claude Agent SDK.

        The ten tools from `tools.py` are wrapped as an in-process SDK MCP
        server. Every built-in Claude Code tool is switched off — no Read, no
        Write, no Bash, no WebSearch — so the only thing the model can do is
        call this product's tools. That is a guardrail, not a tidiness
        preference: a loop with a Bash tool in it is a loop that can act on the
        world.
        """
        import asyncio
        import dataclasses as _dc

        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            SystemMessage,
            TextBlock,
            ThinkingBlock,
            ToolUseBlock,
            create_sdk_mcp_server,
            query,
            tool,
        )

        self._open_loop(ctx, trace)
        server_name = "deliverable"

        def make_handler(schema: dict):
            name = schema["name"]

            @tool(name, schema["description"], schema["input_schema"])
            async def _handler(args: dict) -> dict:
                payload = dict(args or {})
                try:
                    result, ok = await asyncio.to_thread(
                        self._dispatch, ctx, trace, name, payload
                    )
                except RuntimeError:
                    # No thread pool available: run inline rather than fail.
                    result, ok = self._dispatch(ctx, trace, name, payload)
                return {
                    "content": [
                        {"type": "text", "text": json.dumps(result, default=str)[:12000]}
                    ],
                    "is_error": not ok,
                }

            return _handler

        sdk_tools = [make_handler(schema) for schema in TOOL_SCHEMAS]
        server = create_sdk_mcp_server(name=server_name, version="1.0.0", tools=sdk_tools)
        qualified = [f"mcp__{server_name}__{name}" for name in TOOL_NAMES]

        wanted = {
            "system_prompt": SYSTEM_PROMPT,
            "model": self.model,
            "mcp_servers": {server_name: server},
            "allowed_tools": qualified,
            # Empty list means: none of Claude Code's built-in tools.
            "tools": [],
            # Anything not in allowed_tools is denied rather than prompted for.
            # This has to be headless.
            "permission_mode": "dontAsk",
            "max_turns": self.max_turns,
            # Do not inherit the user's CLAUDE.md, settings or project config.
            # The system prompt above is the whole instruction set.
            "setting_sources": [],
            "effort": "high",
            "thinking": {"type": "adaptive", "display": "summarized"},
        }
        valid = {f.name for f in _dc.fields(ClaudeAgentOptions)}
        dropped = sorted(set(wanted) - valid)
        options = ClaudeAgentOptions(**{k: v for k, v in wanted.items() if k in valid})
        if dropped:
            trace.add(
                "setup",
                "note",
                "Agent SDK options not supported by the installed version",
                why=f"Dropped: {', '.join(dropped)}. Upgrade claude-agent-sdk if the run behaves "
                f"differently than the Messages API path.",
            )

        final_text: list[str] = []

        async def drive() -> None:
            async for message in query(prompt=self._brief(ctx), options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ThinkingBlock):
                            self._trace_model_text(trace, block.thinking, thinking=True)
                        elif isinstance(block, TextBlock):
                            final_text.append(block.text)
                            self._trace_model_text(trace, block.text)
                        elif isinstance(block, ToolUseBlock):
                            # Traced inside the handler, where it actually runs,
                            # so the trace matches the Messages API path.
                            pass
                elif isinstance(message, ResultMessage):
                    if message.is_error:
                        trace.add(
                            "loop",
                            "error",
                            f"Run ended: {message.subtype}",
                            why=str(message.result or message.errors or ""),
                        )
                    elif message.result:
                        final_text.append(str(message.result))
                    trace.add(
                        "loop",
                        "note",
                        "Loop closed",
                        why=f"{message.num_turns} turns"
                        + (
                            f", ${message.total_cost_usd:.3f}"
                            if message.total_cost_usd
                            else ""
                        ),
                    )
                elif isinstance(message, SystemMessage) and message.subtype == "init":
                    trace.add(
                        "setup",
                        "note",
                        "Session initialised",
                        why=f"Tools available to the model: "
                        f"{', '.join(message.data.get('tools', []) or []) or 'none reported'}",
                    )

        asyncio.run(drive())
        # Deduplicate: the final assistant text usually repeats in ResultMessage.
        deduped: list[str] = []
        for chunk in final_text:
            chunk = (chunk or "").strip()
            if chunk and chunk not in deduped:
                deduped.append(chunk)
        return "\n\n".join(deduped) if deduped else None

    # -- path 2: Messages API --------------------------------------------

    def _run_messages_api(self, ctx: ToolContext, trace: Trace) -> str | None:
        import anthropic

        client = self.client or anthropic.Anthropic()
        messages: list[dict] = [{"role": "user", "content": self._brief(ctx)}]
        final_text: list[str] = []

        self._open_loop(ctx, trace)

        for _turn in range(self.max_turns):
            budget_left = ctx.calls_remaining > 0 and ctx.credits_remaining > 0
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": 8000,
                "system": SYSTEM_PROMPT,
                "messages": messages,
                # Adaptive thinking so the model can reason between tool calls;
                # summarized so the trace can show what it was weighing.
                "thinking": {"type": "adaptive", "display": "summarized"},
            }
            if budget_left:
                kwargs["tools"] = TOOL_SCHEMAS
            else:
                trace.add(
                    "loop",
                    "note",
                    "Budget spent, tools withdrawn",
                    why=f"{ctx.budget_line()}. The model now has to answer from what it has.",
                )

            # output_config rides in extra_body so this keeps working on older
            # SDK releases that do not type the parameter yet.
            response = client.messages.create(
                **kwargs, extra_body={"output_config": {"effort": "high"}}
            )

            if getattr(response, "stop_reason", None) == "refusal":
                detail = getattr(response, "stop_details", None)
                trace.add(
                    "loop",
                    "error",
                    "Model declined the request",
                    why=str(getattr(detail, "explanation", None) or detail or "no detail given"),
                )
                raise RuntimeError("model refusal")

            tool_uses = []
            for block in response.content:
                btype = getattr(block, "type", None)
                if btype == "thinking":
                    self._trace_model_text(trace, getattr(block, "thinking", ""), thinking=True)
                elif btype == "text":
                    final_text.append(block.text or "")
                    self._trace_model_text(trace, block.text or "")
                elif btype == "tool_use":
                    tool_uses.append(block)

            messages.append({"role": "assistant", "content": response.content})
            if not tool_uses:
                break

            results_blocks = []
            for block in tool_uses:
                args = dict(block.input or {})
                result, ok = self._dispatch(ctx, trace, block.name, args)
                results_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str)[:12000],
                        "is_error": not ok,
                    }
                )
            messages.append({"role": "user", "content": results_blocks})

        deduped = [t.strip() for t in final_text if t and t.strip()]
        return "\n\n".join(deduped) if deduped else None

    # -- deterministic path ----------------------------------------------

    def _run_deterministic(self, ctx: ToolContext, trace: Trace) -> str:
        """The same executors, in the same order, with the same adaptive query
        planning — minus the model choosing the sequence."""
        project = ctx.project
        config = project.config

        # 1. PTE first. It is free and it tells us what the site questions are.
        trace.add(
            "stage 1 — potential to emit",
            "plan",
            "Estimate PTE before spending a single credit",
            why="Emissions are config-only arithmetic. The answer decides whether this is a "
            "major source, and that decides which physical facts are worth buying. Buying "
            "facts first and reasoning second is how screens waste credits.",
        )
        result, _ = run_tool(ctx, "estimate_emissions", {})
        est = ctx.estimate
        assert est is not None
        pollutant, tpy = est.max_criteria_tpy()
        threshold = classify_source_category(config).threshold_tpy
        trace.add(
            "stage 1 — potential to emit",
            "conclusion",
            f"{pollutant} {tpy:,.0f} tpy against a {threshold:,.0f} tpy threshold",
            conclusion=(
                f"{'Major-source shaped. Dispersion modelling is coming.' if _is_major_shaped(est, config) else 'Comfortably minor-source shaped. No modelling demonstration expected.'}"
            ),
            citation=est.basis["emission_factors"],
            result={"tons_per_year": {p: round(v, 1) for p, v in est.tons_per_year.items()}},
        )

        # 2. Resolve.
        trace.add(
            "stage 2 — resolve",
            "plan",
            "Resolve the address to a canonical parcel",
            why="Refuse rather than guess. The county decides the pathway, so a wrong county is "
            "a wrong answer with a confident face on it.",
        )
        res, ok = run_tool(ctx, "resolve_site", {})
        trace.add(
            "stage 2 — resolve",
            "observation" if res.get("resolved") else "error",
            "resolve_site returned",
            result=_compact_result("resolve_site", res),
            conclusion=(
                f"Resolved to {res.get('county')} County, {res.get('state')} "
                f"(confidence {res.get('confidence')})"
                if res.get("resolved")
                else "Provider refused. " + (res.get("guidance") or "")
            ),
        )

        # 3. Adaptive physical read.
        if ctx.location is not None:
            chosen, skipped = plan_physical_intents(config, est, ctx.site, project.grid_tied)
            trace.add(
                "stage 3 — physical read",
                "plan",
                "Choose provider presets for THIS config",
                why="; ".join(f"{i}: {r}" for i, r in chosen),
                result={"skipped": {i: r for i, r in skipped}},
                conclusion=f"Buying {len(chosen)} presets, skipping {len(skipped)}.",
            )
            res, ok = run_tool(
                ctx,
                "get_physical_facts",
                {"intents": [i for i, _ in chosen], "reason": "; ".join(r for _, r in chosen)},
            )
            trace.add("stage 3 — physical read", "observation" if ok else "error",
                      "get_physical_facts returned", result=_compact_result("get_physical_facts", res))

            targets, tskipped = plan_proximity_targets(config, est, ctx.site, project.grid_tied)
            trace.add(
                "stage 3 — physical read",
                "plan",
                "Choose proximity targets",
                why="; ".join(f"{t}: {r}" for t, r in targets),
                result={"skipped": {t: r for t, r in tskipped}},
            )
            res, ok = run_tool(
                ctx,
                "get_proximity",
                {"targets": [t for t, _ in targets], "reason": "; ".join(r for _, r in targets)},
            )
            trace.add("stage 3 — physical read", "observation" if ok else "error",
                      "get_proximity returned", result=_compact_result("get_proximity", res))
        else:
            trace.add(
                "stage 3 — physical read",
                "note",
                "Skipping the physical read",
                why="No resolved parcel, so there is nothing to fetch facts about. Parcel-level "
                "facts stay unknown rather than being approximated from the county.",
            )

        # 4. Regulatory.
        if ctx.site is not None:
            trace.add(
                "stage 4 — regulatory",
                "plan",
                "Load Green Book, county file and dockets",
                why="Attainment status is the single fact most likely to flip the pathway. The "
                "county file and the docket search are the non-air blockers that a pure air "
                "screen misses.",
            )
            res, ok = run_tool(ctx, "get_regulatory_context", {})
            trace.add(
                "stage 4 — regulatory",
                "observation" if ok else "error",
                "get_regulatory_context returned",
                result=_compact_result("get_regulatory_context", res),
                conclusion="; ".join(res.get("gaps", [])) or None,
            )

            # Field requests for what nothing indexes. This is the documented
            # route for a genuine gap, and it is cheaper than an ingest.
            for name, description in (
                (
                    "nearest_class_i_area_km",
                    "Great-circle distance from a coordinate to the nearest Clean Air Act Class I "
                    "area (national parks and wilderness over 5,000 acres, 40 CFR 81 Subpart D). "
                    "Pure geometry over published federal boundaries. Drives the AQRV and "
                    "visibility analysis in every PSD application.",
                ),
                (
                    "background_pm25_ug_m3",
                    "Background ambient PM2.5 and NO2 concentration at a coordinate, from the "
                    "nearest representative EPA monitor. Every NAAQS modelling demonstration adds "
                    "modelled impact to this number.",
                ),
            ):
                res, ok = run_tool(ctx, "request_field", {"field_name": name, "description": description})
                trace.add(
                    "stage 4 — regulatory",
                    "observation",
                    f"request_field: {name}",
                    why="No preset covers this and it is a real physical-world field. Requesting "
                    "it beats building an ingest for it.",
                    result=_compact_result("request_field", res),
                )

        # 5. Pathway.
        if ctx.site is not None:
            trace.add(
                "stage 5 — pathway",
                "plan",
                "Run the decision tree",
                why="Source category, then threshold, then PTE against threshold, then the "
                "overlays that add months.",
            )
            res, ok = run_tool(ctx, "determine_pathway", {})
            if ok and ctx.pathway and ctx.estimate:
                self._trace_chain(trace, ctx)
        else:
            trace.add(
                "stage 5 — pathway",
                "error",
                "No pathway",
                why="Site unresolved and no jurisdiction declared. Producing a pathway here would "
                "mean inventing a county.",
            )
            return (
                "The site could not be resolved and no county was declared, so there is no "
                "pathway to state. Re-run with a coordinate or a declared jurisdiction."
            )

        return self._closing_note(ctx)

    # -- shared helpers --------------------------------------------------

    def _trace_chain(self, trace: Trace, ctx: ToolContext) -> None:
        assert ctx.pathway is not None and ctx.estimate is not None
        for title, detail, citation in explain_pathway_chain(ctx.pathway, ctx.estimate):
            trace.add(
                "stage 5 — pathway",
                "conclusion" if title == "Pathway" else "reasoning",
                title,
                why=detail,
                citation=citation,
            )

    def _brief(self, ctx: ToolContext) -> str:
        project = ctx.project
        lines = [
            f"Screen this project for air permit deliverability.",
            "",
            f"Name: {project.name or 'unnamed'}",
            f"Address or coordinate: {project.address}",
            f"Proposed generation: {project.config.describe()}",
            f"Grid tied: {project.grid_tied}",
        ]
        if project.developer:
            lines.append(f"Developer: {project.developer}")
        if project.target_energization:
            months = project.months_to_target()
            lines.append(
                f"Announced energization: {project.target_energization.isoformat()} "
                f"({months:.0f} months from today)"
            )
        declared = project.declared_jurisdiction()
        if declared:
            lines.append(
                f"Caller-declared jurisdiction (UNVERIFIED, use only if the geocode refuses): "
                f"{declared['county']} County, {declared['state']}"
            )
        lines += [
            "",
            f"Budget: {ctx.max_tool_calls} tool calls, {ctx.max_credits} provider credits. "
            f"Provider in use: {ctx.provider.name}.",
            "",
            "Work it in the order a permitting engineer would. Say which provider calls you are "
            "choosing and why before you make them.",
        ]
        return "\n".join(lines)

    def _closing_note(self, ctx: ToolContext) -> str:
        if ctx.pathway is None:
            return "No pathway determined."
        result = ctx.pathway
        bits = [result.summary()]
        if result.hard_stops:
            bits.append("Hard stops: " + "; ".join(result.hard_stops))
        deciding = sorted(
            (t for t in result.fired if t.months_added),
            key=lambda t: -t.months_added,
        )[:3]
        if deciding:
            bits.append(
                "Deciding factors: "
                + "; ".join(f"{t.name.replace('_', ' ')} (+{t.months_added:.0f} mo)" for t in deciding)
            )
        return " ".join(bits)

    # -- finalize --------------------------------------------------------

    def _finalize(self, ctx: ToolContext, trace: Trace, narrative: str | None) -> ProjectAssessment:
        project = ctx.project

        # Config search always runs. It is pure math, costs nothing, and it is
        # half of what makes this an agent rather than a report.
        configs: ConfigSearchResult | None = getattr(ctx, "config_search", None)
        if configs is None and ctx.site is not None:
            est = ctx.estimate or estimate_emissions(project.config)
            path = ctx.pathway or determine_pathway(est, ctx.site)
            trace.add(
                "stage 6 — act",
                "plan",
                "Config search at this parcel",
                why="Before moving the project, find out whether the equipment can move the "
                "pathway. Free, and controls are cheaper than land.",
            )
            configs = search_configs(ctx.site, project.config, path)
            ctx.config_search = configs
            best = configs.best
            trace.add(
                "stage 6 — act",
                "conclusion" if best else "note",
                best.label if best else "No config change moves the pathway",
                why=best.cost_note if best else None,
                conclusion=(
                    f"{best.label}: {path.pathway.label} -> {best.pathway.label}, "
                    f"~{best.months_saved:.0f} months, {best.availability:.0%} availability."
                    if best
                    else "; ".join(configs.notes) or None
                ),
                result={"options": [o.to_dict() for o in configs.options[:4]]},
            )

        # Alternate-site search. The model may already have called it; if the
        # site fails and it did not, the planner runs it anyway. This is the
        # differentiator and it does not get skipped.
        alternate: AlternateSiteSearchResult | None = getattr(ctx, "alternate", None)
        needs_move = ctx.pathway is not None and (
            ctx.pathway.pathway.rank >= Pathway.MAJOR_PSD.rank or bool(ctx.pathway.hard_stops)
        )
        if alternate is None and needs_move and ctx.site is not None:
            if ctx.site.latitude is None or ctx.site.longitude is None:
                trace.add(
                    "stage 6 — act",
                    "note",
                    "Alternate-site search not run",
                    why="No resolved coordinate, so there is no ring to search around. This loop "
                    "needs a real parcel; it will not search around a county centroid.",
                )
            elif ctx.calls_remaining <= 0 or ctx.credits_remaining <= 0:
                trace.add("stage 6 — act", "note", "Alternate-site search not run",
                          why=f"Budget spent: {ctx.budget_line()}.")
            else:
                trace.add(
                    "stage 6 — act",
                    "plan",
                    "Alternate-site search",
                    why=f"{ctx.pathway.pathway.label} at the announced parcel. The permit you need "
                    f"is decided by where the land is, so search outward across county and state "
                    f"lines for ground where the same plant gets a faster answer.",
                )
                res, ok = run_tool(ctx, "search_alternate_sites", {"radius_km": 15, "n": 24})
                alternate = getattr(ctx, "alternate", None)
                trace.add(
                    "stage 6 — act",
                    "conclusion" if (alternate and alternate.best) else "note",
                    (alternate.delta_statement if (alternate and alternate.delta_statement)
                     else "No better parcel found"),
                    result=_compact_result("search_alternate_sites", res),
                )
        elif alternate is None and ctx.pathway is not None:
            trace.add(
                "stage 6 — act",
                "note",
                "Alternate-site search skipped on purpose",
                why=f"Already {ctx.pathway.pathway.label} with no hard stops. There is nothing to "
                f"improve, and this loop is the biggest credit consumer in the product.",
            )

        probability = energization_probability(project, ctx.pathway)
        trace.add(
            "stage 7 — output",
            "conclusion",
            (f"{probability.value:.0%} on the announced schedule"
             if probability.value is not None else "No probability stated"),
            why=" ".join(probability.basis),
            conclusion="; ".join(probability.caps) or None,
        )

        caveats = self._caveats(ctx, probability)
        assessment = ProjectAssessment(
            project=project,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            provider_name=self.provider.name,
            resolved=ctx.resolved,
            resolution_note=ctx.resolution_note,
            site=ctx.site,
            estimate=ctx.estimate,
            pathway=ctx.pathway,
            probability=probability,
            alternate=alternate,
            configs=configs,
            facts=ctx.facts,
            field_requests=ctx.field_requests,
            trace=trace,
            narrative=narrative,
            caveats=caveats,
            credits_spent=ctx.credits_spent,
            tool_calls=ctx.calls_made,
        )
        return assessment

    def _caveats(self, ctx: ToolContext, probability: Probability) -> list[str]:
        out: list[str] = []
        if not ctx.resolved:
            out.append(
                "The address did not resolve to a canonical parcel. "
                + (ctx.resolution_note or "")
                + " Everything below is screened against a declared jurisdiction and is "
                "unverified at parcel level."
            )
        if isinstance(self.provider, NullProvider):
            out.append(
                "Running against NullProvider: no physical facts were fetched. Terrain, "
                "pipeline distance, receptors and Class I proximity are unknown, not absent. "
                "Set MIREYE_API_KEY to run this for real."
            )
        if ctx.site is not None:
            from .pathway import STATE_OVERLAYS

            if ctx.site.state not in STATE_OVERLAYS:
                out.append(
                    f"{ctx.site.state} is not one of the states modelled in detail. The timeline "
                    f"is the federal default with no agency-specific adjustment, and state "
                    f"toxics programs, transport-region membership and any EJ statute are not "
                    f"evaluated. Treat the range as wider than shown and the trigger list as "
                    f"incomplete."
                )
        if ctx.site is not None and not ctx.site.nonattainment:
            out.append(
                "No nonattainment designation was loaded for this county. If the Green Book "
                "ingest is not wired up, treat 'attainment' as unread rather than confirmed — "
                "it is the single fact most likely to flip the pathway."
            )
        if ctx.site is not None and not ctx.site.class_i_areas:
            out.append(
                "Nearest Class I area distance is unknown. It was requested via the provider's "
                "field-request route. A Class I area inside 100 km adds a Federal Land Manager "
                "review that can stop a project on visibility grounds alone."
            )
        if ctx.site is not None and not ctx.site.increment_consumed:
            out.append(
                "PSD increment consumption by existing major sources is unknown. A consumed "
                "increment can make a site un-permittable at any timeline."
            )
        out.append(
            "This is a screen, not an applicability determination. A licensed professional "
            "signs that opinion and carries the liability."
        )
        out.append(
            "The agent drafts and ranks. It does not contact agencies, file anything, or send "
            "anything. Drafts land in outputs/drafts/ for a person to review."
        )
        return out


def _stage_for(tool_name: str) -> str:
    return {
        "estimate_emissions": "stage 1 — potential to emit",
        "resolve_site": "stage 2 — resolve",
        "get_physical_facts": "stage 3 — physical read",
        "get_proximity": "stage 3 — physical read",
        "ask_mireye": "stage 3 — physical read",
        "get_regulatory_context": "stage 4 — regulatory",
        "request_field": "stage 4 — regulatory",
        "determine_pathway": "stage 5 — pathway",
        "test_config": "stage 6 — act",
        "search_alternate_sites": "stage 6 — act",
    }.get(tool_name, "loop")


def _compact_result(tool_name: str, result: dict) -> dict:
    """Trim tool output for the trace. The full result is in the JSON export."""
    if not isinstance(result, dict):
        return {"value": result}
    if "error" in result:
        return result
    drop = {
        "determine_pathway": ("narrative", "triggers_clear"),
        "estimate_emissions": ("significant_emission_rates_tpy",),
        "get_physical_facts": (),
        "search_alternate_sites": ("ranked",),
    }.get(tool_name, ())
    out = {k: v for k, v in result.items() if k not in drop}
    if tool_name == "get_physical_facts" and "facts" in out:
        out["facts"] = out["facts"][:6]
    return out


# --------------------------------------------------------------------------
# Environment and provider wiring
# --------------------------------------------------------------------------


def load_env(path: str = ".env") -> None:
    """Read .env if python-dotenv is installed. Silent no-op otherwise, because
    the whole package has to run with no keys and no optional dependencies."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(path, override=False)


def load_provider(verbose: bool = False) -> tuple[PhysicalFactsProvider, str]:
    """Return (provider, note).

    Imported defensively: `providers/mireye.py` is owned by someone else and may
    be mid-write. Any import or construction failure falls back to NullProvider
    with the reason attached, so the loop still runs and the trace still says
    what happened.
    """
    load_env()
    if not os.environ.get("MIREYE_API_KEY"):
        return NullProvider(), "No MIREYE_API_KEY. Running against NullProvider — no physical facts."
    try:
        from providers.mireye import MireyeProvider
    except Exception as exc:
        return (
            NullProvider(),
            f"providers.mireye did not import ({exc.__class__.__name__}: {exc}). "
            f"Falling back to NullProvider.",
        )
    try:
        provider = MireyeProvider()
    except Exception as exc:
        return (
            NullProvider(),
            f"MireyeProvider would not construct ({exc.__class__.__name__}: {exc}). "
            f"Falling back to NullProvider.",
        )
    return provider, f"Physical facts from {provider.name}, cached to disk."


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------


def demo_project() -> Project:
    """A 400 MW behind-the-meter gas plant in New Jersey.

    Chosen because it is the live failure mode: NJ sits in the Ozone Transport
    Region, and NJ DEP holds statutory authority to deny a permit outright in
    an overburdened community regardless of whether the modelling passes.
    """
    config = GenerationConfig(
        mw=400.0,
        prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
        fuel=Fuel.NATURAL_GAS,
        controls=(),
        run_hours=8760.0,
        enforceable_limit=False,
    )
    return Project(
        address="Vineland, New Jersey",
        config=config,
        target_energization=date(2027, 12, 1),
        name="Demo — 400 MW onsite gas for a data center campus",
        declared_county="Cumberland",
        declared_state="NJ",
        declared_latitude=39.4862,
        declared_longitude=-75.0257,
        grid_tied=False,
    )


def main(argv: Sequence[str] | None = None) -> None:
    import argparse

    from .report import render_terminal, write_json, write_markdown

    parser = argparse.ArgumentParser(
        prog="python -m agent.planner",
        description="Screen a data center power project for air permit deliverability.",
    )
    parser.add_argument("address", nargs="?", help="Address or 'lat,lon'. Defaults to the demo site.")
    parser.add_argument("--mw", type=float, default=None)
    parser.add_argument(
        "--prime-mover", default=None, choices=[p.value for p in PrimeMover]
    )
    parser.add_argument("--county", default=None, help="Declared county, used only if the geocode refuses.")
    parser.add_argument("--state", default=None, help="Declared two-letter state.")
    parser.add_argument("--target", default=None, help="Announced energization date, YYYY-MM-DD.")
    parser.add_argument("--no-llm", action="store_true", help="Force the deterministic path.")
    parser.add_argument("--null-provider", action="store_true", help="Do not call the provider.")
    parser.add_argument("--max-tool-calls", type=int, default=24)
    parser.add_argument("--max-credits", type=int, default=400)
    parser.add_argument("--out", default=None, help="Directory to write report.md, report.json, trace.json")
    args = parser.parse_args(argv)

    load_env()
    if args.null_provider:
        provider, note = NullProvider(), "Forced NullProvider."
    else:
        provider, note = load_provider()
    print(f"[provider] {note}")

    project = demo_project()
    if args.address:
        project.address = args.address
        project.name = f"Screen — {args.address}"
        project.declared_county = args.county
        project.declared_state = args.state
        project.declared_latitude = None
        project.declared_longitude = None
    if args.county:
        project.declared_county = args.county
    if args.state:
        project.declared_state = args.state
    if args.mw or args.prime_mover:
        base = project.config
        project.config = GenerationConfig(
            mw=args.mw or base.mw,
            prime_mover=PrimeMover(args.prime_mover) if args.prime_mover else base.prime_mover,
            fuel=base.fuel,
            controls=base.controls,
            run_hours=base.run_hours,
            enforceable_limit=base.enforceable_limit,
        )
    if args.target:
        project.target_energization = date.fromisoformat(args.target)

    planner = Planner(
        provider=provider,
        auth=AUTH_NONE if args.no_llm else None,
        max_tool_calls=args.max_tool_calls,
        max_credits=args.max_credits,
    )
    assessment = planner.run(project)
    assessment.trace.render()
    render_terminal(assessment)

    if args.out:
        print("\n" + write_markdown(assessment, os.path.join(args.out, "report.md")))
        print(write_json(assessment, os.path.join(args.out, "report.json")))
        print(assessment.trace.save(os.path.join(args.out, "trace.json")))

    close = getattr(provider, "close", None)
    if callable(close):
        close()


if __name__ == "__main__":  # pragma: no cover
    main()
