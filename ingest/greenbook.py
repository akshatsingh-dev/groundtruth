"""EPA Green Book nonattainment designations, keyed by county FIPS.

This is the single fact that flips the permit pathway. Attainment county: PSD,
BACT, 250 tpy (or 100 tpy for a listed category). Nonattainment county: NSR with
LAER, mandatory emission offsets, and a major-source threshold that falls to
10 tpy in an extreme ozone area. Same plant, same developer, different answer.

Source is the Green Book export files, not the HTML pages. EPA publishes four
dBASE tables at https://www.epa.gov/green-book/green-book-data-download and
refreshes them roughly monthly. Two of them matter here:

  nayro.dbf     One row per (county, pollutant, NAAQS, area). Carries FIPS_STATE
                and FIPS_CNTY, the classification, whether the county is wholly
                or partly in the area, and a YR1992..YR2026 column per year that
                is stamped for every year the designation was in force. That last
                part is what makes "is this county nonattainment *today*" a clean
                query instead of a guess.
  areadata.dbf  One row per (area, pollutant). Carries the current design value
                and whether the area is still NAA or has moved to maintenance.
                Joined on COMPOSID so a screen can say how close the area is to
                being redesignated, which is a real input to a 3-year timeline.

There is no CSV. EPA offers .dbf and .xls only, and .xls is BIFF, which needs a
dependency. dBASE III is 60 lines of struct.unpack, so we parse the .dbf.

Two honest limits, both stated in docs/ingest-notes.md:

1.  Roughly a third of current designations are partial counties — a township, a
    planning area, an air basin boundary that cuts a county in half. A FIPS-keyed
    lookup cannot tell you which side of that line a parcel sits on. Those
    records carry partial=True and say so in the area name, so the output reads
    "check the coordinate" rather than silently applying a severe-15 threshold to
    a parcel that is not in the area.
2.  Revoked standards are excluded. A 1-hour ozone designation from 1991 has
    anti-backsliding consequences but is not the operative threshold, and mixing
    it in would overstate the constraint.
"""

from __future__ import annotations

import html
import json
import re
import struct
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

import httpx

from agent.pathway import NonattainmentStatus

_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = _ROOT / "data" / "raw"
CACHE_PATH = _ROOT / "data" / "greenbook.json"

#: EPA's export directory. These filenames have been stable for years; the
#: contents are re-exported roughly monthly and carry their own EXPORTDT.
BASE_URL = "https://www3.epa.gov/airquality/greenbook/downld"
DOWNLOADS = {
    "nayro": f"{BASE_URL}/nayro.dbf",
    "areadata": f"{BASE_URL}/areadata.dbf",
}
LANDING_PAGE = "https://www.epa.gov/green-book/green-book-data-download"

#: EPA's POLLUTANT string -> (pathway.py pollutant key, NAAQS year).
#: The NAAQS year matters because a county can be nonattainment for two vintages
#: of the same standard at different classifications, and the current standard is
#: the one that governs. Revoked standards are still listed here so the parser can
#: recognise and drop them rather than silently mis-key them.
POLLUTANTS: dict[str, tuple[str, int]] = {
    "1-Hour Ozone (1979)": ("ozone", 1979),
    "8-Hour Ozone (1997)": ("ozone", 1997),
    "8-Hour Ozone (2008)": ("ozone", 2008),
    "8-Hour Ozone (2015)": ("ozone", 2015),
    "PM-2.5 (1997)": ("pm25", 1997),
    "PM-2.5 (2006)": ("pm25", 2006),
    "PM-2.5 (2012)": ("pm25", 2012),
    "PM-2.5 (2024)": ("pm25", 2024),
    "PM-10 (1987)": ("pm10", 1987),
    "Carbon Monoxide (1971)": ("co", 1971),
    "Sulfur Dioxide (1971)": ("so2", 1971),
    "Sulfur Dioxide (2010)": ("so2", 2010),
    "Nitrogen Dioxide (1971)": ("no2", 1971),
    "Lead (1978)": ("lead", 1978),
    "Lead (2008)": ("lead", 2008),
}

#: EPA's CLASS string -> the key agent.pathway._NA_THRESHOLDS is indexed by.
#: EPA writes "Severe 15" and "Severe-15" for the same thing in different rows.
#: The CO entries encode the design value in the classification name; both are
#: still "moderate" for threshold purposes. SO2 and lead have no severity
#: classification at all — "Primary" names which NAAQS was violated, not how
#: badly — so those map to unclassified and take the 100 tpy default.
CLASSIFICATIONS: dict[str, str] = {
    "": "unclassified",
    "marginal": "marginal",
    "marginal (rural transport)": "marginal",
    "rural transport (marginal)": "marginal",
    "moderate": "moderate",
    "moderate <= 12.7ppm": "moderate",
    "moderate > 12.7ppm": "moderate",
    "serious": "serious",
    "severe": "severe",
    "severe 15": "severe-15",
    "severe-15": "severe-15",
    "severe 17": "severe-17",
    "severe-17": "severe-17",
    "extreme": "extreme",
    "not classified": "unclassified",
    "incomplete data": "unclassified",
    "former subpart 1": "unclassified",
    "section 185a": "unclassified",
    "other": "unclassified",
    "primary": "unclassified",
    "secondary": "unclassified",
    "primary, secondary": "unclassified",
}


