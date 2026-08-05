# National county sweep — method and limits

What it is: every US county scored on **days until legal power for a 500 MW gas
plant**. One fixed plant, 3,222 counties, so the only thing varying across the
map is the ground.

What it is not: a site screen. It is a screening layer. The parcel run is the
real answer, and every record in `data/county_scores.json` carries
`resolution: "county"` to say so.

Run it:

```
python -m sweep.counties        # -> data/county_scores.json
python -m sweep.map             # -> outputs/county_map.html
```

Neither needs an API key.

---

## 1. The reference plant

Scored identically in every county:

| | |
|---|---|
| Capacity | 500 MW |
| Prime mover | Combined-cycle gas turbine |
| Fuel | Natural gas |
| Controls | Dry low-NOx combustors + SCR + oxidation catalyst |
| Run hours | 8,760, **no federally enforceable cap** |
| Heat rate | 6,800 Btu/kWh HHV (module default for combined cycle) |
| Heat input | 3,400 MMBtu/hr |

Potential to emit, from AP-42 Table 3.1-1 factors:

| Pollutant | tpy |
|---|---:|
| NOx | 148 |
| CO | 122 |
| PM10 / PM2.5 | 98 each |
| SO2 | 51 |
| VOC | 16 |
| Formaldehyde | 3.2 |
| CO2e | 1,638,120 |

Three choices in that config are doing most of the work, and each was made to
avoid stacking the deck:

**Combined cycle, not simple cycle.** The heat recovery steam generator makes
the plant a "fossil fuel-fired steam electric plant of more than 250 million
Btu/hr heat input" — entry 1 on the List of 28 at 40 CFR 52.21(b)(1)(i)(a). That
drops the PSD major source threshold from 250 tpy to 100 tpy. A simple-cycle
turbine of the same size is not a listed category and would be major at 250 tpy.
That single distinction is worth 150 tpy of headroom, and it is the most common
thing a screen gets wrong.

**Best-available controls, not a strawman.** DLN plus SCR takes NOx from 0.32 to
0.0099 lb/MMBtu, a 97% reduction. An oxidation catalyst takes 90% of the CO. This
is roughly what a BACT determination would land on today. The plant still emits
148 tpy of NOx. The point of the map is that the ceiling is structural, not a
result of picking bad equipment.

**No run-hour cap.** Potential to emit is computed at 8,760 hours unless the
developer accepts a federally enforceable permit condition. A data center is
baseload. Modelling this at 4,000 hours would produce a much prettier map and
would be wrong.

### The consequence, which is the headline

**There is no county in the United States where this plant is a minor source.**
2,843 counties land on major PSD; 379 land on major nonattainment NSR. Zero minor
NSR, zero synthetic minor, zero permit-by-rule. The map is not "where can I build
easily". It is "which major permit, and whose desk".

---

## 2. Method

For each county:

1. Take the Census gazetteer record — FIPS, name, state, and the interior point
   (`INTPTLAT` / `INTPTLONG`). Interior point rather than centroid: a
   horseshoe-shaped county's centroid can land outside the county, and a lookup
   there returns another jurisdiction's answer.
2. Build an `agent.pathway.SiteContext` from what is knowable at county level:
   - nonattainment designations from `ingest.greenbook` (EPA Green Book)
   - the state agency overlay in `agent.pathway.STATE_OVERLAYS`
   - moratorium / zoning posture / litigation from `ingest.counties`
3. Run `agent.emissions.estimate()` once (the config never changes, so the PTE is
   computed once and reused) and `agent.pathway.determine_pathway()` per county.
4. Record the pathway, the months low/likely/high, every trigger that fired with
   its added months, the hard stops, the controlling pollutant, the applicable
   threshold, and the offset tonnage.

Days are months × 30.437.

When a county carries several designations for the same pollutant under different
NAAQS vintages, the sweep keeps the **worst** classification. That is what an
applicability determination does — the stricter rule governs.

### Parallelism and resumability

