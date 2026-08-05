"""Tool definitions the planner hands to Claude, plus the executors behind them.

Two halves:

1.  `TOOL_SCHEMAS` — Anthropic tool-use JSON schemas. The descriptions are
    written to be *prescriptive about when to call*, not just what the tool
    does, because that is what the planner reasons over. In particular
    `get_physical_facts` spells out which presets a dispersion-modelled major
    source needs and which ones a fuel cell has no business paying for. The
    adaptive query planning the brief asks for lives partly here, in the tool
    contract, and partly in `planner.plan_physical_intents`.

2.  The executors. Each one calls the real engine or the real provider and
    returns a compact JSON-serialisable dict. Every dict that carries a
    physical value also carries `source`, `fetched` and `confidence`, because a
    permitting engineer will not act on a number they cannot trace.

Two rules this module holds:

*   **The model decides what to call. The engines decide what is true.** No
    tool asks Claude for a number and then believes it. `estimate_emissions`
    runs AP-42 math, `determine_pathway` runs the decision tree. The model's
    job is query planning and sequencing.

`get_regulatory_context` resolves the `ingest/` modules (Green Book, dockets,
counties) by duck-typing at call time and degrades to "not available" rather
than failing an import. That keeps the file runnable with any subset present.
"""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Iterable

from providers.base import (
    Fact,
    FactSet,
    Location,
    PhysicalFactsProvider,
    PRESET_INTENTS,
    PROXIMITY_TARGETS,
    ProximityResult,
    ResolutionError,
    now_iso,
)

from .emissions import (
    SIGNIFICANT_EMISSION_RATES,
    ConfigError,
    Control,
    EmissionsEstimate,
    Fuel,
    GenerationConfig,
    PrimeMover,
    estimate,
)
from .pathway import (
    NonattainmentStatus,
    Pathway,
    PathwayResult,
    SiteContext,
    determine_pathway,
    overlay_for,
    synthetic_minor_cap,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .planner import Project


# --------------------------------------------------------------------------
# Credits
# --------------------------------------------------------------------------

#: Rough credit cost of each provider operation. The real numbers come off the
#: provider's billing page; these are what the run counts against its budget so
#: a search loop cannot quietly spend a month of credits.
CREDIT_COST = {
    "geocode": 1,
    "lookup": 1,
    "preset": 1,
    "proximity_target": 1,
    "ask": 3,
    "field_request": 0,
}


class BudgetExhausted(RuntimeError):
    """The run hit its tool-call or credit ceiling."""


# --------------------------------------------------------------------------
# Call record
# --------------------------------------------------------------------------


@dataclass
class ToolCall:
    """One executed tool call, kept so the trace is replayable."""

    index: int
    name: str
    arguments: dict
    result: dict
    credits: int
    ok: bool
    started: str


# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------


@dataclass
class ToolContext:
    """Everything the executors read and write.

    The planner owns one of these per run. State accumulates here rather than
    in the conversation, so the final assessment is built from engine output
    and not from anything the model wrote in prose.
    """

    project: "Project"
    provider: PhysicalFactsProvider
    max_tool_calls: int = 24
    max_credits: int = 400

    facts: FactSet = field(default_factory=FactSet)
    location: Location | None = None
    resolved: bool = False
    resolution_note: str | None = None
    site: SiteContext | None = None
    estimate: EmissionsEstimate | None = None
    pathway: PathwayResult | None = None
    proximity: dict[str, ProximityResult] = field(default_factory=dict)
    field_requests: list[dict] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)
    credits_spent: int = 0
    intents_fetched: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: Cache of resolved alternate-site candidates, shared across search calls.
    candidate_cache: dict = field(default_factory=dict)
    #: Results of the two search loops, kept as objects rather than as the JSON
    #: the model saw, so the report renders engine output and not a round trip
    #: through the model.
    alternate: Any = None
    config_search: Any = None

    # ---- budget ----

    @property
    def calls_made(self) -> int:
        return len(self.calls)

    @property
    def calls_remaining(self) -> int:
        return max(0, self.max_tool_calls - self.calls_made)

    @property
    def credits_remaining(self) -> int:
        return max(0, self.max_credits - self.credits_spent)

    def spend(self, kind: str, units: int = 1) -> int:
        cost = CREDIT_COST.get(kind, 1) * units
        if cost > self.credits_remaining:
            raise BudgetExhausted(
                f"{kind} x{units} costs {cost} credits, {self.credits_remaining} left"
            )
        self.credits_spent += cost
        return cost

    def budget_line(self) -> str:
        return (
            f"{self.calls_made}/{self.max_tool_calls} tool calls, "
            f"{self.credits_spent}/{self.max_credits} credits"
        )

    # ---- state helpers ----

    def config(self) -> GenerationConfig:
        return self.project.config

    def require_site(self) -> SiteContext:
        if self.site is None:
            raise ToolError(
                "No site context yet. Call resolve_site first, and if the geocode "
                "refuses, say so rather than assuming a county."
            )
        return self.site

    def provenance(self) -> dict[str, dict]:
        return self.facts.provenance()


class ToolError(RuntimeError):
    """A tool could not run. Returned to the model as an error result rather
    than raised, so it can adapt instead of the loop dying."""


# --------------------------------------------------------------------------
# Tool schemas
# --------------------------------------------------------------------------

_INTENT_VOCAB = "; ".join(f"{k} = {v}" for k, v in PRESET_INTENTS.items())
_TARGET_VOCAB = "; ".join(f"{k} = {v}" for k, v in PROXIMITY_TARGETS.items())

_PRIME_MOVERS = [p.value for p in PrimeMover]
_FUELS = [f.value for f in Fuel]
_CONTROLS = [c.value for c in Control]


