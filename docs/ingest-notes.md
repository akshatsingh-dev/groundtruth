# Ingest notes

Three sources sit next to Mireye. Everything physical comes from Mireye. These
answer the three things it does not index: what the air quality designation is,
who is in court, and what the county board has been doing.

Written 5 August 2026. Each section says what I verified by running it, what I
took on trust, and how fast it goes stale.

---

## 1. EPA Green Book — `ingest/greenbook.py`

### URLs actually used

| What | URL |
|---|---|
| Landing page | `https://www.epa.gov/green-book/green-book-data-download` |
| County x pollutant x year designations | `https://www3.epa.gov/airquality/greenbook/downld/nayro.dbf` |
| Area-level status and design values | `https://www3.epa.gov/airquality/greenbook/downld/areadata.dbf` |
| Data dictionary | `https://www3.epa.gov/airquality/greenbook/downld/greenbook_exportdoc.pdf` |

There is no CSV. The brief said "one CSV download"; it is actually four dBASE
tables, also offered as `.xls`. I took the `.dbf` because dBASE III is 60 lines
of `struct.unpack` and `.xls` is BIFF, which needs a dependency. Confirmed by
request: `allpolls_naa.csv` and friends 404.

The other two files (`allpolls_naa.dbf`, `phistory.dbf`) are downloaded to
`data/raw/` for reference but are not parsed. `allpolls_naa` is the same facts
pivoted one-row-per-area with a column per NAAQS, which is harder to normalise,
and `phistory` is partial/whole county history that `nayro.PART` already carries.

### Real schema — `nayro.dbf`, 2,095 rows, 52 fields

The fields I use, with EPA's own names:

| Field | Type | What it is |
|---|---|---|
| `FIPS_STATE` + `FIPS_CNTY` | C(2), C(3) | 5-digit county FIPS. Verified against the Census 2020 `national_county2020.txt`; zero malformed. |
| `COUNTYNAME`, `ST_ABBR` | C | County name, two-letter state |
| `POLLUTANT` | C(23) | 14 distinct values, e.g. `8-Hour Ozone (2015)`, `PM-2.5 (2012)`, `Sulfur Dioxide (2010)` |
| `AREA_NAME` | C(85) | e.g. `Los Angeles-South Coast Air Basin, CA` |
| `CLASS` | C(26) | 20 distinct values. EPA writes both `Severe 15` and `Severe-15` for the same thing. |
| `PART` | C(1) | `W` whole county, `P` part of county |
| `NONATTAIN` | C(3) | `Yes` or empty |
| `REVOKED_NA` | C(7) | `Revoked` or empty |
| `YR1992` … `YR2026` | C(2) | Stamped with the two-digit year for every year the designation was in force |
| `COMPOSID` | C(50) | Join key to `areadata`, e.g. `PM-2.5.2006.Fairbanks` |
| `EXPORTDT` | D | EPA's export date. `20260731` on the copy I pulled. |

`areadata.dbf` is 748 rows keyed on `(COMPOSID, POLLUTANT)`: `STATUS`
(`NAA` / `Maint`), `CUR_DV`, `CUR_DV24`, `DV_UNITS` (HTML-escaped —
`&micro;g/m<sup>3</sup>`), `CUR_DVASOF`, `CUR_VIO_TX`, `AREAPOP`, `REGION`.

### What "currently nonattainment" means, exactly

Three conditions, all from EPA's own columns:

```
NONATTAIN == "Yes"  and  REVOKED_NA == ""  and  YR2026 != ""
```

Drop any one and history leaks in. Unfiltered, `nayro` has 2,095 rows across
~900 counties going back to 1992. Filtered: **463 designations across 245
counties**. Join to `areadata` on `(COMPOSID, POLLUTANT)` hits 463 of 463, and
every one comes back `STATUS = NAA`, which is the independent check that the
filter is right.

Breakdown: ozone 329, PM2.5 56, SO2 40, PM10 25, lead 13. **CO and NO2: zero.**
No US county is currently CO or NO2 nonattainment, which matches EPA's own area
lists — worth knowing before someone reports a bug.

