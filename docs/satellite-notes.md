# Satellite verification — engineering note

Stage 5. Is there a hole in the ground yet.

Code: `ingest/satellite.py`. Tool: `verify_construction` in `agent/tools.py`.
Chips and verdicts: `outputs/satellite/`. Run it with
`python -m ingest.satellite` — no keys, no credentials, no extra packages.

Of roughly 90 GW of announced behind-the-meter generation, about 2.2% is
operating and about 60% is announcement-only. The permit engine says what is
legally possible. This says what is physically there.

---

## 1. Mireye first, and what Mireye already answered

Mireye cites Sentinel-2 as one of its own sources, so this started at the
catalog, not at Copernicus. Five fields bear on construction state:

| Field | Source | What it is |
|---|---|---|
| `ndvi_current` | `SENTINEL2_NDVI` | most recent Sentinel-2 NDVI at the queried cell |
| `ndvi_change_5y` | `SENTINEL2_NDVI` | fixed 5-year NDVI change at the cell |
| `lcms_class` | `USFS_LCMS` | life-form class, ~120 m block mode. Includes "Barren or Impervious" |
| `land_use_class` | `USFS_LCMS` | Agriculture / Developed / Forest / Rangeland, ~120 m |
| `tree_canopy_pct` | `USFS_NLCD_TCC` | canopy cover %, ~120 m |

Plus `primary_building_footprint_sqm` and `primary_building_height_m` from
Overture, and `nearest_proposed_generator_status` from EIA-860M, which returns
strings like `"V) UNDER CONSTRUCTION, MORE THAN 50 PERCENT COMPLETE"`.

Those are cheap, cited, and worth calling. **They do not answer the question,
and the reason is measurable rather than theoretical.**

Two live reads, 5 August 2026:

| Point | What is actually there | `ndvi_current` | `ndvi_change_5y` |
|---|---|---:|---:|
| 35.065, -90.075 | the coordinate in `backtest/cases.py` for xAI Colossus 1 | 0.840 | **+0.038** |
| 31.8175, -106.6675 | Project Jupiter, graded and built out since Sept 2025 | 0.058 | **-0.048** |
| 31.870, -106.690 | the coordinate in `backtest/cases.py` for Jupiter — untouched desert | 0.112 | **-0.150** |

Read the last two rows against each other. Mireye's five-year NDVI change is
**three times more negative on the empty desert than on the parcel that was
just built out.** Read the first row on its own: the fastest data center
buildout on record returns 0.84 NDVI and *greener over five years*, because the
single ~10 m cell under an approximate coordinate is a surviving tree.

Neither number is wrong. They are answering a different question.

`lcms_class` has the same shape of problem. At Memphis it returns `'Trees'`
while `land_use_class` returns `'Developed'` — a ~120 m block-mode grid
disagreeing with itself between two taxonomies over the same ground.

### The `/v1/ask` attempt

Before writing a line of Copernicus code, the question went to `/v1/ask` at the
Memphis coordinate, phrased exactly as the product needs it. 10 credits. Their
planner refused, and the refusal is better documentation of the gap than
anything written here:

> "This question requires time-series Sentinel-2 imagery analysis with specific
> scene metadata (acquisition dates, cloud cover, radiometric processing) and
> spatial aggregation (500 m radius averaging) that are outside the Mireye Earth
> catalog. Mireye provides only a single snapshot of NDVI (ndvi_current) at the
> query point, not historical scenes, scene dates, cloud cover, or area-averaged
> composites."

### The field request

Filed. `POST /v1/field-requests`, HTTP 201, **0 credits**.

```
request_id  fr_39331af65eef4400986c0d4c8552dc5e
status      queued, position 6
ready       2026-08-06T11:00:40Z
```

Three sub-asks, all `accepted_new`, `feasibility_class: source_uncertain`.
Their screener's reasons, verbatim:

