"""County moratorium and zoning posture, read from a hand-entered file.

There is no national database of county data center ordinances. There are
trackers, and they disagree with each other, and they mix city actions with
county actions in the same column. Scraping 3,140 county websites for board
minutes is a week of work and would still be wrong, because the fact you need is
not "does an ordinance exist" but "what did this board do the last three times
someone asked".

So this is 27 counties typed by hand from the linked source, per the build brief.
It covers the counties where something actually happened since 2024, plus a few
permissive ones so the output has a floor as well as a ceiling. Everything else
returns None, and None means no county-level blocker is known, which is not the
same as none exists. `describe()` says that out loud rather than letting an
absence read as an all-clear.

The important distinction the file encodes: a city moratorium is not a county
moratorium. Peculiar deleting "data center" from its zoning code does not bind
the rest of Cass County, and Fayetteville's UDO amendment does not bind
unincorporated Fayette County. Those records carry moratorium=False with the
municipal action described in the note, because applying a city ordinance to a
whole county produces a wrong answer for most of the county's land.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "counties.json"

VALID_POSTURES = ("by-right", "special-exception", "hostile")


@dataclass(frozen=True)
class CountyRecord:
    fips: str
    county: str
    state: str
    moratorium: bool
    moratorium_note: str
    zoning_posture: str
    board_history: str
    source_url: str
    source_name: str
    entered: str
    confidence: str

    def describe(self) -> str:
        posture = {
            "by-right": "permissive",
            "special-exception": "discretionary approval required",
            "hostile": "has denied or heavily conditioned recent applications",
        }.get(self.zoning_posture, self.zoning_posture)
        head = f"{self.county} County, {self.state}: {posture}"
        if self.moratorium:
            head = f"{self.county} County, {self.state}: MORATORIUM in effect, {posture}"
        return f"{head}. {self.moratorium_note} Source: {self.source_name}, {self.source_url}"


class CountyFileError(RuntimeError):
    pass


def _validate(record: dict) -> None:
    missing = {
        "fips", "county", "state", "moratorium", "moratorium_note",
        "zoning_posture", "board_history", "source_url", "source_name",
        "entered", "confidence",
    } - set(record)
    if missing:
        raise CountyFileError(f"{record.get('fips', '?')} is missing {sorted(missing)}")
    if len(record["fips"]) != 5 or not record["fips"].isdigit():
        raise CountyFileError(f"{record['fips']!r} is not a 5-digit county FIPS")
    if record["zoning_posture"] not in VALID_POSTURES:
        raise CountyFileError(
            f"{record['fips']} has zoning_posture {record['zoning_posture']!r}; "
            f"agent.pathway only reads {VALID_POSTURES}"
        )
    if record["confidence"] not in ("high", "medium"):
        raise CountyFileError(f"{record['fips']} has confidence {record['confidence']!r}")
    if not record["source_url"].startswith("http"):
        raise CountyFileError(f"{record['fips']} has no usable source_url")


_cache: dict[str, dict] | None = None


def load() -> dict[str, dict]:
    """Every hand-entered county, keyed by 5-digit FIPS.

    Returns the raw records rather than dataclasses. Two reasons: it is the shape
    of the file a human edits, and sweep/counties.py reads these structurally by
    key to build its own (state, county-name) index. `records()` gives the typed
    view for code that wants attributes.

    Validates on load. A record that fails validation is a typo in a file a human
    edits, and failing loudly beats a silently missing moratorium.
    """
    global _cache
    if _cache is not None:
        return _cache

    payload = json.loads(DATA_PATH.read_text())
    rows: dict[str, dict] = {}
    for row in payload["records"]:
        _validate(row)
        if row["fips"] in rows:
            raise CountyFileError(f"duplicate FIPS {row['fips']} in counties.json")
        rows[row["fips"]] = dict(row)
    _cache = rows
    return rows


def records() -> dict[str, CountyRecord]:
    """The same records, typed."""
    return {fips: CountyRecord(**row) for fips, row in load().items()}


def for_fips(fips: str) -> CountyRecord | None:
    """One county, or None if it is not in the file.

    None means no county-level blocker is known. It does not mean there is none.
    Roughly 3,100 US counties are not in this file.
    """
    row = load().get(str(fips).zfill(5))
    return CountyRecord(**row) if row else None


def apply_to(site, fips: str | None = None) -> object:
    """Populate the county fields on a pathway.SiteContext in place.

    Kept here rather than in pathway.py so the decision engine stays free of file
    IO. Records provenance under site.provenance["county_posture"] so the output
    can cite the board minute or the news story a human can click.
    """
    record = for_fips(fips or site.county_fips or "")
    if record is None:
        site.provenance["county_posture"] = {
            "source": "ingest/counties.json",
            "value": None,
            "note": "County not in the hand-entered file. No county-level blocker "
            "is known, which is an absence of evidence, not evidence of absence.",
        }
        return site

    site.moratorium = record.moratorium
    site.moratorium_note = record.moratorium_note
    site.zoning_posture = record.zoning_posture
    site.provenance["county_posture"] = {
        "source": record.source_name,
        "source_url": record.source_url,
        "fetched": record.entered,
        "confidence": record.confidence,
        "board_history": record.board_history,
    }
    return site


def moratorium_counties() -> list[CountyRecord]:
    return [r for r in records().values() if r.moratorium]


if __name__ == "__main__":  # pragma: no cover
    entered = records()
    active = moratorium_counties()
    print(f"{len(entered)} counties entered, {len(active)} with a moratorium in effect")
    for posture in VALID_POSTURES:
        count = sum(1 for r in entered.values() if r.zoning_posture == posture)
        print(f"  {posture:18s} {count}")
    high = sum(1 for r in entered.values() if r.confidence == "high")
    print(f"  confidence high    {high}, medium {len(entered) - high}")
    print()
    for record in sorted(active, key=lambda r: (r.state, r.county)):
        print(f"  {record.fips}  {record.county}, {record.state}")