### Normalisation

`POLLUTANT` → the keys `agent.pathway` uses (`ozone`, `pm25`, `pm10`, `co`,
`so2`, `no2`, `lead`) plus the NAAQS year, because a county can be nonattainment
for two vintages of the same standard at different classifications. Los Angeles
County is `extreme` under 2015 ozone in the South Coast basin and `severe-15`
under the same standard in the West Mojave. Both rows are kept; records sort with
the current standard first.

`CLASS` → the keys `agent.pathway._NA_THRESHOLDS` is indexed by. Decisions worth
knowing about:

- `Severe 15` and `Severe-15` both → `severe-15`. Same for 17.
- `Moderate <= 12.7ppm` and `Moderate > 12.7ppm` (CO) both → `moderate`. The
  design value is in the classification string; the threshold is the same.
- `Primary`, `Secondary`, `Primary, Secondary` → `unclassified`. For SO2 and
  lead these name *which NAAQS was violated*, not a severity tier. There is no
  severity classification for those pollutants, so the 100 tpy default applies.
- `Former Subpart 1`, `Section 185A`, `Not Classified`, `Incomplete Data`,
  `Other`, empty → `unclassified`.

An unrecognised `POLLUTANT` raises rather than being dropped. A new designation
round is exactly the change this file exists to catch, and silently skipping it
would make a newly nonattainment county look clean.

### Known gaps

**Partial counties are the big one.** 171 of 463 current designations
(**37%**) cover only part of a county — a township, a planning area, an air basin
boundary that cuts a county in half. A FIPS-keyed lookup physically cannot tell
you which side of that line a parcel is on.

Handled by carrying `partial=True` on `GreenBookRecord` and appending
`— partial county, coordinate-level check required` to the `area_name` that goes
into `NonattainmentStatus`. `determine_pathway()` prints `area_name` into its
narrative, so the caveat lands in the output instead of being swallowed.
`NonattainmentStatus` has no field for this, and I did not edit `agent/pathway.py`.

Concretely: Maricopa County AZ is `partial` for both ozone and PM10. A parcel in
the far east of the county may be outside the Phoenix planning area entirely.
**Do not option land on the FIPS answer alone in a partial county** — check the
coordinate against the 40 CFR 81 area description, or field-request the boundary
from Mireye.

Other gaps:

- **PM-2.5 (2024) is not in the file.** EPA revised the primary annual PM2.5
  NAAQS to 9.0 µg/m³ on 7 Feb 2024 and anticipated signing initial designations
  in February 2026. As of the 31 Jul 2026 export there are no `PM-2.5 (2024)`
  rows. The label is already in `POLLUTANTS`, so they will be picked up the first
  run after EPA adds them. Until then, an area with a 2022–2024 design value
  between 9.0 and 12.0 reads as attainment here and may not be. Marginal
  PM2.5 counties should be confirmed with the state agency.
- **Revoked standards are excluded.** 1-hour ozone and 1997 8-hour ozone
  designations still carry anti-backsliding obligations under CAA 172(e) and
  40 CFR 51.1105. Those are real but they are not the operative major-source
  threshold, and folding them in would overstate the constraint.
- **Maintenance areas are excluded.** An area redesignated to attainment with a
  maintenance plan is legally attainment — PSD, not NA NSR — but the maintenance
  plan can still constrain new sources through the SIP. Not modelled.
- **Tribal lands** are designated separately from counties in places and are not
  represented in a FIPS-keyed structure.

### Staleness

EPA re-exports roughly monthly; the copy here is stamped **2026-07-31**. That
date is what goes into `NonattainmentStatus.fetched` — the age of the *fact*, not
the age of my download, which is the number a permitting engineer would ask for.
`greenbook.data_vintage()` returns it.

Designations change on a rulemaking cycle, not continuously, so a month-old copy
is fine. Re-run `python -m ingest.greenbook` (or delete `data/greenbook.json`) to
refresh. The parsed output is committed as `data/greenbook.json`, 225 KB, so the
national sweep never re-parses and the repo runs offline.

---

## 2. CourtListener / RECAP — `ingest/dockets.py`