class GreenBookError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# dBASE III reader
# --------------------------------------------------------------------------


def read_dbf(path: Path) -> Iterator[dict[str, str]]:
    """Yield each live record of a dBASE III table as a dict of stripped strings.

    Deliberately does no type coercion. EPA uses the character type for numbers
    that are sometimes blank and sometimes "0.075", and a parser that guesses
    would turn a missing design value into a real one.
    """
    blob = path.read_bytes()
    if len(blob) < 32:
        raise GreenBookError(f"{path.name} is truncated ({len(blob)} bytes)")

    n_records, header_len, record_len = struct.unpack("<IHH", blob[4:12])

    fields: list[tuple[str, int]] = []
    pos = 32
    while blob[pos] != 0x0D:
        descriptor = blob[pos : pos + 32]
        name = descriptor[:11].split(b"\x00")[0].decode("latin-1")
        fields.append((name, descriptor[16]))
        pos += 32

    for i in range(n_records):
        start = header_len + i * record_len
        record = blob[start : start + record_len]
        if len(record) < record_len or record[:1] == b"*":  # deleted
            continue
        row: dict[str, str] = {}
        offset = 1  # first byte is the deletion flag
        for name, width in fields:
            row[name] = record[offset : offset + width].decode("latin-1").strip()
            offset += width
        yield row


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


@dataclass
class GreenBookRecord:
    """One current nonattainment designation as it applies to one county.

    Richer than NonattainmentStatus on purpose. The pathway engine only needs
    pollutant, classification and area name; a human reviewing the output needs
    to know whether the designation covers the whole county and how close the
    area is to redesignation.
    """

    county_fips: str
    county: str
    state: str
    pollutant: str  # "ozone", "pm25", ...
    naaqs: int  # the standard year, e.g. 2015
    naaqs_label: str  # EPA's own string, e.g. "8-Hour Ozone (2015)"
    classification: str  # lowercased, keyed to agent.pathway._NA_THRESHOLDS
    area_name: str
    partial: bool  # designation covers only part of this county
    area_status: str | None = None  # "NAA" or "Maint" from areadata
    design_value: str | None = None
    design_value_units: str | None = None
    design_value_as_of: str | None = None
    currently_violating: str | None = None  # EPA's CUR_VIO_TX
    export_date: str | None = None  # EPA's own EXPORTDT — the data vintage

    @property
    def note(self) -> str:
        """What a reader needs appended to the area name to not be misled."""
        if self.partial:
            return (
                f"{self.area_name} — partial county, coordinate-level check required"
            )
        return self.area_name

    def to_status(self) -> NonattainmentStatus:
        """Project onto the dataclass the pathway engine consumes.

        NonattainmentStatus has no field for partial coverage, so the caveat rides
        in area_name. determine_pathway() prints area_name into its narrative, so a
        partial-county designation is visible in the output rather than buried.
        """
        return NonattainmentStatus(
            pollutant=self.pollutant,
            classification=self.classification,
            area_name=self.note,
            source=f"EPA Green Book ({self.naaqs_label})",
            fetched=self.export_date,
        )


# --------------------------------------------------------------------------
# Download and parse
# --------------------------------------------------------------------------


