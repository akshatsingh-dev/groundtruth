"""Render a ProjectAssessment three ways: terminal, markdown, JSON.

The terminal view is for the demo. The markdown is what a human sends. The JSON
is what a fund's pipeline ingests.

All three carry the same things, in the same order:

- the headline probability, with the model that produced it stated inline
- the pathway and its months range
- every trigger that fired, with its citation
- the alternate site and the delta
- the config alternatives with their honest cost
- a provenance appendix listing every physical fact with source, fetch
  timestamp and confidence

That last section is the one that makes the rest defensible. A permitting
engineer will not act on a number they cannot trace, so an untraceable number
is worthless and the appendix is not optional.

`write_draft` exists because the guardrail says drafts land on disk for a human
to send. Nothing in this module sends, posts or submits anything.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

from .pathway import Pathway, Trigger
from .planner import ProjectAssessment

DRAFTS_DIR = os.path.join("outputs", "drafts")


# --------------------------------------------------------------------------
# Shared shaping
# --------------------------------------------------------------------------


def _probability_band(value: float | None) -> str:
    if value is None:
        return "not stated"
    if value >= 0.7:
        return "likely on schedule"
    if value >= 0.4:
        return "coin flip"
    if value >= 0.15:
        return "unlikely"
    return "very unlikely"


def _pathway_colour(pathway: Pathway) -> str:
    return {
        Pathway.PERMIT_BY_RULE: "green",
        Pathway.MINOR_NSR: "green",
        Pathway.SYNTHETIC_MINOR: "yellow",
        Pathway.MAJOR_PSD: "red",
        Pathway.MAJOR_NA_NSR: "red",
    }[pathway]


def _fired(assessment: ProjectAssessment) -> list[Trigger]:
    return assessment.pathway.fired if assessment.pathway else []


def _provenance_rows(assessment: ProjectAssessment) -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    for key, fact in assessment.facts.facts.items():
        value = f"{fact.value}" + (f" {fact.unit}" if fact.unit else "")
        rows.append(
            (
                key,
                value,
                fact.source or "—",
                fact.fetched or "—",
                f"{fact.confidence:.2f}" if fact.confidence is not None else "—",
            )
        )
    site = assessment.site
    if site:
        for status in site.nonattainment:
            rows.append(
                (
                    f"nonattainment.{status.pollutant}",
                    f"{status.classification} — {status.area_name}",
                    status.source,
                    status.fetched or "—",
                    "—",
                )
            )
    return sorted(rows)


# --------------------------------------------------------------------------
# Terminal
# --------------------------------------------------------------------------


def render_terminal(assessment: ProjectAssessment, console: Any = None) -> None:
    """The demo view. Falls back to plain text when rich is not installed."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except Exception:
        print(render_markdown(assessment))
        return

    console = console or Console()
    project = assessment.project
    prob = assessment.probability
    pathway = assessment.pathway

    console.print()
    console.rule("[bold]Deliverable — project assessment")

    head = Text()
    head.append(f"{project.name or project.address}\n", style="bold")
    head.append(f"{project.config.describe()}\n")
    if project.target_energization:
        head.append(f"Announced energization: {project.target_energization.isoformat()}\n")
    head.append(f"Provider: {assessment.provider_name}   ")
    head.append(f"Run: {assessment.trace.mode}   ")
    head.append(f"{assessment.tool_calls} tool calls, {assessment.credits_spent} credits\n", style="dim")
    console.print(Panel(head, border_style="white", expand=True))

    # Headline.
    if prob.value is None:
        console.print(Panel(Text("No probability stated — see caveats.", style="bold yellow"),
                            border_style="yellow"))
    else:
        colour = "green" if prob.value >= 0.6 else "yellow" if prob.value >= 0.3 else "red"
        headline = Text()
        headline.append(f"{prob.value:.0%}", style=f"bold {colour}")
        headline.append(f"  probability this project energizes on its announced schedule")
        headline.append(f"  ({_probability_band(prob.value)})\n\n", style="dim")
        for line in prob.basis:
            headline.append(f"  {line}\n", style="dim")
        for cap in prob.caps:
            headline.append(f"  {cap}\n", style="bold red")
        headline.append(f"\n  Model: {prob.model}", style="italic dim")
        console.print(Panel(headline, title="Headline", title_align="left", border_style=colour))

    # Pathway.
    if pathway:
        colour = _pathway_colour(pathway.pathway)
        body = Text()
        body.append(f"{pathway.pathway.label}\n", style=f"bold {colour}")
        body.append(
            f"{pathway.months_low:.0f}–{pathway.months_high:.0f} months "
            f"(likely {pathway.months_likely:.0f})\n"
        )
        if pathway.controlling_pollutant:
            body.append(
                f"Controlling: {pathway.controlling_pollutant} at "
                f"{pathway.controlling_tpy:,.0f} tpy against a "
                f"{pathway.applicable_threshold:,.0f} tpy threshold\n"
            )
        body.append(f"\n{pathway.source_category.reasoning}\n", style="dim")
        for stop in pathway.hard_stops:
            body.append(f"\nHARD STOP — {stop}\n", style="bold red")
        console.print(Panel(body, title="Pathway", title_align="left", border_style=colour))

        fired = _fired(assessment)
        if fired:
            table = Table(title="Triggers that fired", title_justify="left", expand=True)
            table.add_column("Trigger", style="bold", no_wrap=True)
            table.add_column("+mo", justify="right", width=5)
            table.add_column("Detail")
            table.add_column("Citation", style="dim")
            for trigger in fired:
                table.add_row(
                    trigger.name.replace("_", " "),
                    f"{trigger.months_added:.0f}" if trigger.months_added else "—",
                    trigger.detail,
                    trigger.citation,
                )
            console.print(table)

    # Emissions.
    if assessment.estimate:
        est = assessment.estimate
        table = Table(title="Potential to emit", title_justify="left")
        table.add_column("Pollutant")
        table.add_column("tpy", justify="right")
        table.add_column("lb/hr", justify="right")
        table.add_column("PSD significance", justify="right", style="dim")
        from .emissions import SIGNIFICANT_EMISSION_RATES

        for pollutant, tpy in sorted(est.tons_per_year.items(), key=lambda kv: -kv[1]):
            ser = SIGNIFICANT_EMISSION_RATES.get(pollutant)
            table.add_row(
                pollutant,
                f"{tpy:,.1f}",
                f"{est.lb_per_hour[pollutant]:,.2f}",
                f"{ser:,.0f}" if ser else "—",
            )
        console.print(table)
        console.print(Text(f"  {est.basis['hours_basis']}", style="dim italic"))
        console.print(Text(f"  {est.basis['emission_factors']}", style="dim italic"))

    # The act — alternate site.
    alt = assessment.alternate
    if alt and alt.best:
        body = Text()
        body.append(f"{alt.delta_statement}\n\n", style="bold green")
        best = alt.best
        body.append(
            f"{best.county} County, {best.state} — {best.pathway.label}, "
            f"{best.months_low:.0f}–{best.months_high:.0f} months\n"
        )
        body.append(
            f"{best.distance_miles:.0f} miles ({best.distance_km:.0f} km) from the announced site\n"
        )
        if best.triggers_cleared:
            body.append(f"Clears: {', '.join(best.triggers_cleared)}\n", style="green")
        if best.triggers_added:
            body.append(f"Adds: {', '.join(best.triggers_added)}\n", style="yellow")
        body.append(
            f"\nScreened {alt.candidates_resolved} of {alt.candidates_considered} candidate "
            f"parcels out to {max(alt.rings_km):.0f} km, {alt.credits_spent} credits.\n",
            style="dim",
        )
        if alt.crossed_state_line:
            body.append("Crosses a state line — different agency, different rules.\n", style="dim")
        elif alt.crossed_county_line:
            body.append("Crosses a county line — same state, different designation.\n", style="dim")
        console.print(Panel(body, title="Alternate site", title_align="left", border_style="green"))
    elif alt:
        console.print(
            Panel(
                Text("\n".join(alt.notes) or "No better parcel found.", style="yellow"),
                title="Alternate site",
                title_align="left",
                border_style="yellow",
            )
        )

    # The act — config search.
    configs = assessment.configs
    if configs and configs.options:
        table = Table(title="Config alternatives at this parcel", title_justify="left", expand=True)
        table.add_column("Change", style="bold")
        table.add_column("Pathway")
        table.add_column("Likely", justify="right", width=7)
        table.add_column("Saves", justify="right", width=7)
        table.add_column("Avail.", justify="right", width=7)
        table.add_column("What it costs")
        for option in configs.options[:6]:
            style = "green" if option.rank_delta > 0 else ("red" if option.rank_delta < 0 else "")
            table.add_row(
                option.label,
                option.pathway.label,
                f"{option.months_likely:.0f} mo",
                f"{option.months_saved:+.0f} mo",
                f"{option.availability:.0%}",
                option.cost_note,
                style=style,
            )
        console.print(table)
        for note in configs.notes:
            console.print(Text(f"  {note}", style="yellow"))

    # Field requests.
    if assessment.field_requests:
        table = Table(title="Field requests to the provider", title_justify="left")
        table.add_column("Field")
        table.add_column("Outcome")
        for record in assessment.field_requests:
            table.add_row(
                record["field_name"],
                str(record.get("outcome") or ("returned" if record.get("supported") else "gap")),
            )
        console.print(table)

    # Narrative.
    if assessment.narrative:
        console.print(
            Panel(Text(assessment.narrative), title="Agent's read", title_align="left",
                  border_style="cyan")
        )

    # Caveats.
    if assessment.caveats:
        body = Text()
        for caveat in assessment.caveats:
            body.append(f"• {caveat}\n")
        console.print(Panel(body, title="What this does not know", title_align="left",
                            border_style="yellow"))

    # Provenance.
    rows = _provenance_rows(assessment)
    table = Table(title="Provenance — every physical fact with its source", title_justify="left",
                  expand=True)
    table.add_column("Field", style="bold", no_wrap=True)
    table.add_column("Value")
    table.add_column("Source")
    table.add_column("Fetched", style="dim")
    table.add_column("Conf.", justify="right", width=6)
    if rows:
        for row in rows:
            table.add_row(*row)
    else:
        table.add_row("—", "no physical facts fetched", assessment.provider_name, "—", "—")
    console.print(table)


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------