### URLs actually used

| What | URL |
|---|---|
| Docs | `https://wiki.free.law/c/courtlistener/help/api/rest/v4/overview` (the old `/help/api/rest/` 301s here) |
| Search | `https://www.courtlistener.com/api/rest/v4/search/` |
| Court list (used once, to generate a constant) | `https://www.courtlistener.com/api/rest/v4/courts/?jurisdiction=FD` |

**Current version is v4** (v4.4 as of the docs on 5 Aug 2026). Auth is
`Authorization: Token <token>`.

### Verified by running it, not by reading docs

- **Search answers without a token.** `GET /api/rest/v4/search/?q=test&type=r`
  → 200. The `dockets` endpoint returns **401** without one. Since only search is
  used, `COURTLISTENER_TOKEN` is an upgrade rather than a requirement.
- **Anonymous rate limits are tight.** I hit a 429 after roughly ten requests in
  a few minutes. Authenticated limits are documented as 5/min, 50/hour,
  125/day. Set the token before any sweep.
- `type=r` returns dockets with a `recap_documents` array carrying per-document
  `snippet`. `type=d` returns the same dockets without documents.
- `filed_after=YYYY-MM-DD` and `order_by=dateFiled desc` both work.
- `court` takes **space-separated** court IDs. **An unknown court ID returns
  `count: 0` rather than an error**, so a typo is indistinguishable from an
  answer. That is why `STATE_DISTRICT_COURTS` is a generated constant rather
  than a string the caller passes.
- `party_name` filters on actual parties. This is the difference between "this
  developer was sued" and "this developer was mentioned in someone's exhibit".
- A docket appears once per matching document, so results need dedup.

### Response fields used

`caseName`, `docketNumber`, `court_citation_string`, `court_id`, `dateFiled`,
`docket_absolute_url`, `cause`, `party[]`, `recap_documents[].snippet`.

`cause` is the most useful field in the payload and is why it is on the `Docket`
dataclass: `42:7413(b) Clean Air Act` versus `35:281 Patent Infringement` is the
whole difference between a permitting blocker and noise.

### The live case — found, and the brief had it wrong

The build brief says *"NAACP / SELC / Earthjustice v. xAI over the Memphis gas
turbines, filed around April 2026, Western District of Tennessee."*

Ran `for_developer("X.AI Corp.")`. Found:

```
National Association for the Advancement of Colored People v. X.AI Corp.
  3:26-cv-00074 (full: 3:26-cv-00074-DMB-JMV)
  District Court, N.D. Mississippi  (court_id: msnd)
  filed 2026-04-14
  cause: 42:7413(b) Clean Air Act
  judge: Debra Marie Brown
  parties: NAACP; Mississippi State Conference of the NAACP; X.AI Corp.; MZX Tech LLC
  firms include Earthjustice and Earthjustice Gulf Region; Butler Snow;
    Vinson & Elkins; Troutman Pepper Locke; Boyden Gray
  https://www.courtlistener.com/docket/73188848/national-association-for-the-advancement-of-colored-people-v-xai-corp/
```

Three corrections to the brief, all confirmed against the docket and against
Earthjustice's and NAACP's own press releases:

1. **Northern District of Mississippi, not Western District of Tennessee.**
2. **The facility is the Colossus Gas Plant at Southaven, DeSoto County,
   Mississippi** — 27 turbines, ~495 MW, powering Colossus 2 — not the Memphis
   Shelby County site. Memphis is the separate, earlier fight where the Shelby
   County Health Department *granted* a permit for 15 turbines (247.2 MW) in
   July 2025.
3. **SELC does not appear on the CourtListener firm list for this docket;
   Earthjustice does.** SELC was on the February 2026 notice of intent to sue.
   Two organisations, two documents — worth not conflating in a demo.

DOJ moved to intervene and dismiss on 15 June 2026, arguing the case threatens
power for AI systems used by the military. That motion is visible in the docket's
`recap_documents`.