TOOL_SCHEMAS: list[dict] = [
    {
        "name": "resolve_site",
        "description": (
            "Resolve an address or coordinate to a canonical parcel, county, state and "
            "FIPS code through the physical-facts provider, and pull the jurisdictional "
            "lookup in the same step. Call this before any other site-dependent tool. "
            "If the provider refuses on low confidence the result comes back with "
            "resolved=false and a refusal reason: do NOT invent a county. A centroid "
            "silently substituted for a parcel produces a permit answer for the wrong "
            "county, which is worse than no answer. When the caller has declared a "
            "county and state up front, the refusal result carries them, flagged as "
            "user-declared and unverified — you may screen against them but you must "
            "label the whole assessment as unverified in your conclusion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Street address or 'lat,lon'. Defaults to the project address.",
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Geocode confidence floor, 0-1. Default 0.8. Lower it only "
                    "with a stated reason.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_physical_facts",
        "description": (
            "Fetch named physical-fact presets for the resolved site. Each preset costs "
            "credits, so request the ones the pathway question actually turns on and skip "
            "the rest — the selection is part of the analysis, not a formality.\n"
            "Guidance:\n"
            "- terrain and land_cover: only worth it when the project is heading for a "
            "major-source dispersion modelling exercise. AERMOD needs terrain relief for "
            "complex-terrain receptors and land cover for surface roughness. A "
            "combined-cycle or simple-cycle turbine whose PTE is over the major threshold "
            "needs both. Get the emissions estimate first so you know.\n"
            "- points_of_interest and demographics: receptors and environmental-justice "
            "review. Pull these for engines, for diesel, for nonattainment counties, and "
            "for states with an EJ denial statute.\n"
            "- utilities: any gas-fired config. Pipeline reachability is the most common "
            "non-air failure mode; New Mexico blocked a 2.45 GW site by blocking its "
            "pipeline, not its plant.\n"
            "- grid_interconnect: only when the project is grid-tied or over ~200 MW.\n"
            "- A fuel-cell config emits trivial criteria pollutants, will not be dispersion "
            "modelled, and should not spend credits on terrain, land_cover or "
            "points_of_interest. Fetch parcel and utilities and stop.\n"
            f"Available intents: {_INTENT_VOCAB}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intents": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(PRESET_INTENTS)},
                    "description": "Preset intents to fetch. Ask only for what the pathway needs.",
                },
                "reason": {
                    "type": "string",
                    "description": "One sentence on why these presets and not the others. "
                    "This goes into the trace.",
                },
            },
            "required": ["intents", "reason"],
        },
    },
    {
        "name": "get_proximity",
        "description": (
            "Nearest-by-road (or great circle, flagged) distance from the site to named "
            "target classes. Same rule as get_physical_facts: pick by what the pathway "
            "question needs. gas_pipeline for any gas-fired config. airport for turbines, "
            "because stack height interacts with airspace review and complex terrain "
            "usually forces a taller stack. school, hospital and urban_area when receptors "
            "or opposition drive the answer. transmission and substation whenever the "
            "project may be grid-tied.\n"
            f"Available targets: {_TARGET_VOCAB}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "targets": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(PROXIMITY_TARGETS)},
                },
                "reason": {"type": "string", "description": "Why these targets."},
            },
            "required": ["targets", "reason"],
        },
    },
    {
        "name": "get_regulatory_context",
        "description": (
            "Load the non-physical layer for a county: EPA Green Book attainment status "
            "per pollutant, the hand-entered county moratorium and zoning file, and "
            "federal court dockets touching this county or developer. Call it once the "
            "site is resolved. Nonattainment status is the single fact most likely to "
            "flip the pathway, so a run without it is not an answer. If a source is not "
            "wired up yet the result says so explicitly — report that as a gap rather "
            "than treating the county as attainment by default."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fips": {
                    "type": "string",
                    "description": "Five-digit county FIPS. Defaults to the resolved site's.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "estimate_emissions",
        "description": (
            "Potential to emit in tons per year for a generation config, from AP-42 "
            "emission factors, heat rate and hours. Pure math, no credits, no network. "
            "Call this FIRST, before spending credits on the site: PTE against the "
            "applicable threshold is what tells you whether this is a major source, and "
            "that is what decides which physical facts are worth buying. Remember PTE is "
            "computed at 8760 hours unless there is a federally enforceable cap in the "
            "permit — intent to run less is not a limit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "description": "Overrides on the project config. Omit to use the project as announced.",
                    "properties": {
                        "mw": {"type": "number"},
                        "prime_mover": {"type": "string", "enum": _PRIME_MOVERS},
                        "fuel": {"type": "string", "enum": _FUELS},
                        "controls": {"type": "array", "items": {"type": "string", "enum": _CONTROLS}},
                        "run_hours": {"type": "number"},
                        "enforceable_limit": {"type": "boolean"},
                        "heat_rate_btu_kwh": {"type": "number"},
                        "units": {"type": "integer"},
                    },
                }
            },
            "required": [],
        },
    },
    {
        "name": "determine_pathway",
        "description": (
            "Run the permit decision tree against the current emissions estimate and the "
            "current site context, in the order a permitting engineer runs it: source "
            "category and threshold, attainment status, PTE against threshold, then the "
            "overlays that add time — Class I areas, consumed PSD increment, Title V, "
            "state toxics, terrain, county posture, litigation, gas reachability. Returns "
            "the pathway, a months range for that state agency, every trigger that fired "
            "with its citation, and any hard stops. Call it after the site is loaded; "
            "call it again if you change the config."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "test_config",
        "description": (
            "Test a design change at the CURRENT parcel and report whether it moves the "
            "pathway. No credits — this is the engines only. Use it to probe a specific "
            "hypothesis you can defend: an oxidation catalyst when CO is the pollutant "
            "over the line, SCR when NOx is, combined cycle when heat rate is the lever "
            "(but check the source-category threshold, because adding a steam cycle can "
            "drop the major threshold from 250 tpy to 100 tpy and make things worse), a "
            "run-hour cap for synthetic minor (report the availability cost — a 646 hr/yr "
            "cap is a peaker, not a data center plant)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_changes": {
                    "type": "object",
                    "properties": {
                        "mw": {"type": "number"},
                        "prime_mover": {"type": "string", "enum": _PRIME_MOVERS},
                        "fuel": {"type": "string", "enum": _FUELS},
                        "controls": {"type": "array", "items": {"type": "string", "enum": _CONTROLS}},
                        "run_hours": {"type": "number"},
                        "enforceable_limit": {"type": "boolean"},
                        "heat_rate_btu_kwh": {"type": "number"},
                        "units": {"type": "integer"},
                    },
                },
                "label": {"type": "string", "description": "Short name for this option."},
            },
            "required": ["config_changes"],
        },
    },
    {
        "name": "price_the_delay",
        "description": (
            "Turn the permit timeline into dollars. Megawatts of blocked IT load become an "
            "accelerator count at a stated watts-per-GPU and PUE, times the delayed hours, "
            "times utilisation, times today's spot $/GPU-hour. No credits — the pricing feed "
            "is public and cached. Call it after determine_pathway, once you know the "
            "timeline, and after the searches if you have run them, because it reports how "
            "much of the loss a better config or a better parcel recovers.\n"
            "Read the output before you quote it. It is an opportunity cost under an explicit "
            "and generous counterfactual: that the whole blocked load would have been sold at "
            "spot, at that utilisation, for the whole delay. An operator on a contracted lease "
            "has a smaller number and the tool reports that case separately when a reference "
            "contract exists for the site.\n"
            "Two ways to get this wrong. First, double counting: if the campus is grid-"
            "connected and the onsite plant is firming rather than the sole source, the air "
            "permit is not blocking the whole IT load, and you must pass "
            "plant_share_of_it_load. Second, treating the total as a forecast: spot GPU rates "
            "move daily, so present the figure as 'at today's rate' and never as an expected "
            "value over a multi-year delay."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mw_it_load": {
                    "type": "number",
                    "description": "Megawatts of IT load, not plant nameplate. Omit and it is "
                    "derived from the project's generation size divided by PUE, which the "
                    "output flags as derived.",
                },
                "months_delayed": {
                    "type": "number",
                    "description": "Months of delay to price. Omit to use the negative slack "
                    "against the announced energization date, which is the honest default.",
                },
                "gpu_class": {
                    "type": "string",
                    "description": "Accelerator class to price in. Default H100 SXM, the "
                    "market's unit of account.",
                },
                "utilisation": {
                    "type": "number",
                    "description": "Fraction of accelerator-hours actually sold, 0-1. Omit to "
                    "use the 60/80/92% range. Supplying it pins that axis and narrows the "
                    "reported spread, which the output states.",
                },
                "rate": {
                    "type": "number",
                    "description": "$/GPU-hour override. Omit to use the fetched marketplace "
                    "spot rate. A supplied rate is labelled as caller-supplied and unsourced.",
                },
                "pue": {
                    "type": "number",
                    "description": "Power usage effectiveness. Default 1.30. Ignored when both "
                    "an IT load and a plant size are known, because the pair implies it.",
                },
                "plant_share_of_it_load": {
                    "type": "number",
                    "description": "Fraction of the IT load this permitted plant actually "
                    "serves, 0-1. Default 1.0. Set it below 1.0 whenever the campus has grid "
                    "service and the plant is firming — leaving it at 1.0 there overstates the "
                    "loss by the grid-served share.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_alternate_sites",
        "description": (
            "The expensive one, and the one that makes this an agent rather than a "
            "report. Generates candidate parcels in an expanding ring around the current "
            "site, resolves each through the provider, runs the full pathway on each, and "
            "returns them ranked by pathway then timeline. It deliberately crosses county "
            "and state lines, because that is usually where the answer flips. Call it when "
            "the current site lands on major PSD, major nonattainment NSR, or a hard stop. "
            "Do not call it when the site is already minor NSR or permit by rule — there "
            "is nothing to improve and it burns the credit budget."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "radius_km": {
                    "type": "number",
                    "description": "Starting ring radius in km. Default 15. The loop expands "
                    "outward to ~120 km on its own.",
                },
                "n": {
                    "type": "integer",
                    "description": "Candidate parcels to consider. Default 24. Each one costs credits.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "ask_mireye",
        "description": (
            "Open-ended question to the physical-facts provider for the edges that are not "
            "scripted — it resolves the address, fetches whatever fields it needs, measures "
            "distances, and returns the plan it ran so the answer can be replayed. Costs "
            "more than a preset fetch, so use it when no preset covers the question, not as "
            "a first resort. Good uses: 'how much elevation change is there within 10 km of "
            "this parcel', 'what is between this parcel and the nearest residential area'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "request_field",
        "description": (
            "Ask the provider to add a field it does not index yet. Three outcomes and all "
            "three are useful: the field already exists and you get it with a citation; a "
            "near miss you can accept or reject; or a genuine gap, queued with a request id. "
            "Use it for the facts this analysis needs that no preset covers — distance to "
            "the nearest Class I area, background ambient PM2.5 or NO2 at the coordinate, "
            "count and permitted emissions of major stationary sources within a radius. Do "
            "not go build an ingest pipeline for those; request them and record the gap. "
            "Every request needs at least one example location — a real place where you "
            "needed this value and could not get it. It is what the provider verifies the "
            "new field against and where it samples any near miss, so it decides whether "
            "the answer you get back is about your site or someone else's. If you omit it, "
            "the site already resolved by resolve_site is used."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field_name": {"type": "string"},
                "description": {
                    "type": "string",
                    "description": "What the field is, its unit, and why it is a physical-world fact.",
                },
                "example_locations": {
                    "type": "array",
                    "maxItems": 10,
                    "description": (
                        "1-10 real places where this value was needed. Each entry supplies "
                        "exactly one of `address` or `lat`+`lng`. Defaults to the resolved "
                        "site if omitted."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "address": {"type": "string"},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"},
                            "claimed_value": {
                                "type": "string",
                                "description": (
                                    "What you believe the answer is here, if you know. It "
                                    "becomes a frozen eval case for the build. Leave it out "
                                    "rather than guessing."
                                ),
                            },
                            "note": {
                                "type": "string",
                                "description": "Why this location matters.",
                            },
                        },
                    },
                },
                "use_case": {
                    "type": "string",
                    "description": "What decision this value feeds, and what changes at different values.",
                },
                "decision_threshold": {
                    "type": "string",
                    "description": "The value at which the decision flips, if there is one.",
                },
            },
            "required": ["field_name", "description"],
        },
    },
    {
        "name": "verify_construction",
        "description": (
            "Is there a hole in the ground yet? Compares two cloud-free Sentinel-2 scenes over "
            "the parcel — one near the announced groundbreaking date, one as recent as the "
            "archive has — and reports how much of the footprint changed from vegetated to bare. "
            "Free: public Copernicus imagery, no credential, no provider credits.\n"
            "Call it when the project has an announced groundbreaking or energization date and "
            "you want a physical check on the schedule. The permit pathway says what is legally "
            "possible; this says what is actually on the dirt. A site 14 months past its "
            "announced groundbreaking with an unbroken parcel does not hold its announced "
            "energization date, whatever the permit says.\n"
            "Read the result honestly:\n"
            "- Sentinel-2 is 10 m per pixel. It sees clearing, grading, laydown yards and large "
            "pads. It cannot see a turbine foundation, a transformer or anything under ~20 m. "
            "Never report equipment from this tool.\n"
            "- insufficient_imagery is a real answer, not a failure. It means the only scenes "
            "available were cloudy, or the catalog was unreachable. Say so; do not substitute a "
            "guess.\n"
            "- The verdict corroborates, it does not prove. A cleared pad is not a permitted "
            "plant and an empty parcel is not proof a project is dead.\n"
            "- Quote the scene ids, acquisition dates and cloud fractions next to any claim you "
            "make from this. They are in the result for that reason.\n"
            "- The footprint is a circle around the coordinate, not a parcel boundary. If the "
            "site was resolved from an approximate coordinate rather than a rooftop geocode, say "
            "that the read may be looking at the wrong ground."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "announced_groundbreaking": {
                    "type": "string",
                    "description": "When ground was announced to break, in the form the source "
                    "states it: '2025-09', 'Q4 2026', '2024-06-15'. Drives which scene is used "
                    "as the baseline.",
                },
                "announced_energization": {
                    "type": "string",
                    "description": "The announced energization or in-service date, same forms. "
                    "Used to report how much schedule is left against what is on the ground.",
                },
                "radius_m": {
                    "type": "number",
                    "description": "Footprint radius in metres. Default 500. Use the campus "
                    "scale, not the building: 500 for a single plant, 800-1200 for a large "
                    "campus. Too small misses the pad; too large dilutes it with neighbours.",
                },
                "lat": {
                    "type": "number",
                    "description": "Latitude. Defaults to the resolved site.",
                },
                "lon": {
                    "type": "number",
                    "description": "Longitude. Defaults to the resolved site.",
                },
            },
            "required": [],
        },
    },
]