`ThreadPoolExecutor`, default 12 workers, `--workers` to change it. Without
Mireye the work is pure arithmetic and the whole sweep finishes in well under a
second, so the executor is there for the `--with-mireye` path, where every county
is two network calls.

Every finished county is appended to `data/county_scores.progress.jsonl` and
`fsync`ed before the next one starts. A re-run reads that file, skips what is
already there, and continues. Killing the process at county 2,400 and restarting
resumes at 2,400.

A `kill -9` mid-write leaves a partial line with no trailing newline. Appending
to that file would concatenate the next record onto the fragment and destroy
both, so a resume rewrites the log from the intact records before it appends. That
was a real bug, found by truncating the file and re-running; the test is worth
keeping.

---

## 3. Data vintages

| Source | Vintage | How |
|---|---|---|
| County list, FIPS, interior points | 2025 Census Gazetteer, counties, national (file dated 10 Sep 2025) | One 139 KB zip, downloaded once to `data/raw/`, parsed to `data/county_index.json` |
| County boundaries | 2025 Census cartographic boundary files, 1:5,000,000 (file dated 23 Apr 2026) | One 3.0 MB zip, `.shp` + `.dbf` parsed in `sweep/map.py` |
| State boundaries | Same, 1:5,000,000 | Used for the state outlines on the map |
| Nonattainment | EPA Green Book, current nonattainment counties, all criteria pollutants — fetched 2026-07-31 via `ingest.greenbook` | 236 of 3,222 counties carry at least one designation |
| County posture | `ingest/counties.json`, 27 hand-entered records | 11 counties with a moratorium, 16 with hostile zoning |
| Emission factors | AP-42 Table 3.1-1 / 3.1-2a / 3.1-3 | `agent/emissions.py` |
| Thresholds | 40 CFR 52.21, 40 CFR 51.165, CAA 173/182 | `agent/pathway.py` |

Census URLs were verified live on 5 Aug 2026 (HTTP 200 with `Last-Modified`
headers as above). 2025 is the most recent vintage published for both files.

### What happens when a source is missing

If `ingest.greenbook` is unavailable, the sweep falls back to parsing the Green
Book county page directly (one HTML file, no key). If that also fails, every
county is marked `data_quality: "insufficient"` with this note:

> No nonattainment designation available. The pathway and timeline below are a
> floor: a nonattainment designation can only escalate them. Do not read this
> county as attainment.

Those counties render on the map as a grey diagonal hatch, never as a ramp step —
an unknown is not a low value. The degraded path is tested by hiding the source
and re-running; it produces a fully hatched map rather than a clean-looking one.

---

## 4. What county resolution can and cannot tell you

**It can see:**

- Whether the county is in nonattainment, for which pollutant, at what
  classification. This is the single fact that flips the pathway from PSD to
  nonattainment NSR, and it decides whether you need offsets.
- The offset ratio and therefore the tonnage you have to buy. In a severe or
  extreme area those credits are frequently unavailable at any price, which is a
  hard stop rather than a delay.
- Which agency reviews the application, and how that agency behaves. Eight states
  are modelled from public permit records; the rest fall back to the federal
  default with no adjustment, and those counties are flagged
  `state_modelled: false`.
- County-level political posture: moratoria and recent denials, where somebody
  entered the record by hand.

**It cannot see:**

- **PSD increment already consumed.** Increment is a finite budget tracked
  against modelled receptors in a specific area, not per county. Two parcels in
  the same county can be on opposite sides of an increment problem.
- **Terrain relief in the modelling domain.** Complex terrain forces AERMOD with
  terrain-following receptors and usually a taller stack. County-level terrain is
  meaningless — the average US county is about 1,100 square miles.
- **Distance to a gas transmission pipeline.** This is the New Mexico failure
  mode: the plant was permittable, the pipeline that fed it was not. It is a
  parcel fact.
- **Class I area distance**, which drives the Federal Land Manager AQRV review,
  and which can stop a project on visibility grounds even when the NAAQS
  modelling passes.
- **Residential receptor counts**, which drive the EJ and opposition triggers.