> **NDVI averaged over a caller-supplied radius on a caller-supplied date, with
> scene id, acquisition datetime and cloud fraction** — "ndvi_current and
> ndvi_change_5y exist but neither supports caller-selectable dates,
> radius-averaging, or scene metadata (acquisition datetime, cloud fraction,
> scene id). This is a time-series imagery query that requires temporal
> selectivity and footprint aggregation not present in the catalog."

> **Delta NDVI between two caller-chosen dates** — "ndvi_change_5y is a fixed
> 5-year window; it does not answer a caller-selected pair of dates."

> **Fraction of the footprint that went from vegetated to bare** — "No candidate
> field measures vegetation-loss transition classes at a threshold-based level
> over a caller-specified radius and date pair."

Full capture: `docs/api-captures/fr5-ndvi-two-date-delta.json`.

So the split is clean. Mireye owns the point sample and it is the right first
call. Everything below is the part it cannot do today.

---

## 2. Which imagery API, and whether it needed a credential

**Element 84 Earth Search STAC for scene search, AWS Open Data
`sentinel-cogs` for pixels. No credential. No account. No signing.**

```
search   POST https://earth-search.aws.element84.com/v1/search
pixels   https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/...
```

Verified live on 5 August 2026: the catalog served scenes through 2026-08-04 at
all three sites, and the COGs answered HTTP range requests with `206 Partial
Content` and no authentication header.

Two alternatives were considered and both were rejected for the same reason:

| Path | Why not |
|---|---|
| Copernicus Data Space OData/STAC | Search is open, asset download needs an OAuth token from a registered account. |
| Microsoft Planetary Computer | Search is open, assets need a SAS token from the signing endpoint. |

Both work. Both add a credential to a repo whose whole point is that a judge
with zero keys can clone it and get the same numbers. Sentinel-2 L2A on AWS is
the same Copernicus product, and it is open.

### No new dependencies

`requirements.txt` is unchanged. No GDAL, no rasterio, no numpy, no Pillow.
Three pieces of arithmetic replace them, and each is small enough to read:

**WGS84 to UTM.** Snyder, USGS Professional Paper 1395, eqs 8-9 to 8-11.
Sub-millimetre inside a zone, four orders of magnitude better than a 10 m pixel
needs. It is the only geo-referencing this module owns; the EPSG code and the
pixel transform both come from the STAC item's `proj:epsg` and
`proj:transform`, so there is no GeoTIFF geokey parsing.

**A windowed COG reader.** A cloud-optimized GeoTIFF puts its header at the
front of the file, so an HTTP range request can pull a 300 x 300 window out of a
220 MB scene. Parse the first IFD, look up the tile offsets and byte counts,
range-GET the one or two tiles the window touches, `zlib.decompress`, undo
predictor 2 with `itertools.accumulate`, copy out the sub-rectangle.
Sentinel-2 L2A COGs are little-endian classic TIFF, one uint16 sample (uint8 for
SCL), Adobe Deflate, predictor 2, 1024 x 1024 tiles at full resolution.
Anything else raises rather than guessing.

**A PNG writer.** IHDR, one zlib-compressed IDAT, IEND, filter type 0.

Five footprints, ten scenes, sixty band reads: **18 seconds warm, about 45
seconds cold.**

### One trap worth writing down

The STAC asset metadata carries `raster:bands.offset: -0.1`. **It is wrong for
these files and applying it destroys the answer.**

Sentinel-2 L2A from processing baseline 04.00 (January 2022) carries
`BOA_ADD_OFFSET = -1000`, so the nominal conversion is `(DN - 1000) / 10000`.
The `sentinel-cogs` COGs are harmonized back to the pre-04.00 convention and the
STAC metadata was not updated to match. Measured at one pixel in South Memphis,
same month, seven consecutive years:

| Scene | STAC `offset` | red DN | NIR DN |
|---|---:|---:|---:|
| 2020-06-14 | 0 | 642 | 3275 |
| 2021-06-14 | 0 | 546 | 3406 |
| 2022-06-29 | -0.1 | 687 | 3306 |
| 2023-06-24 | -0.1 | 664 | 3286 |
| 2024-06-13 | -0.1 | 639 | 3407 |
| 2025-06-23 | -0.1 | 636 | 3462 |