TOOL_NAMES = tuple(t["name"] for t in TOOL_SCHEMAS)


# --------------------------------------------------------------------------
# Jurisdiction normalisation
# --------------------------------------------------------------------------
#
# Providers return the state as a code, as a full name, or not at all, and the
# county with or without the word "County". The pathway engine keys its state
# overlays on the two-letter postal code, so getting this wrong is not cosmetic:
# truncating "New Jersey" to "NE" silently loads the federal default overlay
# instead of NJ DEP's, and the Ozone Transport Region and EJ-denial triggers
# never fire. That bug shipped once. It does not ship again.

#: (state FIPS, postal code, name). FIPS is the most reliable of the three
#: because it comes off the county code the geocoder already returned.
_STATES: tuple[tuple[str, str, str], ...] = (
    ("01", "AL", "alabama"), ("02", "AK", "alaska"), ("04", "AZ", "arizona"),
    ("05", "AR", "arkansas"), ("06", "CA", "california"), ("08", "CO", "colorado"),
    ("09", "CT", "connecticut"), ("10", "DE", "delaware"), ("11", "DC", "district of columbia"),
    ("12", "FL", "florida"), ("13", "GA", "georgia"), ("15", "HI", "hawaii"),
    ("16", "ID", "idaho"), ("17", "IL", "illinois"), ("18", "IN", "indiana"),
    ("19", "IA", "iowa"), ("20", "KS", "kansas"), ("21", "KY", "kentucky"),
    ("22", "LA", "louisiana"), ("23", "ME", "maine"), ("24", "MD", "maryland"),
    ("25", "MA", "massachusetts"), ("26", "MI", "michigan"), ("27", "MN", "minnesota"),
    ("28", "MS", "mississippi"), ("29", "MO", "missouri"), ("30", "MT", "montana"),
    ("31", "NE", "nebraska"), ("32", "NV", "nevada"), ("33", "NH", "new hampshire"),
    ("34", "NJ", "new jersey"), ("35", "NM", "new mexico"), ("36", "NY", "new york"),
    ("37", "NC", "north carolina"), ("38", "ND", "north dakota"), ("39", "OH", "ohio"),
    ("40", "OK", "oklahoma"), ("41", "OR", "oregon"), ("42", "PA", "pennsylvania"),
    ("44", "RI", "rhode island"), ("45", "SC", "south carolina"), ("46", "SD", "south dakota"),
    ("47", "TN", "tennessee"), ("48", "TX", "texas"), ("49", "UT", "utah"),
    ("50", "VT", "vermont"), ("51", "VA", "virginia"), ("53", "WA", "washington"),
    ("54", "WV", "west virginia"), ("55", "WI", "wisconsin"), ("56", "WY", "wyoming"),
    ("72", "PR", "puerto rico"),
)
_STATE_BY_FIPS = {fips: code for fips, code, _ in _STATES}
_STATE_BY_NAME = {name: code for _, code, name in _STATES}
_STATE_CODES = {code for _, code, _ in _STATES}

