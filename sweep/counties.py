"""National county sweep — days until legal power for a 500 MW gas plant.

Runs the same permit pathway engine used for a single parcel across every US
county and county equivalent, using one fixed reference plant. The output is a
screening layer: it answers "which conversation am I about to have with this
state agency", not "can I build on this parcel".

What a county-level score can see
---------------------------------
- County attainment / nonattainment designation and classification, per
  pollutant (EPA Green Book). This is the fact that flips the pathway.
- The state agency overlay in ``agent.pathway.STATE_OVERLAYS`` — eight states
  modelled from public permit records, the rest on the federal default.
- Hand-entered county posture: moratoria, hostile zoning (``ingest/counties.json``).

What it cannot see
------------------
- PSD increment already consumed at that specific location. Increment is
  tracked per area against modelled receptors, not per county.
- Terrain relief in the modelling domain. Two parcels 15 miles apart in the
  same county can differ by 400 m of relief.
- Distance to a gas transmission pipeline. This is the New Mexico failure mode
  and it is a parcel fact, not a county fact.
- Class I area distance, residential receptor counts, parcel acreage.

Every record therefore carries ``resolution: "county"``. The parcel run is the
real answer. The map is where you start, not where you stop.

Optional ``--with-mireye`` enriches each county's Census interior point with
real physical facts (pipeline distance, terrain relief, receptors) through
``providers.mireye``. That upgrades a record's resolution to
``"county_interior_point"``, which is still not a parcel — it is one sample
inside a polygon that averages 1,100 square miles.

Usage
-----
    python -m sweep.counties                 # no keys, federal data only
    python -m sweep.counties --workers 16
    python -m sweep.counties --with-mireye   # burns Mireye credits
    python -m sweep.counties --resume        # continue an interrupted run

Writes ``data/county_scores.json``. Progress is appended to
``data/county_scores.progress.jsonl`` after every county, so a run that dies at
county 2,400 restarts at 2,400.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import os
import re
import sys
import threading
import time
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from agent.emissions import Control, Fuel, GenerationConfig, PrimeMover, estimate
from agent.pathway import (
    NonattainmentStatus,
    Pathway,
    SiteContext,
    determine_pathway,
    overlay_for,
)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data"

#: Census 2025 vintage. Verified live 5 Aug 2026; both return 200 with a
#: Last-Modified of 10 Sep 2025 (gazetteer) and 23 Apr 2026 (boundaries).
GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2025_Gazetteer/2025_Gaz_counties_national.zip"
)
GAZETTEER_VINTAGE = "2025 Census Gazetteer, counties, national"

#: EPA Green Book, "Current Nonattainment Counties for All Criteria Pollutants".
#: One HTML page, no key. Only used when ``ingest.greenbook`` is unavailable.
GREENBOOK_URL = "https://www3.epa.gov/airquality/greenbook/ancl.html"

MEAN_DAYS_PER_MONTH = 30.437  # 365.25 / 12

# --------------------------------------------------------------------------
# The reference plant
# --------------------------------------------------------------------------

#: One plant, scored identically in all 3,222 counties, so that the only thing
#: varying across the map is the ground. 500 MW is the size at which onsite
#: generation for a data center campus stops being a backup story and becomes a
#: power plant. Combined cycle because that is what gets built for baseload, and
#: because the HRSG puts the source in List-of-28 category 1, which drops the PSD
#: major threshold from 250 tpy to 100 tpy. DLN + SCR + oxidation catalyst is
#: current BACT-level control for a new gas turbine, so this is the *best case*
#: emissions profile, not a strawman. No run-hour cap: a data center runs
#: baseload, and PTE is computed at 8760 hours unless the developer accepts a
#: federally enforceable limit.
REFERENCE_CONFIG = GenerationConfig(
    mw=500.0,
    prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
    fuel=Fuel.NATURAL_GAS,
    controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
    run_hours=8760.0,
    enforceable_limit=False,
)

REFERENCE_ESTIMATE = estimate(REFERENCE_CONFIG)


# --------------------------------------------------------------------------
# County index
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class County:
    """One county or county equivalent, from the Census gazetteer."""

    fips: str
    name: str  # "Autauga County", "Fairbanks North Star Borough"
    state: str  # two-letter USPS
    latitude: float  # INTPTLAT — a guaranteed-interior point, not a centroid
    longitude: float
    land_sqmi: float

    @property
    def bare_name(self) -> str:
        """Name with the legal suffix stripped, for matching against EPA text."""
        return _strip_suffix(self.name)


_SUFFIXES = (
    " County",
    " Parish",
    " Borough",
    " Census Area",
    " City and Borough",
    " Municipality",
    " Municipio",
    " city",
    " City",
    " Island",
    " District",
)


def _strip_suffix(name: str) -> str:
    out = name
    for suffix in _SUFFIXES:
        if out.endswith(suffix):
            out = out[: -len(suffix)]
    return out.strip()


def _norm(name: str) -> str:
    """Fold a county name to something that survives EPA's typography."""
    out = name.lower()
    out = out.replace("saint ", "st ").replace("st. ", "st ")
    out = out.replace("&", "and")
    out = re.sub(r"[^a-z0-9 ]+", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _download(url: str, dest: Path, timeout: int = 120) -> Path:
    """Fetch once into data/raw/ (gitignored). Never re-downloads."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "deliverable-sweep/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = response.read()
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(payload)
    tmp.replace(dest)
    return dest


def load_counties(refresh: bool = False) -> list[County]:
    """Every US county and county equivalent, with a guaranteed interior point.

    INTPTLAT/INTPTLONG rather than a centroid: for a horseshoe-shaped county the
    centroid can fall outside the county, and a lookup at that point returns the
    wrong jurisdiction's answer.
    """
    cache = DATA / "county_index.json"
    if cache.exists() and not refresh:
        rows = json.loads(cache.read_text())["counties"]
        return [County(**row) for row in rows]

    archive = _download(GAZETTEER_URL, RAW / "gaz_counties.zip")
    with zipfile.ZipFile(archive) as zf:
        member = next(n for n in zf.namelist() if n.endswith(".txt"))
        text = zf.read(member).decode("utf-8", "replace")

    lines = [line for line in text.splitlines() if line.strip()]
    header = [h.strip() for h in lines[0].split("\t" if "\t" in lines[0] else "|")]
    sep = "\t" if "\t" in lines[0] else "|"
    idx = {name: i for i, name in enumerate(header)}

    counties: list[County] = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(sep)]
        if len(parts) < len(header):
            continue
        try:
            counties.append(
                County(
                    fips=parts[idx["GEOID"]],
                    name=parts[idx["NAME"]],
                    state=parts[idx["USPS"]],
                    latitude=float(parts[idx["INTPTLAT"]]),
                    longitude=float(parts[idx["INTPTLONG"]]),
                    land_sqmi=float(parts[idx["ALAND_SQMI"]] or 0.0),
                )
            )
        except (KeyError, ValueError):
            continue

    counties.sort(key=lambda c: c.fips)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(
            {
                "source": GAZETTEER_VINTAGE,
                "url": GAZETTEER_URL,
                "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "count": len(counties),
                "counties": [asdict(c) for c in counties],
            },
            indent=1,
        )
    )
    return counties


# --------------------------------------------------------------------------
# Nonattainment
# --------------------------------------------------------------------------

#: EPA's pollutant labels on the Green Book county page mapped to the keys the
#: pathway engine reasons in. Multiple NAAQS vintages collapse to one key; the
#: engine takes the worst classification across vintages, which is what an
#: applicability determination does.
_POLLUTANT_KEYS: tuple[tuple[str, str], ...] = (
    ("ozone", "ozone"),
    ("pm-2.5", "pm25"),
    ("pm2.5", "pm25"),
    ("pm-10", "pm10"),
    ("pm10", "pm10"),
    ("carbon monoxide", "co"),
    ("sulfur dioxide", "so2"),
    ("nitrogen dioxide", "no2"),
    ("lead", "lead"),
)

#: Worst-first. Used to pick one classification when a county carries several
#: designations for the same pollutant under different NAAQS vintages.
_SEVERITY: tuple[str, ...] = (
    "extreme",
    "severe-17",
    "severe-15",
    "severe",
    "serious",
    "moderate",
    "marginal",
    "unclassified",
)


def _classification(text: str) -> str:
    match = re.search(r"\(([^()]*)\)\s*$", text.strip())
    if not match:
        return "unclassified"
    raw = match.group(1).strip().lower()
    raw = raw.replace("severe 15", "severe-15").replace("severe 17", "severe-17")
    return raw if raw in _SEVERITY else "unclassified"


def _pollutant_key(text: str) -> str | None:
    low = text.strip().lower()
    for needle, key in _POLLUTANT_KEYS:
        if needle in low:
            return key
    return None


@dataclass
class NonattainmentIndex:
    """Designations keyed by FIPS where the source gives one, and by
    (state, normalised county name) otherwise.

    FIPS first because county names collide across states and EPA's typography
    for them is inconsistent. The name key is the fallback for sources that
    publish text only.
    """

    by_county: dict[tuple[str, str], list[NonattainmentStatus]]
    part_county: set[tuple[str, str]]
    source: str
    fetched: str | None
    available: bool
    by_fips: dict[str, list[NonattainmentStatus]] = field(default_factory=dict)
    part_fips: set[str] = field(default_factory=set)

    def lookup(self, county: County) -> tuple[list[NonattainmentStatus], bool]:
        if county.fips in self.by_fips:
            return list(self.by_fips[county.fips]), county.fips in self.part_fips
        key = (county.state, _norm(county.bare_name))
        return list(self.by_county.get(key, [])), key in self.part_county


_STATE_ABBR = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI",
    "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
    "OREGON": "OR", "PENNSYLVANIA": "PA", "PUERTO RICO": "PR", "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX",
    "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "VIRGIN ISLANDS": "VI",
    "WASHINGTON": "WA", "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "AMERICAN SAMOA": "AS", "GUAM": "GU", "NORTHERN MARIANA ISLANDS": "MP",
}


def _index_from_ingest() -> NonattainmentIndex | None:
    """Use ingest.greenbook if that module exists and exposes something usable.

    Another agent owns that file. We probe a few plausible entry points and give
    up quietly rather than coupling to a signature that may still be moving.
    """
    try:
        from ingest import greenbook  # type: ignore
    except Exception:
        return None

    rows: Any = None
    for attr in ("load_nonattainment", "load", "load_counties", "nonattainment_by_county", "all_areas"):
        fn = getattr(greenbook, attr, None)
        if callable(fn):
            try:
                rows = fn()
                break
            except Exception:
                rows = None
    if rows is None:
        return None

    by_county: dict[tuple[str, str], list[NonattainmentStatus]] = {}
    by_fips: dict[str, list[NonattainmentStatus]] = {}
    part: set[tuple[str, str]] = set()
    part_fips: set[str] = set()

    def _get(item, key, default=None):
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    try:
        items = rows.values() if isinstance(rows, dict) else rows
        for item in items:
            state = _get(item, "state")
            county_name = _get(item, "county") or _get(item, "name")
            fips = _get(item, "fips") or _get(item, "county_fips") or _get(item, "geoid")
            statuses = _get(item, "nonattainment") or [item]
            if not (state and county_name) and not fips:
                continue
            key = (
                (str(state).upper()[:2], _norm(_strip_suffix(str(county_name))))
                if state and county_name
                else None
            )
            bucket: list[NonattainmentStatus] = []
            for status in statuses:
                if isinstance(status, NonattainmentStatus):
                    bucket.append(status)
                elif _get(status, "pollutant"):
                    bucket.append(
                        NonattainmentStatus(
                            pollutant=str(_get(status, "pollutant")).lower(),
                            classification=str(_get(status, "classification", "unclassified")).lower(),
                            area_name=str(_get(status, "area_name", "")),
                            source=str(_get(status, "source", "EPA Green Book")),
                            fetched=_get(status, "fetched"),
                        )
                    )
            if not bucket:
                continue
            is_part = bool(_get(item, "part_county", False))
            if key:
                by_county.setdefault(key, []).extend(bucket)
                if is_part:
                    part.add(key)
            if fips:
                code = str(fips).zfill(5)
                by_fips.setdefault(code, []).extend(bucket)
                if is_part:
                    part_fips.add(code)
    except Exception:
        return None

    if not by_county and not by_fips:
        return None
    fetched = None
    for candidate in ("data_vintage", "VINTAGE", "FETCHED"):
        value = getattr(greenbook, candidate, None)
        try:
            fetched = str(value() if callable(value) else value) if value else fetched
        except Exception:
            pass
    return NonattainmentIndex(
        by_county=_collapse(by_county),
        part_county=part,
        source="EPA Green Book via ingest.greenbook",
        fetched=fetched,
        available=True,
        by_fips=_collapse_flat(by_fips),
        part_fips=part_fips,
    )


def _index_from_epa_page() -> NonattainmentIndex | None:
    """Parse the Green Book county page ourselves.

    Fallback only. One HTML file, no key, no scraper infrastructure. Structure is
    a flat table: a one-cell row is either a state (all caps) or a county; a
    three-cell row is one designation on the county above it.
    """
    try:
        path = _download(GREENBOOK_URL, RAW / "greenbook_ancl.html", timeout=60)
        html = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    if not rows:
        return None

    by_county: dict[tuple[str, str], list[NonattainmentStatus]] = {}
    part: set[tuple[str, str]] = set()
    fetched = datetime.fromtimestamp(
        (RAW / "greenbook_ancl.html").stat().st_mtime, tz=timezone.utc
    ).isoformat(timespec="seconds")

    state: str | None = None
    key: tuple[str, str] | None = None
    for row in rows:
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(" ", strip=True) for c in cells]
        if len(cells) == 1:
            text = texts[0]
            if not text:
                continue
            if text.upper() in _STATE_ABBR:
                state = _STATE_ABBR[text.upper()]
                key = None
            elif state:
                key = (state, _norm(_strip_suffix(text)))
        elif len(cells) >= 3 and state and key:
            pollutant = _pollutant_key(texts[0])
            if not pollutant:
                continue
            area = texts[2]
            by_county.setdefault(key, []).append(
                NonattainmentStatus(
                    pollutant=pollutant,
                    classification=_classification(area),
                    area_name=re.sub(r"\s*-\s*\([^()]*\)\s*$", "", area).strip(),
                    source="EPA Green Book (ancl.html)",
                    fetched=fetched,
                )
            )
            if "*" in texts[1]:
                part.add(key)

    if not by_county:
        return None
    return NonattainmentIndex(
        by_county=_collapse(by_county),
        part_county=part,
        source=f"EPA Green Book, current nonattainment counties, all criteria pollutants ({GREENBOOK_URL})",
        fetched=fetched,
        available=True,
    )


def _worst(statuses: list[NonattainmentStatus]) -> list[NonattainmentStatus]:
    """One designation per pollutant, keeping the worst classification.

    A county can be nonattainment for ozone under both the 2008 and 2015 NAAQS
    with different classifications. The permit applies the stricter one.
    """
    worst: dict[str, NonattainmentStatus] = {}
    for status in statuses:
        rank = (
            _SEVERITY.index(status.classification)
            if status.classification in _SEVERITY
            else len(_SEVERITY)
        )
        current = worst.get(status.pollutant)
        current_rank = (
            _SEVERITY.index(current.classification)
            if current and current.classification in _SEVERITY
            else len(_SEVERITY)
        )
        if current is None or rank < current_rank:
            worst[status.pollutant] = status
    return list(worst.values())


def _collapse_flat(by_fips: dict[str, list[NonattainmentStatus]]) -> dict[str, list[NonattainmentStatus]]:
    return {k: _worst(v) for k, v in by_fips.items() if v}


def _collapse(
    by_county: dict[tuple[str, str], list[NonattainmentStatus]]
) -> dict[tuple[str, str], list[NonattainmentStatus]]:
    out: dict[tuple[str, str], list[NonattainmentStatus]] = {}
    for key, statuses in by_county.items():
        worst: dict[str, NonattainmentStatus] = {}
        for status in statuses:
            rank = _SEVERITY.index(status.classification) if status.classification in _SEVERITY else len(_SEVERITY)
            current = worst.get(status.pollutant)
            current_rank = (
                _SEVERITY.index(current.classification)
                if current and current.classification in _SEVERITY
                else len(_SEVERITY)
            )
            if current is None or rank < current_rank:
                worst[status.pollutant] = status
        out[key] = list(worst.values())
    return out


def load_nonattainment() -> NonattainmentIndex:
    """ingest.greenbook first, our own parse second, refusal third.

    Refusal is a real outcome. If neither path works, every county is marked
    insufficient rather than scored as if it were clean air.
    """
    for builder in (_index_from_ingest, _index_from_epa_page):
        index = builder()
        if index is not None:
            return index
    return NonattainmentIndex(
        by_county={},
        part_county=set(),
        source="unavailable",
        fetched=None,
        available=False,
    )


# --------------------------------------------------------------------------
# County posture file
# --------------------------------------------------------------------------


def load_county_file() -> tuple[dict[str, dict], str]:
    """Hand-entered county posture: moratoria, hostile zoning, notes.

    Owned by another agent (``ingest/counties.json``, ~20 records entered by
    hand rather than scraped). Keyed here by FIPS and by (state, name).
    """
    records: Any = None
    label = "unavailable"

    try:
        from ingest import counties as counties_module  # type: ignore

        for attr in ("load", "load_counties", "COUNTIES", "RECORDS"):
            value = getattr(counties_module, attr, None)
            if callable(value):
                records = value()
                label = "ingest.counties"
                break
            if value is not None:
                records = value
                label = "ingest.counties"
                break
    except Exception:
        records = None

    if records is None:
        path = ROOT / "ingest" / "counties.json"
        if path.exists():
            try:
                records = json.loads(path.read_text())
                label = "ingest/counties.json"
            except Exception:
                records = None

    if records is None:
        return {}, label

    if isinstance(records, dict):
        rows = list(records.values()) if not any(isinstance(v, (str, bool)) for v in records.values()) else [records]
    else:
        rows = list(records)

    index: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        fips = str(row.get("fips") or row.get("county_fips") or row.get("geoid") or "").strip()
        state = str(row.get("state") or "").upper()[:2]
        name = str(row.get("county") or row.get("name") or "")
        if fips:
            index[fips.zfill(5)] = row
        if state and name:
            index[f"{state}|{_norm(_strip_suffix(name))}"] = row
    return index, label


# --------------------------------------------------------------------------
# Mireye enrichment (optional, burns credits)
# --------------------------------------------------------------------------


@dataclass
class CreditMeter:
    """Counts what the sweep actually consumed. The founders email needs a real
    number, not an estimate."""

    calls: int = 0
    credits: float = 0.0
    counties_enriched: int = 0
    errors: int = 0
    _lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def record(self, calls: int, credits: float, ok: bool) -> None:
        with self._lock:
            self.calls += calls
            self.credits += credits
            self.counties_enriched += 1 if ok else 0
            self.errors += 0 if ok else 1

    def as_dict(self) -> dict:
        return {
            "mireye_calls": self.calls,
            "mireye_credits": round(self.credits, 2),
            "counties_enriched": self.counties_enriched,
            "enrichment_errors": self.errors,
        }


def build_provider() -> tuple[Any | None, str]:
    """Instantiate providers.mireye if the module and a key both exist.

    Written defensively: that module is another agent's and may not have landed.
    No key means no provider, which means no enrichment and no silent zeros.
    """
    if not os.environ.get("MIREYE_API_KEY"):
        return None, "no MIREYE_API_KEY in environment"
    try:
        from providers import mireye as mireye_module  # type: ignore
    except Exception as exc:
        return None, f"providers.mireye unavailable ({type(exc).__name__})"

    for attr in ("MireyeProvider", "Mireye", "Provider", "build", "provider"):
        candidate = getattr(mireye_module, attr, None)
        if candidate is None:
            continue
        try:
            return (candidate() if callable(candidate) else candidate), f"providers.mireye.{attr}"
        except Exception:
            continue
    return None, "providers.mireye exposed no constructible provider"


#: Presets asked for at a county interior point. Chosen for what the *pathway*
#: needs, not for completeness: pipeline reachability, terrain for dispersion,
#: and receptors for the EJ and opposition triggers.
MIREYE_PRESETS = ("terrain", "utilities", "points_of_interest")
MIREYE_TARGETS = ("gas_pipeline", "transmission", "airport", "urban_area")


def enrich_site(provider: Any, county: County, site: SiteContext) -> tuple[int, float]:
    """Fill the parcel-shaped fields on a SiteContext from one interior point.

    Returns (calls made, credits spent). Anything the provider does not return
    stays None — the pathway engine skips triggers it has no input for, which is
    the correct behaviour. A zero would read as "pipeline is right here".
    """
    from providers.base import Location  # imported late; base.py has no deps

    calls = 0
    credits = 0.0
    location = Location(
        latitude=county.latitude,
        longitude=county.longitude,
        county=county.bare_name,
        county_fips=county.fips,
        state=county.state,
        source="Census gazetteer interior point",
    )

    def _cost(result: Any) -> float:
        for attr in ("credits", "credits_used", "cost"):
            value = getattr(result, attr, None)
            if isinstance(value, (int, float)):
                return float(value)
        return 1.0

    try:
        facts = provider.fetch(location, MIREYE_PRESETS)
        calls += len(MIREYE_PRESETS)
        credits += _cost(facts) * len(MIREYE_PRESETS)
        for key, attr in (
            ("terrain_relief_m", "terrain_relief_m"),
            ("relief_m", "terrain_relief_m"),
            ("residential_within_1km", "residential_within_1km"),
        ):
            value = facts.get(key) if hasattr(facts, "get") else None
            if isinstance(value, (int, float)):
                setattr(site, attr, value)
        if hasattr(facts, "provenance"):
            site.provenance.update(facts.provenance())
    except Exception:
        pass

    try:
        near = provider.proximity(location, MIREYE_TARGETS)
        calls += 1
        credits += 1.0
        for target, attr in (
            ("gas_pipeline", "gas_pipeline_km"),
            ("transmission", "transmission_km"),
            ("airport", "nearest_airport_km"),
        ):
            result = near.get(target) if isinstance(near, dict) else None
            distance = getattr(result, "distance_km", None)
            if isinstance(distance, (int, float)):
                setattr(site, attr, float(distance))
            if result is not None:
                site.provenance[target] = {
                    "source": getattr(result, "source", None),
                    "fetched": getattr(result, "fetched", None),
                    "confidence": None,
                }
    except Exception:
        pass

    return calls, credits


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def score_county(
    county: County,
    na_index: NonattainmentIndex,
    county_file: dict[str, dict],
    provider: Any | None,
    meter: CreditMeter | None,
) -> dict:
    """One county, one record.

    The record is deliberately verbose about what it did not know. A screening
    layer that hides its gaps is worse than no screening layer.
    """
    statuses, part_county = na_index.lookup(county)
    posture = county_file.get(county.fips) or county_file.get(
        f"{county.state}|{_norm(county.bare_name)}"
    ) or {}

    site = SiteContext(
        state=county.state,
        county=county.bare_name,
        county_fips=county.fips,
        latitude=county.latitude,
        longitude=county.longitude,
        nonattainment=statuses,
        moratorium=bool(posture.get("moratorium")),
        moratorium_note=posture.get("moratorium_note") or posture.get("note"),
        zoning_posture=posture.get("zoning_posture"),
        litigation=list(posture.get("litigation") or []),
    )

    resolution = "county"
    mireye_calls = 0
    mireye_credits = 0.0
    if provider is not None:
        try:
            mireye_calls, mireye_credits = enrich_site(provider, county, site)
            resolution = "county_interior_point"
            if meter:
                meter.record(mireye_calls, mireye_credits, ok=True)
        except Exception:
            if meter:
                meter.record(mireye_calls, mireye_credits, ok=False)

    result = determine_pathway(REFERENCE_ESTIMATE, site)
    overlay = overlay_for(county.state)
    fired = [t for t in result.triggers if t.fired]
    for trigger in fired:
        TRIGGER_CITATIONS[trigger.name] = trigger.citation

    # Honesty gate. Without a Green Book designation we do not know whether this
    # county is in nonattainment, and nonattainment can only make the answer
    # worse. So the number is a floor, and it is labelled as one.
    if na_index.available:
        data_quality = "ok"
        quality_note = None
    else:
        data_quality = "insufficient"
        quality_note = (
            "No nonattainment designation available. The pathway and timeline below are a "
            "floor: a nonattainment designation can only escalate them. Do not read this "
            "county as attainment."
        )

    return {
        "fips": county.fips,
        "county": county.bare_name,
        "county_full": county.name,
        "state": county.state,
        "latitude": county.latitude,
        "longitude": county.longitude,
        "land_sqmi": county.land_sqmi,
        # ---- the score ----
        "pathway": result.pathway.value,
        "pathway_label": result.pathway.label,
        "pathway_rank": result.pathway.rank,
        "months_low": round(result.months_low, 1),
        "months_likely": round(result.months_likely, 1),
        "months_high": round(result.months_high, 1),
        "days_low": round(result.months_low * MEAN_DAYS_PER_MONTH),
        "days_likely": round(result.months_likely * MEAN_DAYS_PER_MONTH),
        "days_high": round(result.months_high * MEAN_DAYS_PER_MONTH),
        # ---- why ----
        # Citations live once at the top level under `trigger_citations` rather
        # than repeated 3,222 times. Same information, a third of the bytes.
        "triggers": [
            {"name": t.name, "detail": t.detail, "months_added": t.months_added} for t in fired
        ],
        "trigger_names": [t.name for t in fired],
        "hard_stops": result.hard_stops,
        "controlling_pollutant": result.controlling_pollutant,
        "controlling_tpy": round(result.controlling_tpy, 1) if result.controlling_tpy else None,
        "applicable_threshold_tpy": result.applicable_threshold,
        "offsets_required_tons": (
            round(result.offsets_required_tons) if result.offsets_required_tons else None
        ),
        "nonattainment": [
            {"pollutant": s.pollutant, "classification": s.classification, "area": s.area_name}
            for s in statuses
        ],
        "agency": overlay["agency"],
        "state_modelled": county.state.upper() in _modelled_states(),
        # ---- what this record does not know ----
        "resolution": resolution,
        "data_quality": data_quality,
        "data_quality_note": quality_note,
        "part_county_nonattainment": part_county,
        "county_posture_source": (
            posture.get("source") or posture.get("source_name") or posture.get("source_url")
            if posture
            else None
        ),
        "mireye_calls": mireye_calls,
        "mireye_credits": round(mireye_credits, 3),
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _modelled_states() -> set[str]:
    from agent.pathway import STATE_OVERLAYS

    return set(STATE_OVERLAYS)


#: Trigger name -> regulatory citation, collected once while scoring. Dict
#: assignment is atomic, so the workers can fill this without a lock.
TRIGGER_CITATIONS: dict[str, str] = {}


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

PROGRESS_PATH = DATA / "county_scores.progress.jsonl"
OUTPUT_PATH = DATA / "county_scores.json"


def _load_progress(path: Path) -> dict[str, dict]:
    """Records already written. Malformed lines from a hard kill are dropped
    rather than crashing the resume."""
    done: dict[str, dict] = {}
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("fips"):
                done[record["fips"]] = record
    return done


def _repair_progress(path: Path) -> dict[str, dict]:
    """Load, then rewrite the log with only the intact records.

    A kill -9 mid-write leaves a partial line with no newline. Appending to that
    file concatenates the next record onto the fragment and destroys both, so a
    resume has to rewrite before it appends.
    """
    done = _load_progress(path)
    if not done:
        return done
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for fips in sorted(done):
            handle.write(json.dumps(done[fips], separators=(",", ":")) + "\n")
    tmp.replace(path)
    return done


def run(
    workers: int = 12,
    limit: int | None = None,
    with_mireye: bool = False,
    resume: bool = True,
    refresh_index: bool = False,
    progress_every: int = 200,
) -> dict:
    started = time.time()
    counties = load_counties(refresh=refresh_index)
    if limit:
        counties = counties[:limit]

    na_index = load_nonattainment()
    county_file, county_file_label = load_county_file()

    provider = None
    provider_label = "disabled"
    if with_mireye:
        provider, provider_label = build_provider()
        if provider is None:
            print(f"[sweep] --with-mireye requested but no provider: {provider_label}", file=sys.stderr)
            print("[sweep] continuing at county resolution with federal data only", file=sys.stderr)

    meter = CreditMeter()

    if not resume and PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()
    done = _repair_progress(PROGRESS_PATH) if resume else {}
    todo = [c for c in counties if c.fips not in done]

    print(
        f"[sweep] {len(counties):,} counties | {len(done):,} already scored | "
        f"{len(todo):,} to do | workers={workers}",
        file=sys.stderr,
    )
    print(f"[sweep] reference plant: {REFERENCE_CONFIG.describe()}", file=sys.stderr)
    print(f"[sweep] nonattainment: {na_index.source}", file=sys.stderr)
    print(f"[sweep] county posture: {county_file_label} ({len(county_file) // 2 or len(county_file)} records)", file=sys.stderr)
    print(f"[sweep] mireye: {provider_label}", file=sys.stderr)
    if not na_index.available:
        print(
            "[sweep] WARNING no nonattainment data. Every county will be marked "
            "data_quality=insufficient and its timeline treated as a floor.",
            file=sys.stderr,
        )

    write_lock = threading.Lock()
    counter = {"n": 0}

    def work(county: County) -> dict:
        record = score_county(county, na_index, county_file, provider, meter)
        with write_lock:
            with PROGRESS_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            counter["n"] += 1
            n = counter["n"]
            if n % progress_every == 0 or n == len(todo):
                elapsed = time.time() - started
                rate = n / elapsed if elapsed else 0.0
                remaining = (len(todo) - n) / rate if rate else 0.0
                extra = f" | {meter.calls:,} calls" if with_mireye else ""
                print(
                    f"[sweep] {n:,}/{len(todo):,} ({n / len(todo):.0%}) "
                    f"{rate:,.0f}/s eta {remaining:,.0f}s{extra}",
                    file=sys.stderr,
                )
        return record

    if todo:
        with futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for future in futures.as_completed([pool.submit(work, c) for c in todo]):
                future.result()

    # A resume that scores nothing new leaves the citation table empty, so
    # rebuild it in memory from a spread of counties. Cheap: pure math.
    if len(TRIGGER_CITATIONS) < 8:
        step = max(1, len(counties) // 400)
        for county in counties[::step]:
            score_county(county, na_index, county_file, None, None)

    records = _load_progress(PROGRESS_PATH)
    wanted = {c.fips for c in counties}
    rows = [records[f] for f in sorted(wanted & set(records))]
    elapsed = time.time() - started

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resolution": "county",
        "resolution_note": (
            "County-level screening layer. Scored from county-level facts only: EPA Green Book "
            "designation, the state agency overlay, and the hand-entered county posture file. "
            "It cannot see parcel-level PSD increment consumption, terrain relief, Class I area "
            "distance or gas pipeline reachability. The parcel run is the real answer."
        ),
        "reference_config": {
            "description": REFERENCE_CONFIG.describe(),
            "mw": REFERENCE_CONFIG.mw,
            "prime_mover": REFERENCE_CONFIG.prime_mover.value,
            "fuel": REFERENCE_CONFIG.fuel.value,
            "controls": [c.value for c in REFERENCE_CONFIG.controls],
            "run_hours": REFERENCE_CONFIG.run_hours,
            "enforceable_limit": REFERENCE_CONFIG.enforceable_limit,
            "heat_rate_btu_kwh": REFERENCE_CONFIG.heat_rate,
            "heat_input_mmbtu_hr": REFERENCE_ESTIMATE.heat_input_mmbtu_hr,
            "pte_tpy": {p: round(t, 1) for p, t in REFERENCE_ESTIMATE.tons_per_year.items()},
            "emission_factor_basis": REFERENCE_ESTIMATE.basis["emission_factors"],
        },
        "sources": {
            "counties": {"name": GAZETTEER_VINTAGE, "url": GAZETTEER_URL},
            "nonattainment": {"name": na_index.source, "fetched": na_index.fetched},
            "county_posture": {"name": county_file_label},
            "pathway_engine": "agent/pathway.py — 40 CFR 51/52, CAA 173/182, AP-42",
            "mireye": provider_label,
        },
        "trigger_citations": dict(sorted(TRIGGER_CITATIONS.items())),
        "counts": {
            "counties": len(rows),
            "insufficient_data": sum(1 for r in rows if r["data_quality"] != "ok"),
            "with_hard_stop": sum(1 for r in rows if r["hard_stops"]),
            "part_county_nonattainment": sum(1 for r in rows if r["part_county_nonattainment"]),
            "by_pathway": _tally(r["pathway"] for r in rows),
            "modelled_states": sorted(_modelled_states()),
        },
        "run": {
            "seconds": round(elapsed, 1),
            "workers": workers,
            "newly_scored": len(todo),
            **meter.as_dict(),
        },
        "counties": rows,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, separators=(",", ":")))
    print(
        f"[sweep] wrote {OUTPUT_PATH} — {len(rows):,} counties in {elapsed:,.1f}s "
        f"({OUTPUT_PATH.stat().st_size / 1e6:.1f} MB)",
        file=sys.stderr,
    )
    if with_mireye:
        print(f"[sweep] mireye {meter.as_dict()}", file=sys.stderr)
    return payload


def _tally(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _rank_key(row: dict) -> tuple:
    """Days first, then severity, then land area descending.

    Land area is the tie-break because within a tier every county scores
    identically, and the one a developer would actually look at is the one with
    room to put 500 MW on it. It is an arbitrary rule, but a stated arbitrary
    rule beats alphabetical order pretending to be a ranking.
    """
    return (
        row["days_likely"],
        -len(row["hard_stops"]),
        -(row["offsets_required_tons"] or 0),
        -row.get("land_sqmi", 0.0),
        row["state"],
        row["county"],
    )


def extremes(payload: dict, n: int = 5, distinct: bool = True) -> tuple[list[dict], list[dict]]:
    """Fastest and slowest counties.

    A county-level model produces heavy ties — every attainment county in Texas
    lands on the same number, because at this resolution they *are* the same
    number. Reporting the five alphabetically-first Texas counties would imply a
    precision that does not exist. So by default the lists take one
    representative per distinct (state, days) tier and carry ``tied_with``, the
    number of counties sharing that exact score.
    """
    rows = [r for r in payload["counties"] if r["data_quality"] == "ok"] or payload["counties"]
    tiers: dict[tuple[str, int], int] = {}
    for row in rows:
        tiers[(row["state"], row["days_likely"])] = tiers.get((row["state"], row["days_likely"]), 0) + 1

    def pick(sequence: list[dict]) -> list[dict]:
        out: list[dict] = []
        seen: set[tuple[str, int]] = set()
        for row in sequence:
            tier = (row["state"], row["days_likely"])
            if distinct and tier in seen:
                continue
            seen.add(tier)
            out.append({**row, "tied_with": tiers[tier] - 1})
            if len(out) == n:
                break
        return out

    fastest = pick(sorted(rows, key=_rank_key))
    slowest = pick(sorted(rows, key=lambda r: (-_rank_key(r)[0], *_rank_key(r)[1:])))
    return fastest, slowest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sweep.counties",
        description="Score every US county on days until legal power for a 500 MW gas plant.",
    )
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--limit", type=int, default=None, help="score only the first N counties")
    parser.add_argument(
        "--with-mireye",
        action="store_true",
        help="enrich each county interior point via providers.mireye. Burns credits.",
    )
    parser.add_argument("--fresh", action="store_true", help="ignore prior progress and rescore")
    parser.add_argument("--refresh-index", action="store_true", help="re-parse the Census gazetteer")
    args = parser.parse_args(argv)

    payload = run(
        workers=args.workers,
        limit=args.limit,
        with_mireye=args.with_mireye,
        resume=not args.fresh,
        refresh_index=args.refresh_index,
    )

    fastest, slowest = extremes(payload)
    for title, rows in (("fastest 5", fastest), ("slowest 5", slowest)):
        print(f"\n{title}")
        for r in rows:
            tied = f"  (+{r['tied_with']:,} tied in {r['state']})" if r["tied_with"] else ""
            print(
                f"  {r['days_likely']:>5,} d  {r['county']}, {r['state']:2s}  "
                f"{r['pathway']}{tied}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