**91 counties are only partly in nonattainment.** EPA designates areas, not
counties, and an area boundary can run through the middle of one. Those records
carry `part_county_nonattainment: true`. For those, the county-level answer is
wrong for part of the county in a knowable direction, and only a coordinate-level
check resolves it.

**53 distinct answers across 3,222 counties.** That is the honest resolution of
this model, and the map's full-answers table shows all 53 so nobody has to take
it on trust. It is also the argument for the parcel run: if the county map could
tell you what you need to know, it would produce more than 53 answers.

---

## 5. Run and file numbers

| | |
|---|---:|
| Counties scored | 3,222 |
| Counties drawn on the map | 3,219 |
| Sweep run time, 16 workers, no Mireye | 0.5 s |
| Map render time | 0.7 s |
| `data/county_scores.json` | 7.7 MB |
| `outputs/county_map.html` | 0.72 MB |
| `outputs/county_map.svg` (static, for PNG) | 0.58 MB |
| Distinct answers | 53 |
| Counties with a hard stop | 77 |
| Counties marked insufficient data | 0 |

Three counties are scored but not drawn: they are in territories
(American Samoa, Guam, Northern Mariana Islands, US Virgin Islands) that have no
place in the Albers USA composite. Puerto Rico's 78 municipios *are* drawn, as an
inset — they have EPA designations like anywhere else, and leaving them off a
"national" map is a choice rather than a default.

The sweep is fast because it is arithmetic. Loading and parsing the source files
dominates the wall clock; the 3,222 pathway determinations themselves are the
cheap part.

---

## 6. Mireye calls and credits

The sweep runs at county resolution with **zero Mireye calls** by default. That
is deliberate: the map has to be reproducible by anyone with no key.

`--with-mireye` enriches each county's interior point with the physical facts the
county file cannot supply. Per county:

- one `/v1/fetch` with an explicit field list — the union of `AIR_PERMIT_FIELDS`
  (nonattainment flags, air district, nearest Class I area distance) with the
  `terrain`, `utilities` and `demographics` expansions. 42 fields, which is under
  the 50-field cap, so it bills as one call at 1 credit per field.
- one `/v1/proximity` for gas pipeline, transmission and airport, in **geodesic**
  mode at 2 credits per target. Driving mode is 12 credits per target and would
  put the same sweep past 500,000 credits for an answer that does not change any
  permit trigger.

| | |
|---|---:|
| Calls per county | 2 |
| Credits per county | 48 |
| Full national sweep, calls | 6,444 |
| Full national sweep, credits | 154,656 |
| At $1.00 per 1,000 credits | ~$155 |

The estimate is printed before the run starts. `--max-credits N` stops enrichment
once the provider's meter passes N; counties past the cap still score, at county
resolution, and the run says so rather than silently changing what the numbers
mean. That is the §12 guardrail implemented as a boundary rather than a note.

**Credits actually spent so far: 0.** No key was configured when this map was
built. The enrichment path was exercised with a deliberately invalid key: 16
calls, 16 errors, 0 credits, 0 counties enriched, and every record correctly kept
`resolution: "county"` rather than claiming an enrichment that did not happen.
Run-level call and credit totals come straight off
`providers.mireye.usage()` — the same number Mireye will have — rather than from
a count kept here.

Note that this shape is leaner than the 30k–60k call estimate in the build brief.
That estimate assumed several presets per county. Batching the field list into one
`/v1/fetch` and using geodesic proximity cuts it to two calls, at the cost of
about 155k credits rather than 30–60k calls' worth. The credit number is the one
that matters for the founders email.

---

## 7. The map

`outputs/county_map.html` is one file. No CDN, no external stylesheet, no font
download, no `fetch`, no XHR, no websocket. It opens from a USB stick with the
network off and will still work in a year.

Built by:

1. Parsing the Census shapefile with a small reader in `sweep/map.py` rather than
   a GIS stack — the `.shp` format is a header and a run of little-endian doubles,
   and the project has no geopandas dependency.