There is no 1000-count step where the baseline changed, so the offset is already
in the bytes. Applying it again drove more than half the visible band negative
and pinned NDVI at 1.0 — which is exactly what the first run of this module did,
and what a chip that came out nearly black looked like. `APPLY_STAC_OFFSET` is a
module constant with that table next to it.

---

## 3. Scene selection

Two windows, one search each, a probe budget rather than a widening loop.
Widening re-sorts to the same nearest-in-time scenes and would re-probe the ones
that just failed.

**Baseline.** `announced_groundbreaking` plus or minus 180 days. Candidates are
bucketed by fortnight and, inside a bucket, the cleaner tile wins. Straight
nearest-in-time picks a hazy scene over a clean one five days further out, and a
hazy baseline is what a false clearing signal looks like.

**Recent.** The last 400 days, newest first, floored at baseline + 30 days.

**Both.** STAC pre-filter at `eo:cloud_cover < 60`, because a 40%-cloudy
110 km tile is very often a clear parcel and the whole-tile number is the wrong
one. Then up to 10 candidates are probed by reading the scene's own SCL band
over the footprint. A scene at or under 2% footprint cloud is taken
immediately; between 2% and 10% it is held as a fallback while the search
continues; above 10%, or below 60% usable pixels, it is rejected and the
rejection is logged with the SCL histogram. If nothing passes,
`insufficient_imagery`.

**Zone boundaries.** A point near a UTM zone edge is served by two MGRS tiles in
two projections. Memphis is 0.075 degrees inside zone 15 and returns both
`15SYU` and `16SBD`. Scenes are filtered to the zone the longitude actually
falls in, and the recent scene is required to share the baseline's `proj:epsg`,
so the two dates sit on one pixel grid and the per-pixel comparison is real.

Every accepted and rejected scene, with its dates and cloud numbers, is in
`scene_selection_log` on the result.

---

## 4. The change metric

Over a circular footprint of `radius_m` (default 500 m), differenced against a
control ring — the annulus from `radius_m` to `3 x radius_m`, on the same two
scenes.

Per pixel, from surface reflectance:

```
NDVI = (NIR - RED) / (NIR + RED)                                  B08, B04
BSI  = ((SWIR16 + RED) - (NIR + BLUE))
     / ((SWIR16 + RED) + (NIR + BLUE))                            B11, B04, B08, B02
brightness = mean(BLUE, GREEN, RED)                               B02, B03, B04
```

B11 and SCL are 20 m and are sampled nearest-neighbour onto the 10 m grid.

A pixel is **disturbed** if either detector fires:

```
A.  NDVI fell by >= 0.15  AND  BSI rose by >= 0.05
B.  NDVI < 0.25 in the recent scene, NDVI did not rise,
    AND brightness rose by >= 0.030
```

A is the ordinary case: vegetated ground that lost vegetation *and* gained
bare-soil signal. Requiring both is the point — NDVI alone moves on drought and
harvest. B exists because arid parcels have no vegetation to lose, so A can never
fire on them; grading fresh caliche or laying a gravel pad raises visible
reflectance.

The reported number is **excess disturbed fraction**: footprint minus ring.

### Why the control ring is the load-bearing part

Same day, same sun angle, same atmospheric correction, same weather, same crop
calendar, adjacent ground. Regional greening and drought move both and cancel.
Construction moves only the footprint.

The cleanest demonstration is the Memphis 122-day window, June to October 2024:

```
footprint disturbed   50.5%
control ring          33.8%
excess                16.7%
```

Two thirds of the raw signal is autumn senescence across South Memphis. Without
the ring this reads as a spectacular construction event. With it, it reads as a
real but moderate one, which is what it was.

Vineland is the same story with the opposite sign. A tilled field clips the east
edge of the footprint and goes from partly green in May 2024 to fully bare in
August 2026 — a crop rotation, unmistakable in the change chip. Footprint 3.3%,
ring 5.3%, excess **-2.1%**. Correctly `no_visible_activity`.