_COUNTY_SUFFIXES = (
    " county", " parish", " borough", " census area", " municipality", " city and borough"
)


def normalize_state(value: Any, county_fips: str | None = None) -> str:
    """Two-letter postal code, or '??'.

    The county FIPS wins when it is present, because a five-digit FIPS is
    unambiguous and a provider's `state` field is not.
    """
    if county_fips:
        code = _STATE_BY_FIPS.get(str(county_fips).zfill(5)[:2])
        if code:
            return code
    if value is None:
        return "??"
    text = str(value).strip()
    if len(text) == 2 and text.upper() in _STATE_CODES:
        return text.upper()
    code = _STATE_BY_NAME.get(text.lower())
    return code or "??"


def normalize_county(value: Any) -> str:
    """County name without the trailing 'County' / 'Parish' / 'Borough'.

    Keeps 'Cumberland County County' out of the narrative, and matters more
    than that for the docket search, which appends the suffix itself.
    """
    if value is None:
        return "unknown"
    text = str(value).strip()
    low = text.lower()
    for suffix in _COUNTY_SUFFIXES:
        if low.endswith(suffix):
            return text[: -len(suffix)].strip() or text
    return text


# --------------------------------------------------------------------------
# Fact folding
# --------------------------------------------------------------------------

#: Provider field names are not frozen yet, so map returned facts onto the
#: SiteContext fields the pathway engine reads by substring, and record which
#: key mapped to which field so the mapping is auditable rather than magic.
_SITE_FACT_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("terrain_relief_m", ("terrain_relief", "relief", "elevation_range", "elevation_delta")),
    ("gas_pipeline_km", ("gas_pipeline", "pipeline_distance", "nearest_pipeline")),
    ("transmission_km", ("transmission_distance", "nearest_transmission", "transmission_km")),
    ("transmission_kv", ("transmission_voltage", "line_voltage", "voltage_kv", "transmission_kv")),
    ("nearest_airport_km", ("airport_distance", "nearest_airport")),
    ("residential_within_1km", ("residential_count", "residents_within", "population_1km", "households_within")),
)

_KM_PER_MILE = 1.609344


def _to_km(value: float, unit: str | None) -> float:
    if not unit:
        return float(value)
    u = unit.strip().lower()
    if u in ("m", "meter", "meters", "metre", "metres"):
        return float(value) / 1000.0
    if u in ("mi", "mile", "miles"):
        return float(value) * _KM_PER_MILE
    if u in ("ft", "feet", "foot"):
        return float(value) * 0.3048 / 1000.0
    return float(value)


def _to_m(value: float, unit: str | None) -> float:
    if not unit:
        return float(value)
    u = unit.strip().lower()
    if u in ("ft", "feet", "foot"):
        return float(value) * 0.3048
    if u in ("km", "kilometer", "kilometers"):
        return float(value) * 1000.0
    return float(value)


def fold_facts_into_site(ctx: ToolContext) -> dict[str, str]:
    """Push provider facts onto the SiteContext fields the pathway engine reads.

    Returns {site_field: fact_key} so the trace can show exactly which cited
    fact drove which trigger.
    """
    site = ctx.site
    if site is None:
        return {}
    mapped: dict[str, str] = {}

    for target, hints in _SITE_FACT_HINTS:
        if getattr(site, target, None) is not None:
            continue
        for key, fact in ctx.facts.facts.items():
            low = key.lower()
            if not any(h in low for h in hints):
                continue
            try:
                raw = float(fact.value)
            except (TypeError, ValueError):
                continue
            if target.endswith("_km"):
                value: float | int = _to_km(raw, fact.unit)
            elif target.endswith("_m"):
                value = _to_m(raw, fact.unit)
            elif target.endswith("_kv"):
                value = raw
            else:
                value = int(raw)
            setattr(site, target, value)
            mapped[target] = key
            break

    # Class I areas arrive as (name, distance) pairs or as a distance fact.
    for key, fact in ctx.facts.facts.items():
        low = key.lower()
        if "class_i" not in low and "class1" not in low:
            continue
        try:
            km = _to_km(float(fact.value), fact.unit)
        except (TypeError, ValueError):
            continue
        name = fact.note or key
        if all(existing[0] != name for existing in site.class_i_areas):
            site.class_i_areas.append((name, km))
            mapped.setdefault("class_i_areas", key)

    # Proximity results map straight through and are more reliable than the
    # preset fields, so they win.
    prox_map = {
        "gas_pipeline": "gas_pipeline_km",
        "transmission": "transmission_km",
        "airport": "nearest_airport_km",
    }
    for target, result in ctx.proximity.items():
        attr = prox_map.get(target)
        if attr:
            setattr(site, attr, float(result.distance_km))
            mapped[attr] = f"proximity:{target}"
            if target == "transmission":
                kv = result.attributes.get("voltage_kv") or result.attributes.get("kv")
                if kv:
                    try:
                        site.transmission_kv = float(kv)
                    except (TypeError, ValueError):
                        pass
    return mapped


def _fact_rows(fs: FactSet, keys: Iterable[str] | None = None, limit: int = 40) -> list[dict]:
    rows = []
    items = list(fs.facts.items())
    if keys is not None:
        wanted = set(keys)
        items = [(k, f) for k, f in items if k in wanted]
    for key, fact in items[:limit]:
        rows.append(
            {
                "key": key,
                "value": fact.value,
                "unit": fact.unit,
                "source": fact.source,
                "fetched": fact.fetched,
                "confidence": fact.confidence,
            }
        )
    return rows


# --------------------------------------------------------------------------
# Regulatory context loading
# --------------------------------------------------------------------------