2. Projecting to the Albers USA composite **in Python**, matching d3-geo's
   arithmetic, so the page ships screen coordinates. No trigonometry in the
   browser. Equal-area, because on a choropleth the visual weight of a county
   should be proportional to its actual size.
3. Simplifying with Ramer-Douglas-Peucker in **projected pixel space** at a 0.45 px
   tolerance. Simplifying in degrees over-smooths the north and under-smooths the
   south; in pixels the tolerance means the same thing in Maine and in Nevada.
   227,746 source points come down to a 0.72 MB page.
4. Emitting inline SVG `<path>` elements with relative integer coordinates on a
   10x grid. The map is in the markup, so it renders with JavaScript disabled.
   JavaScript adds only the hover layer.

### Colour

One blue hue, light to dark, five ordinal steps keyed to days. Not a rainbow, and
not categorical-by-pathway: the pathway is ordinal here — minor NSR is strictly
easier than PSD, which is strictly easier than nonattainment NSR — so an ordered
ramp encodes it correctly and the pathway boundary falls out of the data rather
than being painted on.

Both ramps were run through the palette validator and pass: monotone lightness,
adjacent lightness gap ≥ 0.06, light-end contrast ≥ 2:1 against the surface,
single hue. Dark mode uses its own steps chosen against the dark surface, not an
automatic inversion, with the anchor flipped so "few days" recedes toward the
surface in both modes.

Bins are threshold-based, not quantile-based. Three quarters of all counties land
on the same number, so a quantile scale would paint the map one colour and call
it information.

Two channels beyond the ramp:

- **Grey diagonal hatch** for counties with no attainment data. Never a ramp step.
- **A red outline** on the 77 counties with a hard stop. A moratorium county can
  score 730 days and still be un-permittable; the ramp encodes time, and this
  second channel encodes "time may not be the binding constraint here". It ships
  with a legend label, never as colour alone.

### Accessibility

Every county path is focusable and gives the same readout on keyboard focus as on
hover. The full-answers table lists all 53 distinct answers, so every value on the
map is reachable without a pointer. County and state names go into the DOM with
`textContent`, never string-concatenated HTML.

### Also emitted

- `outputs/county_map.svg` — the same map, static, titled, with its own legend and
  caveat, sized for PNG export. It carries its own caption because an unlabelled
  choropleth posted on its own is a rumour.
- `outputs/county_extremes.md` — the fastest and slowest tables below, for thread
  follow-ups.

One repo note: `.gitignore` currently excludes `outputs/*.html`, so
`outputs/county_map.html` — the artifact the video ends on — will not be
committed unless that line is changed or the file is force-added. The `.svg` and
the `.md` are not excluded. Files written by the sweep and their status:

| File | Committed? |
|---|---|
| `data/county_scores.json` (7.7 MB) | yes |
| `data/county_index.json` (0.5 MB, parsed gazetteer) | yes — keeps the sweep runnable with no download |
| `data/county_scores.progress.jsonl` | yes, and it is what makes a re-run free |
| `data/raw/*` (source zips and HTML) | no, gitignored |
| `outputs/county_map.html` | **no — currently gitignored** |
| `outputs/county_map.svg` | yes |
| `outputs/county_extremes.md` | yes |

---

## 8. Fastest five

Ranking rule: days first, then hard stops, then offset tonnage, then land area
descending. Land area breaks ties because within a tier every county scores
identically and the one a developer would actually look at is the one with room
to put 500 MW on it. It is an arbitrary rule, but a stated arbitrary rule beats
alphabetical order pretending to be a ranking. Tie counts are disclosed.