### The ladder

On excess disturbed fraction:

| Excess | Verdict |
|---|---|
| < 5% | `no_visible_activity` |
| 5-15% | `clearing_underway` |
| 15-40% | `earthworks_or_foundations` |
| >= 40% **and** built fraction >= 15% | `structures_present` |
| >= 40% but built fraction < 15% | held at `earthworks_or_foundations`, with the reason stated |

Built fraction is the share of the footprint reading bright (visible reflectance
>= 0.22) and unvegetated (NDVI < 0.15) in the recent scene, which is the
signature of roofs, concrete and new pavement.

These are screening thresholds, not a calibrated classifier. They sit in one
block at the top of `ingest/satellite.py` and are meant to be moved and re-run.

Anything above the cloud gate returns `insufficient_imagery` instead.

---

## 5. What this can and cannot see

**Sentinel-2 is 10 metres per pixel.** One pixel is 100 m^2, about a tennis
court. Visible: land clearing, grading, laydown yards, haul roads, large pads,
new pavement. **Not visible: a turbine foundation, a transformer, a switchyard
bay, a pipe rack, or anything under roughly 20 m.** Nothing in this module's
output is evidence about equipment, and the tool description in `agent/tools.py`
says so to the model as well as to the reader.

**Cloud, snow, drought and crop cycles all move NDVI**, some of them further
than construction does. Cloud is measured over the footprint from the scene's
own SCL band, not taken from the whole-tile `eo:cloud_cover`. Above 10%
footprint cloud, shadow or snow, the answer is `insufficient_imagery`. That is a
correct answer, and it fires: Colossus 1 with `--as-of 2024-08-15` finds a
baseline and no usable recent scene, and refuses rather than reporting a change
from one date.

**The footprint is a circle around a coordinate, not a parcel boundary.** This
is the single largest source of error in practice and section 6 is mostly about
it.

**A brownfield retrofit reads low.** Colossus 1 went into an existing 785,000
sq ft factory. The building itself does not change, and the change mask
correctly leaves it alone; what lights up is everything built around it.

**Dark roofs on bright ground read as no change.** Visible in
`jupiter-construction_2026-07-31_change.png`: the campus is flagged wall to
wall, but the individual building roofs sit inside it as unflagged grey
rectangles. Detector B fires on brightening, and a dark metal roof laid over
bright desert is a brightness *decrease*. The pad around each building is
caught; the building is not. Adding a symmetric "darkened and unvegetated"
detector would catch it and would also catch every new pond, shadow and asphalt
patch in the country, so it is not in.

**`structures_present` does not travel.** The 0.22 brightness gate is an
absolute reflectance threshold. Desert ground is above it before anyone builds
anything — the Santa Teresa control ring reads 34.7% built fraction on
undisturbed shrubland. In humid Memphis the whole scene is darker: the Colossus
1 footprint averages 0.111 visible reflectance *after* the buildout, so only
8.7% of it clears the gate even though the buildings are plainly there. Read the
disturbed fraction, not the label, where they disagree.

**This corroborates. It does not prove.** A cleared pad is not a permitted
plant — Project Jupiter has a graded campus and had its pipeline right-of-way
denied twice. An empty parcel is not proof a project is dead.

---

## 6. The three cases

Run at `--as-of 2026-08-05`. Full JSON in `outputs/satellite/results.json`,
chips in `outputs/satellite/`.

Two of the three published coordinates in `backtest/cases.py` are wrong, and
both are run here against a corrected one, because the pairs say more about the
method than the verdicts do.