def download(force: bool = False, timeout: float = 120.0) -> dict[str, Path]:
    """Pull the export files into data/raw. Skips files already present."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, url in DOWNLOADS.items():
        target = RAW_DIR / f"{name}.dbf"
        if target.exists() and not force:
            paths[name] = target
            continue
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        if len(response.content) < 1024:
            raise GreenBookError(f"{url} returned {len(response.content)} bytes")
        target.write_bytes(response.content)
        paths[name] = target
    return paths


def _clean_units(raw: str) -> str | None:
    """EPA stores units as HTML fragments: '&micro;g/m<sup>3</sup>'."""
    if not raw:
        return None
    return re.sub(r"<[^>]+>", "", html.unescape(raw)).strip() or None


def _iso(yyyymmdd: str) -> str | None:
    if not yyyymmdd or len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        return None
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:])).isoformat()
    except ValueError:
        return None


def parse(as_of_year: int | None = None) -> list[GreenBookRecord]:
    """Read the raw tables and return every designation in force this year.

    "In force" is three conditions, all from EPA's own columns:
      NONATTAIN == "Yes"     the row is a nonattainment designation
      REVOKED_NA is empty    the standard has not been revoked
      YR<year> is stamped    the designation is live in the year we care about

    Dropping any one of those pulls in history. nayro carries every designation
    back to 1992, so an unfiltered read makes 245 nonattainment counties look
    like 900.
    """
    paths = download()
    year = as_of_year or date.today().year
    year_column = f"YR{year}"

    areas = {}
    export_date = None
    for row in read_dbf(paths["areadata"]):
        areas[(row["COMPOSID"], row["POLLUTANT"])] = row
        export_date = export_date or _iso(row["EXPORTDT"])

    records: list[GreenBookRecord] = []
    unknown_pollutants: set[str] = set()

    for row in read_dbf(paths["nayro"]):
        if row["NONATTAIN"] != "Yes" or row["REVOKED_NA"]:
            continue
        if year_column not in row:
            raise GreenBookError(
                f"nayro.dbf has no {year_column} column. EPA adds one per year; "
                f"if this fires the file is older than the run date."
            )
        if not row[year_column]:
            continue

        label = row["POLLUTANT"]
        if label not in POLLUTANTS:
            unknown_pollutants.add(label)
            continue
        pollutant, naaqs = POLLUTANTS[label]

        classification = CLASSIFICATIONS.get(row["CLASS"].strip().lower(), "unclassified")
        area = areas.get((row["COMPOSID"], label), {})

        records.append(
            GreenBookRecord(
                county_fips=row["FIPS_STATE"] + row["FIPS_CNTY"],
                county=row["COUNTYNAME"],
                state=row["ST_ABBR"],
                pollutant=pollutant,
                naaqs=naaqs,
                naaqs_label=label,
                classification=classification,
                area_name=row["AREA_NAME"],
                partial=row["PART"] == "P",
                area_status=area.get("STATUS") or None,
                design_value=(area.get("CUR_DV") or area.get("CUR_DV24") or None),
                design_value_units=_clean_units(area.get("DV_UNITS", "")),
                design_value_as_of=_iso(area.get("CUR_DVASOF", "")),
                currently_violating=area.get("CUR_VIO_TX") or None,
                export_date=_iso(row["EXPORTDT"]) or export_date,
            )
        )

    if unknown_pollutants:
        raise GreenBookError(
            "Unrecognised POLLUTANT values in nayro.dbf: "
            + ", ".join(sorted(unknown_pollutants))
            + ". Add them to POLLUTANTS rather than dropping them — a new NAAQS "
            "designation round is exactly the update this file exists to catch."
        )

    # Current standard first, so na_for() returns the one that governs.
    records.sort(key=lambda r: (r.county_fips, r.pollutant, -r.naaqs, r.area_name))
    return records


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------


def build_cache(force: bool = False) -> dict:
    """Parse once and write data/greenbook.json.

    The national sweep touches 3,140 counties. Re-reading two dBASE tables and
    re-filtering 2,095 rows for each of them is pointless, and the parsed result
    is ~200 KB of JSON that is worth committing so the repo runs offline.
    """
    if CACHE_PATH.exists() and not force:
        return json.loads(CACHE_PATH.read_text())

    records = parse()
    by_fips: dict[str, list[dict]] = {}
    for record in records:
        by_fips.setdefault(record.county_fips, []).append(asdict(record))

    payload = {
        "source": "EPA Green Book",
        "source_url": LANDING_PAGE,
        "files": DOWNLOADS,
        "epa_export_date": records[0].export_date if records else None,
        "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "record_count": len(records),
        "county_count": len(by_fips),
        "partial_county_count": sum(1 for r in records if r.partial),
        "counties": by_fips,
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, indent=1, sort_keys=True))
    return payload


_cache: dict | None = None


def _cached() -> dict:
    global _cache
    if _cache is None:
        _cache = build_cache()
    return _cache


def records_by_county() -> dict[str, list[GreenBookRecord]]:
    """Full records, including the partial-county flag and design values."""
    return {
        fips: [GreenBookRecord(**row) for row in rows]
        for fips, rows in _cached()["counties"].items()
    }


def load() -> dict[str, list[NonattainmentStatus]]:
    """Every currently nonattainment county, keyed by 5-digit FIPS.

    Counties not in the mapping are attainment or unclassifiable, which is the
    same thing for permitting purposes. Do not treat a missing key as unknown.
    """
    return {
        fips: [GreenBookRecord(**row).to_status() for row in rows]
        for fips, rows in _cached()["counties"].items()
    }


def for_county(fips: str) -> list[NonattainmentStatus]:
    """Designations for one county. Empty list means attainment."""
    rows = _cached()["counties"].get(str(fips).zfill(5), [])
    return [GreenBookRecord(**row).to_status() for row in rows]


def records_for_county(fips: str) -> list[GreenBookRecord]:
    rows = _cached()["counties"].get(str(fips).zfill(5), [])
    return [GreenBookRecord(**row) for row in rows]


def data_vintage() -> str | None:
    """EPA's own export date. This is the age of the fact, not of our download."""
    return _cached().get("epa_export_date")


if __name__ == "__main__":  # pragma: no cover
    payload = build_cache(force=True)
    print(f"EPA export date: {payload['epa_export_date']}")
    print(
        f"{payload['record_count']} designations across {payload['county_count']} counties "
        f"({payload['partial_county_count']} partial-county)"
    )
    counts: dict[str, int] = {}
    for rows in payload["counties"].values():
        for row in rows:
            counts[row["pollutant"]] = counts.get(row["pollutant"], 0) + 1
    for pollutant, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {pollutant:6s} {count}")
    print(f"\nwrote {CACHE_PATH}")