| Days | County | Pathway | Why |
|---:|---|---|---|
| 609 | Brewster, TX (+233 tied in TX) | Major PSD | TCEQ. Attainment. State air toxics program (+2 mo). TCEQ's 0.75x multiplier is the fastest major-state pathway in the country for onsite generation. |
| 694 | Ashtabula, OH (+87 tied in OH) | Major PSD | Ohio EPA DAPC, 0.95x. Attainment. General permits exist for smaller sources; at 500 MW you are still in full PSD. |
| 730 | Yukon-Koyukuk, AK (+28 tied in AK) | Major PSD | Federal default, no state adjustment. Attainment. This is the base case: 24 months likely, and 2,437 counties sit on exactly this number, 2,281 of them on the federal default. |
| 730 | Nye, NV (+15 tied in NV) | Major PSD | Same base case. Nevada is not one of the eight modelled states, so treat the range as wider than shown. |
| 730 | Harney, OR (+34 tied in OR) | Major PSD | Same base case. |

The fastest county in America is still a two-year major PSD permit. That is the
finding, not a bug in the ranking.

## 9. Slowest five

| Days | County | Pathway | Why |
|---:|---|---|---|
| 1,918 | Sussex, NJ (+20 tied in NJ) | Major nonattainment NSR | Ozone severe-15. NJ DEP at 1.6x, plus the Ozone Transport Region (+3 mo), state toxics (+2 mo), and the EJ law at N.J.S.A. 13:1D-157 that lets the agency deny outright in an overburdened community (+4 mo). Offsets at 1.3:1 are a flagged hard stop. **All 21 New Jersey counties tie here.** This is the Nebius failure mode, and Nebius is trying to build a 400 MW plant under a $17.4B Microsoft deal. |
| 1,568 | Prince William, VA | Major nonattainment NSR | Ozone moderate (DC metro). Virginia DEQ at 1.25x plus state toxics. The differentiator is county posture: the board voted 8-0 on 7 Jul 2026 to deny Dulles Cloud South, days after the Digital Gateway collapsed (+6 mo for hostile zoning). |
| 1,415 | Doña Ana, NM | Major nonattainment NSR | Ozone marginal plus PM10 moderate — two separate offset problems on one parcel. NMED at 1.35x, a small bureau with few reviewers. New Mexico is also the state that blocked the pipeline feeding the 2.45 GW Stargate site, which the air permit timeline does not capture. |
| 1,385 | Loudoun, VA (+7 tied in VA) | Major nonattainment NSR | Ozone moderate. Virginia DEQ at 1.25x plus state toxics. Data Center Alley is the slowest place in the country to add on-site generation that is not New Jersey. DEQ has approved exactly one air permit for a data center campus with on-site gas. |
| 1,278 | Broomfield, CO | Major nonattainment NSR | Ozone severe-15 (Denver Metro / North Front Range). Colorado is not one of the eight modelled states, so this is the federal default timeline on top of a severe-area offset problem, and the county carries an 18-month data center moratorium that took effect 7 July 2026, which is flagged as a hard stop: the air permit timeline is irrelevant until it lifts. |

The gap between the fastest and slowest counties is **1,309 days — three and a
half years — for the same plant.** Nothing about the equipment changes. That is
the number the map exists to show.

---

## 10. Known gaps

1. **Eight states modelled, 44 on the federal default.** Records carry
   `state_modelled` so you can see which is which, but a Colorado or a
   Pennsylvania answer is a federal-minimum estimate, not an agency-behaviour
   estimate. Adding a state is a dictionary entry in `agent/pathway.py` and about
   an hour of reading permit records.
2. **27 hand-entered county posture records.** Everything else has
   `moratorium: false` because nobody looked, not because it was checked. Absence
   of a moratorium record is absence of evidence.
3. **Part-county nonattainment (91 counties).** Flagged, not resolved. Resolving
   it needs a coordinate-level check, which is the parcel run.
4. **No increment, no terrain, no pipeline distance** without `--with-mireye`,
   and even with it those come from one interior point rather than a parcel.
5. **The timeline model is a screen.** Base ranges times a state multiplier plus
   trigger months. It is calibrated against published permit records and
   consultant guidance, not fitted to a dataset of issued permits, because no
   clean public panel of those exists. Treat the ranges as wider than shown.
6. **Nothing here is an applicability determination.** A licensed professional
   signs those and carries the liability. This tells you which conversation you
   are about to have.