def _call_flexible(fn: Callable, **kwargs) -> Any:
    """Call `fn` with whichever of `kwargs` its signature accepts.

    The ingest modules are being written in parallel. Rather than guess their
    exact signatures and break, pass what fits and let anything else through
    positionally.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(kwargs.get("fips"))
    params = sig.parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return fn(**kwargs)
    accepted = {k: v for k, v in kwargs.items() if k in params}
    if accepted:
        return fn(**accepted)
    positional = [
        p
        for p in params.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) == 1:
        first = next((v for v in kwargs.values() if v is not None), None)
        return fn(first)
    return fn()


def _resolve_ingest(module_name: str, candidates: tuple[str, ...]) -> tuple[Callable | None, str | None]:
    try:
        module = __import__(f"ingest.{module_name}", fromlist=["*"])
    except Exception as exc:  # module not written yet, or import-time failure
        return None, f"ingest.{module_name} unavailable ({exc.__class__.__name__}: {exc})"
    for name in candidates:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn, None
    return None, f"ingest.{module_name} imported but has none of {', '.join(candidates)}"


_GREENBOOK_FUNCS = (
    "nonattainment_for",
    "designations_for",
    "status_for_county",
    "for_county",
    "county_status",
    "lookup",
)
_COUNTY_FUNCS = ("for_fips", "county_record", "for_county", "record_for", "lookup", "county")
_DOCKET_FUNCS = ("for_county", "cases_for", "search_cases", "dockets_for", "search", "lookup")


def _as_nonattainment(raw: Any) -> list[NonattainmentStatus]:
    out: list[NonattainmentStatus] = []
    if raw is None:
        return out
    if isinstance(raw, (NonattainmentStatus,)):
        return [raw]
    if isinstance(raw, dict):
        raw = [raw]
    for item in raw:
        if isinstance(item, NonattainmentStatus):
            out.append(item)
        elif isinstance(item, dict):
            pollutant = item.get("pollutant") or item.get("parameter") or item.get("naaqs")
            if not pollutant:
                continue
            out.append(
                NonattainmentStatus(
                    pollutant=str(pollutant).lower().replace(".", "").replace("-", ""),
                    classification=str(
                        item.get("classification") or item.get("class") or "unclassified"
                    ).lower(),
                    area_name=str(item.get("area_name") or item.get("area") or "unnamed area"),
                    source=str(item.get("source") or "EPA Green Book"),
                    fetched=item.get("fetched"),
                )
            )
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            out.append(
                NonattainmentStatus(
                    pollutant=str(item[0]).lower(),
                    classification=str(item[1]).lower(),
                    area_name=str(item[2]) if len(item) > 2 else "unnamed area",
                )
            )
    return out


def _as_county_record(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    out = {}
    for key in (
        "moratorium",
        "moratorium_note",
        "zoning_posture",
        "board_history",
        "note",
        "source",
        "source_name",
        "source_url",
        "confidence",
    ):
        if hasattr(raw, key):
            out[key] = getattr(raw, key)
    if "source" not in out and out.get("source_name"):
        out["source"] = f"{out['source_name']} — {out.get('source_url', '')}".strip(" —")
    return out


def _as_cases(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    out = []
    for item in raw:
        if isinstance(item, str):
            out.append(item)
        elif hasattr(item, "summary") and callable(item.summary):
            out.append(item.summary())
        elif isinstance(item, dict):
            name = (
                item.get("caseName")
                or item.get("case_name")
                or item.get("name")
                or item.get("title")
                or "unnamed case"
            )
            court = item.get("court") or item.get("court_id") or ""
            docket = item.get("docketNumber") or item.get("docket_number") or ""
            out.append(" ".join(str(p) for p in (name, court, docket) if p).strip())
    return out


def load_regulatory_context(
    fips: str | None,
    county: str | None,
    state: str | None,
    developer: str | None = None,
) -> dict:
    """Pull Green Book, county file and dockets for one county.

    Returns a dict with the normalised values plus, for each source, whether it
    was actually available. A missing source is reported as missing — it is not
    silently treated as "attainment, no moratorium, no litigation", because that
    reads as a clean site when it is really an unread one.
    """
    result: dict[str, Any] = {
        "fips": fips,
        "county": county,
        "state": state,
        "nonattainment": [],
        "moratorium": False,
        "moratorium_note": None,
        "zoning_posture": None,
        "litigation": [],
        "sources": {},
        "gaps": [],
    }

    fn, err = _resolve_ingest("greenbook", _GREENBOOK_FUNCS)
    if fn is None:
        result["sources"]["greenbook"] = {"available": False, "note": err}
        result["gaps"].append(
            "County attainment status not loaded. Nonattainment is the single fact most "
            "likely to flip the pathway, so treat this screen as incomplete."
        )
    else:
        try:
            statuses = _as_nonattainment(
                _call_flexible(fn, fips=fips, county=county, state=state)
            )
            result["nonattainment"] = [
                {
                    "pollutant": s.pollutant,
                    "classification": s.classification,
                    "area_name": s.area_name,
                    "source": s.source,
                    "fetched": s.fetched,
                }
                for s in statuses
            ]
            result["_status_objects"] = statuses
            result["sources"]["greenbook"] = {
                "available": True,
                "note": f"{len(statuses)} designation(s)",
                "source": "EPA Green Book, 40 CFR 81",
            }
        except Exception as exc:
            result["sources"]["greenbook"] = {"available": False, "note": f"{exc}"}
            result["gaps"].append(f"Green Book lookup failed: {exc}")

    fn, err = _resolve_ingest("counties", _COUNTY_FUNCS)
    if fn is None:
        result["sources"]["counties"] = {"available": False, "note": err}
        result["gaps"].append("County moratorium and zoning file not loaded.")
    else:
        try:
            record = _as_county_record(_call_flexible(fn, fips=fips, county=county, state=state))
            result["moratorium"] = bool(record.get("moratorium", False))
            result["moratorium_note"] = record.get("moratorium_note") or record.get("note")
            result["zoning_posture"] = record.get("zoning_posture")
            result["sources"]["counties"] = {
                "available": True,
                "note": "hand-entered county file" if record else "county not in the file",
                "source": record.get("source", "ingest/counties.json (hand entered)"),
            }
        except Exception as exc:
            result["sources"]["counties"] = {"available": False, "note": f"{exc}"}

    fn, err = _resolve_ingest("dockets", _DOCKET_FUNCS)
    if fn is None:
        result["sources"]["dockets"] = {"available": False, "note": err}
    else:
        try:
            cases = _as_cases(
                _call_flexible(fn, fips=fips, county=county, state=state, developer=developer)
            )
            result["litigation"] = cases
            result["sources"]["dockets"] = {
                "available": True,
                "note": f"{len(cases)} case(s)",
                "source": "CourtListener / RECAP",
            }
        except Exception as exc:
            result["sources"]["dockets"] = {"available": False, "note": f"{exc}"}

    return result


# --------------------------------------------------------------------------
# Config building
# --------------------------------------------------------------------------


def build_config(base: GenerationConfig, changes: dict | None) -> GenerationConfig:
    """Apply a partial config override to a base config. Raises ConfigError if
    the combination is not physically or legally coherent."""
    changes = dict(changes or {})
    kwargs = {
        "mw": float(changes.get("mw", base.mw)),
        "prime_mover": PrimeMover(changes["prime_mover"])
        if "prime_mover" in changes
        else base.prime_mover,
        "fuel": Fuel(changes["fuel"]) if "fuel" in changes else base.fuel,
        # Control.NONE is a legitimate enum value and a natural thing for a
        # caller to send for "uncontrolled", but it carries no efficiency
        # entry, so it is dropped rather than passed through to the estimator.
        "controls": tuple(c for c in (Control(x) for x in changes["controls"]) if c is not Control.NONE)
        if "controls" in changes
        else tuple(c for c in base.controls if c is not Control.NONE),
        "run_hours": float(changes.get("run_hours", base.run_hours)),
        "enforceable_limit": bool(changes.get("enforceable_limit", base.enforceable_limit)),
        "heat_rate_btu_kwh": changes.get("heat_rate_btu_kwh", base.heat_rate_btu_kwh),
        "units": int(changes.get("units", base.units)),
    }
    # A control set that no longer applies to the new prime mover is dropped
    # rather than raising, so "switch to combined cycle" does not fail just
    # because a Tier 4 flag was hanging around.
    pm = kwargs["prime_mover"]
    if pm is not PrimeMover.DIESEL_RECIP:
        kwargs["controls"] = tuple(c for c in kwargs["controls"] if c is not Control.TIER4)
    if "turbine" not in pm.value:
        kwargs["controls"] = tuple(
            c for c in kwargs["controls"] if c not in (Control.DLN, Control.WATER_INJECTION)
        )
    if pm is PrimeMover.DIESEL_RECIP:
        kwargs["fuel"] = Fuel.DIESEL
    elif pm in (PrimeMover.RECIP_LEAN_BURN, PrimeMover.RECIP_RICH_BURN, PrimeMover.FUEL_CELL):
        kwargs["fuel"] = Fuel.NATURAL_GAS
    return GenerationConfig(**kwargs)


def estimate_summary(est: EmissionsEstimate) -> dict:
    pollutant, tpy = est.max_criteria_tpy()
    return {
        "config": est.config.describe(),
        "heat_input_mmbtu_hr": round(est.heat_input_mmbtu_hr, 1),
        "tons_per_year": {p: round(v, 1) for p, v in est.tons_per_year.items()},
        "largest_criteria_pollutant": pollutant,
        "largest_criteria_tpy": round(tpy, 1),
        "above_significant_emission_rate": {
            p: round(v, 1) for p, v in est.significant().items()
        },
        "hap_tpy": round(est.total_hap_tpy(), 2),
        "basis": est.basis,
    }


def pathway_summary(result: PathwayResult) -> dict:
    return {
        "pathway": result.pathway.value,
        "label": result.pathway.label,
        "rank": result.pathway.rank,
        "months_low": round(result.months_low, 1),
        "months_likely": round(result.months_likely, 1),
        "months_high": round(result.months_high, 1),
        "controlling_pollutant": result.controlling_pollutant,
        "controlling_tpy": round(result.controlling_tpy, 1) if result.controlling_tpy else None,
        "applicable_threshold_tpy": result.applicable_threshold,
        "source_category": {
            "on_list_of_28": result.source_category.on_list_of_28,
            "category": result.source_category.category,
            "threshold_tpy": result.source_category.threshold_tpy,
            "reasoning": result.source_category.reasoning,
            "citation": result.source_category.citation,
        },
        "triggers_fired": [
            {
                "name": t.name,
                "detail": t.detail,
                "citation": t.citation,
                "months_added": t.months_added,
            }
            for t in result.fired
        ],
        "triggers_clear": [t.name for t in result.triggers if not t.fired],
        "bact_pollutants": {p: round(v, 1) for p, v in result.bact_pollutants.items()},
        "offsets_required_tons": round(result.offsets_required_tons, 1)
        if result.offsets_required_tons
        else None,
        "hard_stops": result.hard_stops,
        "narrative": result.narrative,
    }


# --------------------------------------------------------------------------
# Executors
# --------------------------------------------------------------------------


def _same_address(a: str | None, b: str | None) -> bool:
    """Whether two address strings name the same input.

    Deliberately strict. A coordinate that differs in the fifth decimal is a
    different parcel for our purposes, and treating it as the same one is how a
    permit answer ends up attached to the wrong county.
    """
    if not a or not b:
        return False
    return " ".join(str(a).split()).strip().lower() == " ".join(str(b).split()).strip().lower()


def _exec_resolve_site(ctx: ToolContext, args: dict) -> dict:
    address = args.get("address") or ctx.project.address
    min_confidence = float(args.get("min_confidence", 0.8))
    project = ctx.project

    # Only the announced parcel becomes ctx.site. A model exploring the map will
    # call this on a candidate coordinate, and letting that overwrite the origin
    # produced a report describing Cumberland County NJ's pathway under Kent
    # County DE's name. Getting the jurisdiction wrong on an air permit answer is
    # the exact failure this product exists to catch, so it must not happen here.
    is_origin = ctx.site is None or _same_address(address, project.address)

    try:
        ctx.spend("geocode")
        location = ctx.provider.geocode(address, min_confidence=min_confidence)
    except ResolutionError as exc:
        ctx.resolved = False
        ctx.resolution_note = str(exc)
        declared = project.declared_jurisdiction()
        if declared and is_origin:
            ctx.site = SiteContext(
                state=declared["state"],
                county=declared["county"],
                county_fips=declared.get("fips"),
                latitude=declared.get("latitude"),
                longitude=declared.get("longitude"),
            )
            ctx.facts.add(
                Fact(
                    key="jurisdiction",
                    value=f"{declared['county']} County, {declared['state']}",
                    source="user-declared (unverified)",
                    fetched=now_iso(),
                    confidence=None,
                    note="Provider refused the geocode. This jurisdiction came from the "
                    "project input, not from a resolved parcel.",
                )
            )
            return {
                "resolved": False,
                "refused": True,
                "reason": str(exc),
                "declared_jurisdiction": declared,
                "guidance": (
                    "Screening will proceed against the declared county, but every "
                    "conclusion must be labelled unverified. Parcel-level facts "
                    "(terrain, pipeline distance, receptors) are not available."
                ),
            }
        return {
            "resolved": False,
            "refused": True,
            "reason": str(exc),
            "guidance": (
                "No canonical parcel and no declared county. Do not guess a "
                "jurisdiction — stop and report that the site could not be resolved."
            ),
        }

    ctx.location = location
    ctx.resolved = True
    ctx.facts.add(
        Fact(
            key="parcel",
            value=location.formatted_address or address,
            source=location.source or ctx.provider.name,
            fetched=location.fetched or now_iso(),
            confidence=location.confidence,
        )
    )

    ctx.spend("lookup")
    lookup = ctx.provider.lookup(location)
    ctx.facts = ctx.facts.merge(lookup)

    county = location.county or (lookup.get("county") if lookup else None)
    state = location.state or (lookup.get("state") if lookup else None)
    fips = location.county_fips or (lookup.get("county_fips") if lookup else None)

    resolved_site = SiteContext(
        state=normalize_state(state, fips),
        county=normalize_county(county),
        county_fips=fips,
        latitude=location.latitude,
        longitude=location.longitude,
    )
    if is_origin:
        ctx.site = resolved_site
        fold_facts_into_site(ctx)

    overlay = overlay_for(resolved_site.state, resolved_site.county)
    return {
        "resolved": True,
        "formatted_address": location.formatted_address,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "county": ctx.site.county,
        "state": ctx.site.state,
        "county_fips": ctx.site.county_fips,
        "parcel_id": location.parcel_id,
        "confidence": location.confidence,
        "source": location.source or ctx.provider.name,
        "fetched": location.fetched or now_iso(),
        "permitting_agency": overlay["agency"],
        "agency_note": overlay["notes"],
        "lookup_facts": _fact_rows(lookup),
    }


def _exec_get_physical_facts(ctx: ToolContext, args: dict) -> dict:
    if ctx.location is None:
        raise ToolError(
            "No resolved location. resolve_site refused or was not called; parcel-level "
            "facts are not available and must not be assumed."
        )
    intents = [i for i in args.get("intents", []) if i in PRESET_INTENTS]
    if not intents:
        raise ToolError(f"No valid intents. Pick from: {', '.join(sorted(PRESET_INTENTS))}")
    reason = args.get("reason", "")

    ctx.spend("preset", len(intents))
    fetched = ctx.provider.fetch(ctx.location, intents)
    ctx.facts = ctx.facts.merge(fetched)
    ctx.intents_fetched.extend(i for i in intents if i not in ctx.intents_fetched)
    mapped = fold_facts_into_site(ctx)

    return {
        "intents": intents,
        "reason": reason,
        "fields_returned": len(fetched),
        "facts": _fact_rows(fetched),
        "mapped_to_site_context": mapped,
        "note": (
            "Provider returned no fields for these presets."
            if len(fetched) == 0
            else "Every value above carries its own source and fetch timestamp."
        ),
    }


def _exec_get_proximity(ctx: ToolContext, args: dict) -> dict:
    if ctx.location is None:
        raise ToolError("No resolved location. resolve_site first.")
    targets = [t for t in args.get("targets", []) if t in PROXIMITY_TARGETS]
    if not targets:
        raise ToolError(f"No valid targets. Pick from: {', '.join(sorted(PROXIMITY_TARGETS))}")

    ctx.spend("proximity_target", len(targets))
    results = ctx.provider.proximity(ctx.location, targets)
    ctx.proximity.update(results)
    for name, res in results.items():
        ctx.facts.add(
            Fact(
                key=f"proximity.{name}",
                value=round(res.distance_km, 2),
                unit="km",
                source=res.source or ctx.provider.name,
                fetched=res.fetched or now_iso(),
                note=("by road" if res.by_road else "great circle")
                + (f" — {res.name}" if res.name else ""),
            )
        )
    mapped = fold_facts_into_site(ctx)

    return {
        "targets": targets,
        "reason": args.get("reason", ""),
        "results": {
            name: {
                "distance_km": round(res.distance_km, 2),
                "name": res.name,
                "by_road": res.by_road,
                "attributes": res.attributes,
                "source": res.source,
                "fetched": res.fetched,
            }
            for name, res in results.items()
        },
        "missing": [t for t in targets if t not in results],
        "mapped_to_site_context": mapped,
    }


def _exec_get_regulatory_context(ctx: ToolContext, args: dict) -> dict:
    site = ctx.require_site()
    fips = args.get("fips") or site.county_fips
    data = load_regulatory_context(
        fips=fips,
        county=site.county,
        state=site.state,
        developer=getattr(ctx.project, "developer", None),
    )

    statuses = data.pop("_status_objects", None) or []
    site.nonattainment = list(statuses)
    site.moratorium = bool(data["moratorium"])
    site.moratorium_note = data["moratorium_note"]
    site.zoning_posture = data["zoning_posture"]
    site.litigation = list(data["litigation"])

    overlay = overlay_for(site.state)
    data["state_overlay"] = {
        "agency": overlay["agency"],
        "timeline_multiplier": overlay["multiplier"],
        "permit_by_rule": overlay.get("permit_by_rule", False),
        "state_toxics": overlay.get("state_toxics", False),
        "ozone_transport_region": overlay.get("otr", False),
        "ej_denial_authority": overlay.get("ej_denial_authority", False),
        "notes": overlay["notes"],
        "source": overlay["source"],
    }
    data["unknowns"] = [
        k
        for k, present in (
            ("class_i_area_distance", bool(site.class_i_areas)),
            ("psd_increment_consumed", bool(site.increment_consumed)),
            ("background_ambient_concentration", False),
        )
        if not present
    ]
    if data["unknowns"]:
        data["gaps"].append(
            "Not indexed by any wired source: "
            + ", ".join(data["unknowns"])
            + ". These are pure geometry or monitor data over public federal boundaries — "
            "request_field is the right route, not a bespoke ingest."
        )
    return data


def _exec_estimate_emissions(ctx: ToolContext, args: dict) -> dict:
    try:
        config = build_config(ctx.config(), args.get("config"))
    except (ConfigError, ValueError) as exc:
        raise ToolError(f"Config is not coherent: {exc}") from exc
    est = estimate(config)
    ctx.estimate = est
    out = estimate_summary(est)
    threshold_note = (
        "Potential to emit is computed at 8760 hr/yr because there is no federally "
        "enforceable cap in this config. Intended dispatch does not lower PTE."
        if not config.enforceable_limit
        else f"Potential to emit reflects a federally enforceable {config.run_hours:,.0f} hr/yr cap."
    )
    out["threshold_note"] = threshold_note
    out["significant_emission_rates_tpy"] = SIGNIFICANT_EMISSION_RATES
    return out


def _exec_determine_pathway(ctx: ToolContext, args: dict) -> dict:
    site = ctx.require_site()
    if ctx.estimate is None:
        _exec_estimate_emissions(ctx, {})
    assert ctx.estimate is not None
    result = determine_pathway(ctx.estimate, site)
    ctx.pathway = result
    out = pathway_summary(result)
    cap = synthetic_minor_cap(ctx.estimate, site)
    out["synthetic_minor_option"] = cap
    out["unverified_jurisdiction"] = not ctx.resolved
    return out


def _exec_test_config(ctx: ToolContext, args: dict) -> dict:
    site = ctx.require_site()
    baseline_est = ctx.estimate or estimate(ctx.config())
    baseline = ctx.pathway or determine_pathway(baseline_est, site)

    try:
        config = build_config(ctx.config(), args.get("config_changes"))
    except (ConfigError, ValueError) as exc:
        return {
            "feasible": False,
            "label": args.get("label"),
            "reason": f"Config is not coherent: {exc}",
        }
    est = estimate(config)
    result = determine_pathway(est, site)

    return {
        "feasible": True,
        "label": args.get("label") or config.describe(),
        "config": config.describe(),
        "emissions": estimate_summary(est),
        "pathway": pathway_summary(result),
        "delta": {
            "pathway_from": baseline.pathway.value,
            "pathway_to": result.pathway.value,
            "rank_change": baseline.pathway.rank - result.pathway.rank,
            "months_saved": round(baseline.months_likely - result.months_likely, 1),
            "hard_stops_cleared": [s for s in baseline.hard_stops if s not in result.hard_stops],
            "hard_stops_added": [s for s in result.hard_stops if s not in baseline.hard_stops],
        },
        "availability": (
            round(config.run_hours / 8760.0, 3) if config.enforceable_limit else 1.0
        ),
    }


def _exec_price_the_delay(ctx: ToolContext, args: dict) -> dict:
    from types import SimpleNamespace

    from . import economics  # local import keeps the module graph acyclic
    from .planner import energization_probability

    if ctx.pathway is None:
        raise ToolError(
            "No pathway yet. Call determine_pathway first — the delay is priced against the "
            "timeline that produces, not against the config."
        )
    gpu_class = args.get("gpu_class") or economics.DEFAULT_GPU_CLASS
    try:
        economics.power_for(gpu_class)
    except KeyError as exc:
        raise ToolError(str(exc)) from exc

    months = args.get("months_delayed")
    probability = energization_probability(ctx.project, ctx.pathway)
    if months is None and probability.slack_months is None:
        raise ToolError(
            "No announced energization date, so there is no delay to price against it. Pass "
            "months_delayed explicitly if you want the pathway's own duration valued, and say "
            "in your conclusion that is what you priced."
        )

    valuation = economics.value_for_assessment(
        SimpleNamespace(
            project=ctx.project,
            site=ctx.site,
            pathway=ctx.pathway,
            probability=probability,
            configs=ctx.config_search,
            alternate=ctx.alternate,
        ),
        it_load_mw=float(args["mw_it_load"]) if args.get("mw_it_load") is not None else None,
        gpu_class=gpu_class,
        utilisation=float(args["utilisation"]) if args.get("utilisation") is not None else None,
        rate=float(args["rate"]) if args.get("rate") is not None else None,
        pue=float(args["pue"]) if args.get("pue") is not None else None,
        plant_share_of_it_load=float(args.get("plant_share_of_it_load", 1.0)),
        months_delayed=float(months) if months is not None else None,
    )
    if valuation is None:
        raise ToolError(
            "Could not price the delay. Either no spot rate was available for this GPU class "
            "and none was supplied, or the inputs were out of range. Do not substitute a rate "
            "of your own — report that the delay is not priced."
        )

    out = valuation.to_dict()
    out["cost_of_being_wrong"] = economics.cost_of_being_wrong(
        valuation.it_load_mw,
        gpu_class=gpu_class,
        plant_share_of_it_load=float(args.get("plant_share_of_it_load", 1.0)),
    )
    out["quoting_rules"] = [
        "Quote the likely figure with its range, never the point alone.",
        "Say 'at today's spot rate'. It is a mark, not a forecast, and a multi-year "
        "extrapolation of a spot GPU price is not defensible.",
        "Say it is an opportunity cost under the counterfactual printed above, and that a "
        "contracted lease produces a smaller number.",
        "If the plant is not the sole power source, the figure is an upper bound until "
        "plant_share_of_it_load is set.",
    ]
    return out


def _exec_search_alternate_sites(ctx: ToolContext, args: dict) -> dict:
    from .search import search_alternate_sites  # local import keeps the module graph acyclic

    site = ctx.require_site()
    if site.latitude is None or site.longitude is None:
        raise ToolError(
            "No coordinate for the current site, so there is no ring to search around. "
            "This needs a resolved parcel."
        )
    if ctx.estimate is None:
        _exec_estimate_emissions(ctx, {})
    baseline = ctx.pathway or determine_pathway(ctx.estimate, site)  # type: ignore[arg-type]

    result = search_alternate_sites(
        site,
        ctx.config(),
        provider=ctx.provider,
        regulatory_lookup=load_regulatory_context,
        radius_km=float(args.get("radius_km", 15.0)),
        n_candidates=int(args.get("n", 24)),
        baseline=baseline,
        budget=ctx,
        cache=ctx.candidate_cache,
    )
    ctx.notes.extend(result.notes)
    ctx.alternate = result
    return result.to_dict()


def _exec_ask_mireye(ctx: ToolContext, args: dict) -> dict:
    if ctx.location is None:
        raise ToolError("No resolved location. resolve_site first.")
    question = args.get("question", "").strip()
    if not question:
        raise ToolError("Empty question.")
    ctx.spend("ask")
    answer = ctx.provider.ask(ctx.location, question)
    ctx.facts = ctx.facts.merge(answer)
    mapped = fold_facts_into_site(ctx)
    return {
        "question": question,
        "fields_returned": len(answer),
        "facts": _fact_rows(answer),
        "mapped_to_site_context": mapped,
        "note": "Provider returned nothing for this question." if len(answer) == 0 else None,
    }


def _exec_request_field(ctx: ToolContext, args: dict) -> dict:
    name = args.get("field_name", "").strip()
    description = args.get("description", "").strip()
    if not name:
        raise ToolError("field_name is required.")

    # The provider requires at least one example location and the model rarely
    # thinks to supply one — the ask reads like a catalog question, not a
    # question about a place. The site we already resolved is the honest
    # default: it is where the gap was actually hit. Nothing is fabricated; if
    # there is no resolved site and the model named none, we refuse.
    supplied = args.get("example_locations") or []
    if not isinstance(supplied, list):
        raise ToolError("example_locations must be a list of {address} or {lat, lng} objects.")
    if not supplied and ctx.location is None:
        raise ToolError(
            "request_field needs at least one example location. Call resolve_site first, "
            "or pass example_locations=[{'address': '...'}] naming a real place where this "
            "value was needed."
        )

    record = {
        "field_name": name,
        "description": description,
        "requested_at": now_iso(),
        "example_locations": supplied or None,
    }
    try:
        ctx.spend("field_request")
        response = ctx.provider.field_request(
            name,
            description,
            example_locations=supplied,
            default_location=ctx.location,
            use_case=(args.get("use_case") or "").strip() or None,
            decision_threshold=(args.get("decision_threshold") or "").strip() or None,
        )
        record.update(
            {
                "supported": True,
                "response": response,
                "outcome": response.get("outcome"),
                "request_id": response.get("request_id"),
                "status": response.get("status"),
            }
        )
    except NotImplementedError as exc:
        record.update(
            {
                "supported": False,
                "outcome": "genuine gap",
                "response": None,
                "note": f"{exc}. This is a real hole in the catalog for air permitting work; "
                "record it and source the fact elsewhere or state it as unknown.",
            }
        )
    except Exception as exc:
        record.update({"supported": False, "outcome": "error", "note": str(exc)})
    ctx.field_requests.append(record)
    return record


#: Mireye land-cover fields that bear on construction state. Read out of the
#: fact set the run already paid for rather than fetched again — the point of
#: putting them next to the imagery is that Mireye answers first, and the
#: difference between a point sample and a footprint mean is then visible in
#: one result instead of being argued about.
_LAND_COVER_KEYS = (
    "ndvi_current",
    "ndvi_change_5y",
    "lcms_class",
    "land_use_class",
    "tree_canopy_pct",
    "primary_building_footprint_sqm",
    "cdl_class",
)


def _exec_verify_construction(ctx: ToolContext, args: dict) -> dict:
    # Imported here rather than at module scope so a missing or broken imagery
    # module degrades to one unavailable tool instead of an unimportable
    # planner. Same reason `get_regulatory_context` duck-types `ingest/`.
    try:
        from ingest.satellite import verify_construction
    except Exception as exc:  # pragma: no cover - defensive
        raise ToolError(
            f"satellite verification is not available ({exc.__class__.__name__}: {exc}). "
            "Report the construction state as unknown rather than assuming either answer."
        )

    lat, lon = args.get("lat"), args.get("lon")
    if lat is None or lon is None:
        if ctx.location is None:
            raise ToolError(
                "No coordinate. Call resolve_site first, or pass lat and lon explicitly."
            )
        lat, lon = ctx.location.latitude, ctx.location.longitude

    announced_energization = args.get("announced_energization")
    if not announced_energization and getattr(ctx.project, "target_energization", None):
        announced_energization = ctx.project.target_energization.isoformat()

    mireye_facts = {
        key: {
            "value": ctx.facts.fact(key).value,
            "source": ctx.facts.fact(key).source,
            "fetched": ctx.facts.fact(key).fetched,
        }
        for key in _LAND_COVER_KEYS
        if ctx.facts.fact(key) is not None
    }

    # No ctx.spend(): this is public Copernicus imagery over HTTP range reads.
    # It costs no provider credits, which is why it is worth calling on every
    # project that has an announced date.
    verdict = verify_construction(
        float(lat),
        float(lon),
        announced_groundbreaking=args.get("announced_groundbreaking"),
        announced_energization=announced_energization,
        radius_m=float(args.get("radius_m") or 500.0),
        label=(ctx.project.name or ctx.project.address or "site"),
        mireye_facts=mireye_facts or None,
    )

    confidence_note = None
    if ctx.location is not None and ctx.location.confidence is not None:
        if ctx.location.confidence < 0.9:
            confidence_note = (
                f"The site geocoded at {ctx.location.confidence:.2f} confidence. The footprint "
                f"is a circle around that point, so a coarse geocode reads the wrong ground and "
                f"an empty result may only mean the circle is in the wrong place."
            )
    ctx.notes.append(f"satellite: {verdict.headline()}")

    result = verdict.to_dict()
    result["geocode_caveat"] = confidence_note
    result["credits"] = 0
    return result


EXECUTORS: dict[str, Callable[[ToolContext, dict], dict]] = {
    "resolve_site": _exec_resolve_site,
    "get_physical_facts": _exec_get_physical_facts,
    "get_proximity": _exec_get_proximity,
    "get_regulatory_context": _exec_get_regulatory_context,
    "estimate_emissions": _exec_estimate_emissions,
    "determine_pathway": _exec_determine_pathway,
    "test_config": _exec_test_config,
    "price_the_delay": _exec_price_the_delay,
    "search_alternate_sites": _exec_search_alternate_sites,
    "ask_mireye": _exec_ask_mireye,
    "request_field": _exec_request_field,
    "verify_construction": _exec_verify_construction,
}


def run_tool(ctx: ToolContext, name: str, arguments: dict) -> tuple[dict, bool]:
    """Execute one tool. Returns (result, ok).

    Errors come back as a result dict rather than an exception so the model can
    adapt — a refused geocode is information, not a crash.
    """
    started = now_iso()
    if name not in EXECUTORS:
        result = {"error": f"unknown tool {name!r}", "available": list(EXECUTORS)}
        ctx.calls.append(ToolCall(len(ctx.calls) + 1, name, arguments, result, 0, False, started))
        return result, False

    if ctx.calls_remaining <= 0:
        result = {
            "error": "tool call budget exhausted",
            "budget": ctx.budget_line(),
            "guidance": "Write the assessment from what you already have.",
        }
        ctx.calls.append(ToolCall(len(ctx.calls) + 1, name, arguments, result, 0, False, started))
        return result, False

    before = ctx.credits_spent
    try:
        result = EXECUTORS[name](ctx, arguments or {})
        ok = True
    except BudgetExhausted as exc:
        result = {
            "error": "credit budget exhausted",
            "detail": str(exc),
            "budget": ctx.budget_line(),
            "guidance": "Do not retry. Write the assessment from what you already have.",
        }
        ok = False
    except ToolError as exc:
        result = {"error": str(exc)}
        ok = False
    except Exception as exc:  # a provider blowing up should not kill the run
        result = {"error": f"{exc.__class__.__name__}: {exc}"}
        ok = False

    spent = ctx.credits_spent - before
    ctx.calls.append(
        ToolCall(len(ctx.calls) + 1, name, arguments, result, spent, ok, started)
    )
    return result, ok