Also in RECAP and worth noting: `x.AI LLC v. Darana Hybrid LLC`, 2:26-cv-02994
(W.D. Tenn., filed 2026-08-04) — a different, newer xAI case that *is* in the
district the brief named. Easy to mistake for the environmental suit.

### Known gaps

- **Federal only.** RECAP is PACER. The fight that actually kills most data
  center projects is in *state* court — a board of supervisors decision appealed
  to a circuit court — and none of that is here. The Prince William Digital
  Gateway litigation is state court. This source finds Clean Air Act citizen
  suits, RLUIPA land use claims and removed diversity cases; it does not find
  zoning appeals.
- **`for_county` is noisy.** The venue pass is full text over every document
  filed in the district, so `"Loudoun County" AND "data center"` returns Google
  patent cases that mention Google's Loudoun facilities. The party pass is clean
  and is returned first. Results are evidence to read, not a count to score on.
  Real hits it did find for Prince William: *Alive Church of the Nazarene v.
  Prince William County* (RLUIPA land use, county as defendant) and *GW
  Acquisition Co. v. Pageland LLC* (the Pageland Lane assemblage behind the
  Digital Gateway).
- **RECAP coverage is not complete.** RECAP holds what someone has purchased and
  contributed from PACER, plus free-look documents. A quiet docket may exist and
  not be here. Absence is weak evidence.
- **No cross-entity resolution.** `for_developer("X.AI Corp.")`,
  `"X.AI LLC"` and `"X Corp"` are three different party strings and return
  overlapping but different sets. Subsidiaries and SPVs — the LLC that actually
  holds a data center parcel is usually a shell with an unrelated name — are not
  linked. Query the specific entity on the deed, not the brand.

### Failure handling

`search()` never raises. Every failure path — no network, 401/403, 429, non-200,
non-JSON — returns `[]` and records why on `status()`. Without a token,
`status().reason` carries `NO_TOKEN_REASON` even on success, so an agent can
report "searched unauthenticated" rather than implying a clean result.

### Staleness

RECAP updates continuously. `data/dockets_cache.json` has a **7-day TTL** per
query and is committed, so a demo works offline and repeated runs are free. The
committed cache contains the xAI query and three county queries. Delete the file
or pass `use_cache=False` to force a refresh.

---

## 3. County posture — `ingest/counties.json`, `ingest/counties.py`

**27 counties, typed by hand, 17 high confidence and 10 medium.** 11 have a
moratorium in force. Postures: 16 hostile, 5 special-exception, 6 by-right.

A scraper was not worth the hours, and the brief says so. There is no national
database of county data center ordinances; the trackers that exist disagree with
each other and mix city actions with county actions in the same column. Every
record here was read from the linked source before it was typed.

### What was verified

- **Every FIPS code** was checked against the Census 2020
  `national_county2020.txt`. 27/27 matched name and state.
- **Every record has a source URL**, and `counties.py` refuses to load a record
  without one, without a valid 5-digit FIPS, or with a `zoning_posture` outside
  the three values `agent.pathway` reads.
- Nine records come from **primary sources** — the county's own site or press
  release (Montgomery MD, Linn IA, Santa Fe NM, Walker GA, Louisa VA), a law
  firm client alert on the adopted ordinance (Loudoun VA), or the plaintiff's own
  press release (DeSoto MS).

### The distinction the file encodes

**A city moratorium is not a county moratorium.** Peculiar, Missouri deleting
"data center" from its zoning code killed a $1.5B project — but it does not bind
the rest of Cass County. Fayetteville amending its UDO does not bind
unincorporated Fayette County. Those records carry `moratorium: false` with the
municipal action written out in `moratorium_note`, because applying a city
ordinance across a whole county gives a wrong answer for most of the county's
land. Broomfield CO is the exception: it is a consolidated city-county, so the
city ordinance *is* the county ordinance.

### Records that earn their place

- **Hill County, TX** — one-year moratorium adopted 12 May 2026, rescinded
  5 June 2026 under a reported $100M developer lawsuit. Twenty-four days. A
  moratorium is not a durable fact.
- **Pima County, AZ** — Tucson City Council killed Project Blue 7-0 in August
  2025; the county Board of Supervisors approved the land deal 3-2 in December
  2025 and the developer moved to unincorporated land. City posture and county
  posture are different variables.