def render_markdown(assessment: ProjectAssessment) -> str:
    project = assessment.project
    prob = assessment.probability
    pathway = assessment.pathway
    out: list[str] = []
    add = out.append

    add(f"# {project.name or project.address}")
    add("")
    add(f"{project.config.describe()}")
    add("")
    if prob.value is not None:
        add(f"## {prob.value:.0%} probability of energizing on the announced schedule")
    else:
        add("## No probability stated")
    add("")
    for line in prob.basis:
        add(f"- {line}")
    for cap in prob.caps:
        add(f"- **{cap}**")
    add("")
    add(f"*Model:* {prob.model}")
    add("")

    add("## Pathway")
    add("")
    if pathway:
        add(f"**{pathway.pathway.label}** — {pathway.months_low:.0f}–{pathway.months_high:.0f} "
            f"months, likely {pathway.months_likely:.0f}.")
        add("")
        if pathway.controlling_pollutant:
            add(f"Controlling pollutant: {pathway.controlling_pollutant} at "
                f"{pathway.controlling_tpy:,.0f} tpy against a "
                f"{pathway.applicable_threshold:,.0f} tpy threshold.")
            add("")
        add(f"Source category: {pathway.source_category.reasoning}")
        add("")
        add(f"*{pathway.source_category.citation}*")
        add("")
        for stop in pathway.hard_stops:
            add(f"> **HARD STOP.** {stop}")
            add("")
    else:
        add("No pathway determined. See caveats.")
        add("")

    fired = _fired(assessment)
    if fired:
        add("## Triggers that fired")
        add("")
        add("| Trigger | Months added | Detail | Citation |")
        add("|---|---:|---|---|")
        for trigger in fired:
            detail = trigger.detail.replace("|", "\\|").replace("\n", " ")
            add(f"| {trigger.name.replace('_', ' ')} | "
                f"{trigger.months_added:.0f} | {detail} | {trigger.citation} |")
        add("")

    if assessment.estimate:
        est = assessment.estimate
        add("## Potential to emit")
        add("")
        add("| Pollutant | tpy | lb/hr |")
        add("|---|---:|---:|")
        for pollutant, tpy in sorted(est.tons_per_year.items(), key=lambda kv: -kv[1]):
            add(f"| {pollutant} | {tpy:,.1f} | {est.lb_per_hour[pollutant]:,.2f} |")
        add("")
        add(f"{est.basis['method']}")
        add("")
        add(f"- Heat input: {est.basis['heat_input']}")
        add(f"- Hours: {est.basis['hours_basis']}")
        add(f"- Emission factors: {est.basis['emission_factors']}")
        add(f"- Controls: {est.basis['controls']}")
        add("")

    alt = assessment.alternate
    add("## Alternate site")
    add("")
    if alt and alt.best:
        best = alt.best
        add(f"**{alt.delta_statement}**")
        add("")
        add(f"- {best.county} County, {best.state} at {best.latitude:.4f}, {best.longitude:.4f}")
        add(f"- {best.pathway.label}, {best.months_low:.0f}–{best.months_high:.0f} months")
        add(f"- {best.distance_miles:.0f} miles from the announced site")
        if best.triggers_cleared:
            add(f"- Clears: {', '.join(best.triggers_cleared)}")
        if best.triggers_added:
            add(f"- Adds: {', '.join(best.triggers_added)}")
        add(f"- Screened {alt.candidates_resolved} of {alt.candidates_considered} parcels out to "
            f"{max(alt.rings_km):.0f} km for {alt.credits_spent} credits")
        add("")
    elif alt:
        for note in alt.notes:
            add(f"- {note}")
        add("")
    else:
        add("Not run — see the trace for why.")
        add("")

    configs = assessment.configs
    if configs and configs.options:
        add("## Config alternatives at this parcel")
        add("")
        add("| Change | Pathway | Likely | Months saved | Availability | What it costs |")
        add("|---|---|---:|---:|---:|---|")
        for option in configs.options:
            note = option.cost_note.replace("|", "\\|")
            add(f"| {option.label} | {option.pathway.label} | {option.months_likely:.0f} | "
                f"{option.months_saved:+.0f} | {option.availability:.0%} | {note} |")
        add("")
        for note in configs.notes:
            add(f"> {note}")
            add("")

    if assessment.field_requests:
        add("## Field requests")
        add("")
        for record in assessment.field_requests:
            outcome = record.get("outcome") or ("returned" if record.get("supported") else "gap")
            add(f"- `{record['field_name']}` — {outcome}. {record.get('note', '')}")
        add("")

    if assessment.narrative:
        add("## Agent's read")
        add("")
        add(assessment.narrative)
        add("")

    add("## What this does not know")
    add("")
    for caveat in assessment.caveats:
        add(f"- {caveat}")
    add("")

    add("## Provenance")
    add("")
    add("Every physical fact with its source, fetch timestamp and confidence.")
    add("")
    add("| Field | Value | Source | Fetched | Confidence |")
    add("|---|---|---|---|---:|")
    rows = _provenance_rows(assessment)
    if rows:
        for key, value, source, fetched, confidence in rows:
            add(f"| {key} | {str(value).replace('|', '/')} | {source} | {fetched} | {confidence} |")
    else:
        add(f"| — | no physical facts fetched | {assessment.provider_name} | — | — |")
    add("")
    add(f"*Generated {assessment.generated_at} · {assessment.trace.mode} · "
        f"{assessment.tool_calls} tool calls · {assessment.credits_spent} credits.*")
    add("")
    add("*Screen, not an applicability determination. The agent does not contact agencies, "
        "file anything, or send anything.*")
    return "\n".join(out)


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------


def to_json(assessment: ProjectAssessment, indent: int | None = 2) -> str:
    return json.dumps(assessment.to_dict(), indent=indent, default=str)


def write_json(assessment: ProjectAssessment, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(to_json(assessment))
    return path


def write_markdown(assessment: ProjectAssessment, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(assessment))
    return path


# --------------------------------------------------------------------------
# Drafts
# --------------------------------------------------------------------------


def write_draft(name: str, text: str, directory: str = DRAFTS_DIR) -> str:
    """Write a draft to disk for a human to review and send.

    This is the only "outreach" path in the codebase and it ends at the
    filesystem. There is no mail client, no webhook and no form here, and there
    should never be one — see the guardrail note at the top of planner.py.
    """
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def write_memo_draft(assessment: ProjectAssessment, directory: str = DRAFTS_DIR) -> str:
    """Render the assessment as a memo draft. Unsent, by design."""
    project = assessment.project
    slug = "".join(c if c.isalnum() else "-" for c in (project.name or project.address)).strip("-")
    header = (
        "DRAFT — not sent. Review before this leaves the building.\n"
        "Generated by an agent that does not contact anyone.\n\n"
    )
    return write_draft(f"memo-{slug.lower()[:60]}.md", header + render_markdown(assessment), directory)