| Footprint | Verdict | Excess | Footprint dNDVI | Ring dNDVI | Scenes |
|---|---|---:|---:|---:|---|
| Jupiter — construction found on the NM-136 corridor | `structures_present` | **+61.3%** | -0.108 | -0.042 | 2025-08-25 -> 2026-07-31 |
| Jupiter — published coordinate | `no_visible_activity` | -0.9% | +0.009 | -0.010 | 2025-08-25 -> 2026-07-31 |
| Vineland — Nebius / DataOne | `no_visible_activity` | -2.1% | +0.048 | +0.070 | 2024-06-15 -> 2026-08-04 |
| Memphis — Colossus 1, geocoded address | `earthworks_or_foundations` | **+23.8%** | -0.153 | +0.013 | 2024-06-13 -> 2026-07-28 |
| Memphis — published coordinate | `no_visible_activity` | -2.6% | -0.022 | -0.032 | 2024-06-13 -> 2026-07-18 |

All ten scenes came back at or under 0.4% footprint cloud.

### Memphis — the positive control. The method works.

`backtest/cases.py` carries 35.065, -90.075, labelled "South Memphis,
approximate". That point is **7.3 km east of the site**, in a residential
neighbourhood off the rail yard, and this module returns `no_visible_activity`
there — correctly, because nothing was built there.

Colossus 1 is the former Electrolux plant, 3231 Paul R Lowry Rd, Memphis TN
38109. Geocoded through Mireye at 0.95 confidence, rooftop grade, to
**35.060553, -90.155133**.

At that coordinate the method sees it. 35.2% of the 201 ha footprint disturbed
against 11.5% for the surrounding 1,598 ha, footprint NDVI down 0.153 while the
ring went *up* 0.013, BSI up 0.109 against -0.010. `earthworks_or_foundations`.

`outputs/satellite/memphis-colossus1_2026-07-28_change.png` is the picture that
settles it. The mask lands on the ring of new pads, the turbine yard and the
laydown around the existing building, is tight to the site, does not bleed into
the surrounding fields, and correctly leaves the pre-existing factory roof
unflagged.

It also works on the short window. June to October 2024 — the actual 122-day
buildout — returns `earthworks_or_foundations` at 16.7% excess. So the method
detects this at the timescale that matters, not only in a two-year retrospective.

**The method is not wrong. The coordinate was.**

Two things it does not do. It does not reach `structures_present` here, because
the roofs are dark; and it says `earthworks_or_foundations` about a site that
by July 2026 has finished buildings, which is the honest limit of a 10 m
spectral index.

### Santa Teresa — the interesting one

The published coordinate 31.870, -106.690 reads `no_visible_activity`: -0.9%
excess, footprint NDVI +0.009 against the ring's -0.010. Flat nothing.

That answer would have been reported as fact if the Memphis result had not
already shown what an approximate coordinate does. No coordinate for Project
Jupiter is public — Baxtel withholds the street address — so instead of looking
it up, the module went and found it. The change metric was run over a 15 km
window centred on the NM-136 corridor and the 300 m blocks were ranked by
disturbed-pixel count. 103 blocks came back over 250 disturbed pixels out of
900, clustered at **31.8175, -106.6675**, 6.2 km south-southeast of the
published point.

Mireye then identified the ground: Doña Ana County, 1.6 km off the Pete V.
Domenici International Highway, 1.1 km from a substation, 3.3 km from an
EIA-860M generator reported as `"V) UNDER CONSTRUCTION, MORE THAN 50 PERCENT
COMPLETE"`, 150 MW. That is consistent with the reported Project Jupiter site —
1,400 acres along NM-136 toward the Santa Teresa Port of Entry, construction
begun September 2025 — and it is not a confirmed parcel ID.

At that footprint: **61.3% excess disturbed**, brightness up 0.059 against the
ring's 0.008, 81.1% of the footprint bright and unvegetated.
`structures_present`. In August 2025 it was bare desert. The chips are
`jupiter-construction_2025-08-25_baseline.png` and
`jupiter-construction_2026-07-31_recent.png`.

**So the plain reading of "Project Jupiter has no hole in the ground" is wrong.**
There is a very large hole in the ground and a lot of concrete. What Jupiter
lost was the gas — the pipeline right-of-way denied 20 March and again 14 July
2026, and the simple-cycle turbine applications withdrawn 27 April 2026 for
Bloom fuel cells. Which is the whole thesis stated more precisely than the
product usually manages: **the dirt is not the constraint. The permit is.** A
campus can be poured and still have no legal way to make power on it.