- **DeSoto County, MS** — permissive county, attainment air basin, no
  moratorium, and the project is in federal court anyway. The record that shows
  why county posture alone is not a screen.
- **Prince William County, VA** — approved the Digital Gateway rezoning in 2023,
  denied Dulles Cloud South 8-0 in July 2026. Do not price this county off the
  2023 vote.
- **Stokes County, NC** and **Glynn County, GA** — boards that *rejected*
  proposed moratoria. Organised opposition at a hearing is not a denial.

### Known gaps

- **Coverage is 27 of ~3,140 counties, and it is not a sample.** These are the
  counties where something happened. `for_fips()` returns `None` everywhere else,
  and `apply_to()` writes an explicit provenance note saying that absence of a
  record is absence of evidence, not evidence of absence. Any national map built
  on this must not colour unknown counties as permissive.
- **Municipal actions are under-covered.** Most of the 2026 moratorium wave is
  municipal — Seattle, Spokane, Coachella, Ravenna, Lordstown, San Marcos,
  Lysander NY, Perth NY. This file is keyed on county FIPS and cannot represent
  them, so it names them in the county note only where a well-known project sits
  in that municipality.
- **Indiana is under-represented.** IU's Environmental Resilience Institute
  counted 11 Indiana counties with ordinances and at least 17 with temporary
  moratoria by mid-2026. Only Marshall County is entered, because it is the only
  one where I could find the specific action and date. Cass County IN is reported
  as the second outright ban and is **deliberately left out** — I could not
  confirm the ordinance date. Same for Sierra County NM, Jackson County MO,
  Dodge County WI and Pulaski County AR: reported by trackers, not verified here.
- **Expiry dates are mostly unmodelled.** Several moratoria have a stated end
  (Linn IA to 1 Jan 2028, DeKalb GA to 30 Sep 2026, Sarasota FL to Jul 2027) and
  those are in the note text, but the schema has no `expires` field and nothing
  computes against it. Read the note.
- **Medium confidence means one source.** Ten records rest on a single story or
  a tracker entry, and the note says which part to re-verify.

### Staleness

This is the fastest-rotting source in the repo. Records were entered **2026-08-05**
and each carries its own `entered` date. Moratoria get adopted, extended and
rescinded on a weekly cadence right now — DeKalb GA extended its by 100 days in
June, Hill TX rescinded its inside a month. **Anything older than about 30 days
should be re-read before it goes in front of a buyer**, and any record over 90
days old should be treated as a lead rather than a fact.

---

## Where each source lands in `SiteContext`

| Field | Source | Function |
|---|---|---|
| `nonattainment` | Green Book | `greenbook.for_county(fips)` |
| `moratorium`, `moratorium_note`, `zoning_posture` | county file | `counties.apply_to(site)` |
| `litigation` | CourtListener | `dockets.as_litigation_notes(dockets.for_county(...))` |
| `provenance["county_posture"]` | county file | set by `counties.apply_to` |

Everything else on `SiteContext` is Mireye.

## Interfaces other modules bind to

`agent/tools.py` and `sweep/counties.py` were written in parallel against these
modules and probe for function names rather than importing a fixed signature.
Two shapes exist only to keep those probes working, and should not be changed
without checking both callers:

- `greenbook.load_nonattainment()` returns a list of one dict per county
  (`fips`, `state`, `county`, `part_county`, `nonattainment[]`).
  `sweep/counties.py` joins on county *name*, not FIPS, and falls back to
  scraping the Green Book HTML page if this is missing. Keeping it means the
  national sweep runs off the parsed dBASE export.
- `counties.load()` returns `dict[str, dict]` — raw records keyed by FIPS, the
  shape of the JSON file itself — because `sweep/counties.py` reads them
  structurally. `counties.records()` and `counties.for_fips()` give the typed
  `CountyRecord` view.
- `dockets.Docket.summary()` is what `agent/tools.py` calls to turn a case into
  the one-line string `SiteContext.litigation` expects.