### Vineland — a clean negative

`no_visible_activity`, -2.1% excess, on 78 ha over 26 months. Footprint NDVI
went *up* 0.048, the ring up 0.070, canopy intact. Mireye agrees from a
different direction: `lcms_class = 'Trees'`, `tree_canopy_pct = 63`,
`land_use_class = 'Forest'`, `ndvi_current = 0.857`.

The change chip flags one block of bare field on the east edge. It is a crop
rotation and the ring nets it out. This is the case the ring was built for.

3.9 months remain to the announced 2026 energization on a parcel nobody has
broken. NJDEP never issued air permit PCP250002, and Nebius replaced the engines
with 328 MW of Bloom fuel cells on 20 May 2026. The imagery and the permit
record say the same thing by different routes.

---

## 7. What would be needed to do this properly

**Higher-resolution optical.** Planet at 3 m daily, Airbus or Maxar at 30-50 cm
on tasking. At 50 cm you can count turbine trailers, see a transformer pad,
read a switchyard, and tell a finished building from a slab. That is the
difference between "the surface is built" and "there are 35 turbines on site,"
which is the claim a fund actually wants. It is also the difference between free
and roughly $10-25 per km^2 per pass.

**SAR.** Sentinel-1 C-band, also free on the same open-data path, and it sees
through cloud, at night, every 6-12 days. Two things it does better than
anything optical here: it never returns `insufficient_imagery` for weather, and
interferometric coherence loss is a direct measure of ground disturbance — a
graded pad decorrelates hard, which is a physically cleaner signal than a
vegetation index. The obvious next build, and the reason the cloud refusal in
this module is a stated limitation rather than an accepted one.

**Parcel boundaries instead of circles.** Mireye already has
`parcel_boundary_geojson`. It costs 300 credits per location (the
per-record-licensed parcel group), and this module has not spent them. Running
the metric over the real polygon instead of a circle would remove the largest
error source in section 6 outright.

**Somewhere to put the coordinates.** Two of three published coordinates in this
repo's own backtest are kilometres from the site, and the failure is silent —
an empty circle over the wrong ground looks exactly like an empty circle over
the right ground. Every verdict in `outputs/satellite/results.json` carries its
footprint centre so it can be checked, and the tool result carries a
`geocode_caveat` when the site resolved below 0.9 confidence. That is a warning,
not a fix.

**A panel, not five footprints.** Five footprints is a demonstration. The claim
in the first line of this note — 2.2% operating, 60% announcement-only — needs
this run against a tracked universe of projects on a schedule, with the verdicts
stored per date. That is the same point-in-time-panel problem the README already
admits to for the permit backtest.

---

## 8. Cost

**Mireye: 87 credits.** 48 for the imagery-derived field sweep at the three
backtest coordinates, 10 for the `/v1/ask` attempt, 1 for the Colossus 1
address geocode, 28 for identifying the Santa Teresa cluster. The field request
cost 0 — it bills the plan's allowance, not the credit pool.

**Imagery: free.** Copernicus Sentinel-2 L2A is open data and the AWS mirror is
public. Zero credentials, zero cost, per project, forever.

Every COG window, every STAC search and every Mireye response is cached through
`providers/cache.py`, so a re-run costs nothing and the chips reproduce byte for
byte.

---

## 9. Degradation

The tool never raises into the agent loop. No network, no scenes, an unreadable
COG, a snowed-in parcel and a nonsense coordinate all return
`insufficient_imagery` with the reason attached. A screening tool that crashes
the run is worse than one that says it does not know.

An unreachable catalog and a cloudy sky are different answers and the output
says which:

```
$ python -m ingest.satellite   # with the catalog unreachable
insufficient_imagery — The Sentinel-2 catalog could not be reached, so no
imagery was read and no construction claim is made either way. This needs no
credential; if it is failing, it is the network. See scene_selection_log.
```

73 tests pass, no keys required.
