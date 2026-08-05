# Mireye API — engineering notes

Written 5 Aug 2026 from the docs, then **verified against the live API the same day**
with a real Loudoun County, VA data center address. Nothing in this file is a guess any
more. Where their docs contradicted themselves, measurement settled it.

- Test site: **21571 Beaumeade Cir, Ashburn, VA 20147** — Loudoun County, the densest
  data center market in the world, and (as it turns out) ozone nonattainment.
- Raw request/response captures: **`docs/api-captures/`**, 27 files, one per call.
- **Total verification spend: 884 credits of the 25,000 monthly Build allowance**
  (~$0.88), across 25 billable calls. Zero 429s, zero 402s.
- The credit model in `providers/mireye.py` reproduces the account's own
  `credits.used` figure **exactly** — 884 modelled, 884 billed.

Sources, all fetched 5 Aug 2026:

- `https://docs.mireye.ai/llms.txt` — the doc index. Every page is served as raw
  markdown at `<page>.md`, so the whole reference is scriptable. Do that first next time.
- `https://api.mireye.com/v1/openapi.json` — OpenAPI 3.1, `version: 0.14.0`.
- `https://api.mireye.com/v1/meta/fields` — **public, no token**. 304 fields, 15 presets,
  the live preset expansions, the US envelope.
- `https://api.mireye.com/v1/meta/plans` — **public, no token**. Real credit prices and
  real per-plan rate limits. This is the single most useful undocumented-in-prose endpoint.
- `https://www.mireye.com/templates` and the nine `/templates/<slug>` pages.

**Docs are readable without auth.** No login wall anywhere. Only the data endpoints
(`/v1/ask`, `/v1/fetch`, `/v1/geocode`, `/v1/lookup`, `/v1/proximity`,
`/v1/field-requests`) need a bearer token.

---

## 1. Base URL and auth — VERIFIED LIVE

```
https://api.mireye.com
Authorization: Bearer <token>
content-type: application/json
```

One header. No API-key query params, no custom headers. **Tested, not assumed.** The
key in `.env` is a JWT (291 chars, `eyJhbGci…`, two dots) and it goes in the standard
`Authorization: Bearer` header — there is no custom header variant. `MIREYE_BASE_URL`
in `.env` is `https://api.mireye.com`, which agrees with the docs.

The cheapest possible auth check is `GET /v1/users/me/usage` — it needs the token,
costs nothing, and tells you the plan and the credit balance in one shot:

```json
{
  "period": {"start": "2026-08-01", "end": "2026-08-31", "resets_at": "2026-09-01T00:00:00+00:00"},
  "plan": {"id": "build", "name": "Build", "price_usd_month": 19,
           "credits_included": 25000, "rpm": 60, "field_requests_included": 1},
  "credits": {"used": 884, "included": 25000, "remaining": 24116,
              "overage": 0, "overage_rate_usd_per_1k": 1.0},
  "refusals_24h": {"throttled_429s": 0, "blocked_402s": 0, "last_refusal_at": null,
                   "window_hours": 24}
}
```

**Our account is on the `build` plan**: 25,000 credits/month, **60 rpm**, and
**1 included field request**. The `BUILD` signup code did what the challenge said.

`GET /v1/users/me` also works and returns the account profile.

**`credits.used` is eventually consistent, not a live meter.** It lagged reads by tens
of seconds and at one point read *lower* than an earlier poll (160 then 115 then 536).
Do not try to price a single call by polling before and after it. Reconcile at the end
of a run — over the whole session it settled on exactly the right number.

Tokens are JWTs with a 90-day default life, created in account settings at
`https://www.mireye.com`. The plaintext is shown at creation and can be re-revealed
from the dashboard while the token is still `recoverable`.

Three ways to get one:

1. Dashboard API token — what our scripts use. `MIREYE_API_KEY` in `.env`.
2. `mireye-mcp login` device flow — stores a token at
   `~/.config/mireye-mcp/credentials.json`, bound to the `MIREYE_BASE_URL` it was
   minted against.
3. OAuth 2.1 + PKCE against the hosted MCP endpoint. **These tokens are scoped to MCP
   tool calls and are explicitly not accepted on `/v1/*`.** Do not try to reuse the MCP
   token for the HTTP client.

Auth errors: `auth_missing` / `auth_malformed` / `auth_invalid` / `auth_expired` /
`auth_revoked` (401), `email_unverified` / `user_disabled` / `auth_method_not_allowed`
(403), `rate_limited` (429, honour `Retry-After`).

One doc inconsistency: the authentication page lists only `/v1/ask` and `/v1/fetch`
under "token required". `/v1/lookup`, `/v1/geocode`, `/v1/proximity` and
`/v1/field-requests` are obviously also protected — every example on their own pages
sends the header. Treat the auth page as stale, not as a claim those endpoints are open.

---

## 2. Endpoints — VERIFIED

| Method | Path | What it is |
|---|---|---|
| POST | `/v1/ask` | Planner LLM picks fields, fetches, synthesiser writes a cited answer |
| POST | `/v1/ask/stream` | Same body, SSE (`delta` / `final` / `error` frames) |
| POST | `/v1/fetch` | Deterministic per-field fetch with provenance |
| POST | `/v1/fetch/batch` | Same field selection over up to **25 locations** |
| POST | `/v1/runs` | Async job wrapper; today only `kind: "fetch_batch"` |
| GET | `/v1/runs/{run_id}` | Poll a run. `/events` for SSE |
| POST | `/v1/geocode` | Address → coordinate + quality of that coordinate |
| POST | `/v1/lookup` | Address / `"lat,lng"` / APN → canonical join keys (+ parcel) |
| POST | `/v1/proximity` | `distance` / `nearest` / `screen` / `labor_shed` |
| POST | `/v1/field-requests` | Ask for a field that isn't in the catalog |
| GET | `/v1/field-requests/{request_id}` | Poll a field request |
| GET | `/v1/meta/fields` | Field + preset catalog. **Public** |
| GET | `/v1/meta/plans` | Credit prices, plan limits. **Public** |
| GET | `/v1/users/me/usage` | Credits used, `field_requests_included`. Needs the token |
| — | `/mcp` | Hosted MCP endpoint, OAuth 2.1 |

Note the brief's `/v1/lookup` framing was right but its cost model was not — see §6.

`/v1/proximity` was called `/v1/compute` in early design docs. Nothing ever served
under that path; ignore it.

---

## 3. Presets — the real names, VERIFIED

Fifteen. These are the exact enum values `/v1/fetch` accepts:

```
terrain  flood_risk  wildfire_underwrite  land_cover  site_selection
building_lookup  points_of_interest  utilities  boundaries  solar_siting
wind_siting  storage_siting  data_center_siting  grid_interconnect  natural_hazard
```

Live expansion sizes from `/v1/meta/fields` (5 Aug 2026, catalog `0.14.0`):

| Preset | Fields |
|---|---|
| `data_center_siting` | **106** |
| `site_selection` | 72 |
| `grid_interconnect` | 29 |
| `utilities` | 27 |
| `solar_siting` / `wind_siting` | 26 |
| `points_of_interest` | 23 |
| `storage_siting` | 19 |
| `natural_hazard` | 17 |
| `flood_risk` | 13 |
| `terrain` / `wildfire_underwrite` | 6 |
| `land_cover` | 5 |
| `boundaries` / `building_lookup` | 4 |

The brief guessed "data_center_siting — 90 fields" and "site_selection — 54". Both are
low; they are 106 and 72. Also the brief's `wildfire` is really `wildfire_underwrite`,
and `boundaries` is a 4-field jurisdiction preset, not the parcel-boundary preset it
sounds like — parcel geometry lives in `site_selection` / the `parcel_*` fields.

### The 50-field cap, settled by measurement

`/v1/fetch` returns `400 fields_too_many` when the "resolved field set
(post-preset-expansion) exceeds 50" — which would make `data_center_siting` (106)
impossible. Two other pages say the opposite and are more specific:

> "50 explicit fields max, **presets exempt**." — `/api-reference/fetch-batch`

> "one request, capped at 50 explicitly-named fields (**preset members are exempt from
> that cap**)" — the `land-read` starter skill

**Settled: presets are exempt. The errors page is stale.**
`{"lat": 39.022183, "lng": -77.453578, "preset": "data_center_siting"}` returned
**HTTP 200 with all 106 fields** in 8.9 s
(`docs/api-captures/05-fetch-preset-data_center_siting.json`). `providers/mireye.py`
keeps a chunking fallback on `400 fields_too_many` anyway — it costs nothing until it
fires, and it is the same credits either way.

The explicit-field cap is real. `fields_unknown` is also real and is a hard 400 that
kills the whole request:

```json
{"detail": {"error": "fields_unknown",
            "message": "Unknown field names: ['totally_not_a_field']",
            "fields_unknown": ["totally_not_a_field"]}}
```

Note it names the offenders in a `fields_unknown` array, so a client could self-heal.
Ours validates against the catalog first instead.

`preset` + `fields` in one body is legal and shipped in two of their own starter skills.

---

## 4. Response shapes — VERIFIED (pasted from their docs)

### `/v1/fetch`

```json
{
  "lat": 40.7128,
  "lng": -74.006,
  "fetched_at": "2026-06-12T07:27:35.840477+00:00",
  "fields": {
    "elevation": {
      "value": 13.150006294,
      "unit": "meters",
      "source": "USGS_EPQS",
      "source_url": "https://epqs.nationalmap.gov/v1/json?x=-74.006&y=40.7128&wkid=4326&units=Meters",
      "confidence": "high",
      "fetched_at": "2026-06-12T07:27:35.826959+00:00",
      "dataset_vintage": "3DEP dynamic service",
      "ttl_seconds": 31536000,
      "notes": null,
      "status": "ok"
    }
  },
  "partial_failures": [],
  "resolved_location": {"lat": 40.7128, "lng": -74.006, "source": "coordinate"}
}
```

Address requests add a `geocode` block:

```json
"geocode": {
  "accuracy": 1.0,
  "accuracy_type": "rooftop",
  "match_type": "building_centroid",
  "normalized_address": "350 5th Ave, New York, NY 10118",
  "provider": "geocodio",
  "source": "City of New York",
  "parcel_grade": true,
  "precision_note": null
}
```

**`confidence` is a bucket string, not a float** — `high` / `medium` / `low` /
`unknown`. This matters because `providers/base.py` types `Fact.confidence` as
`float | None`. We translate through one explicit table
(`high→0.9, medium→0.6, low→0.3, unknown→None`) and keep the raw bucket verbatim in
`Fact.note`. That is a stated translation, not an invented score, and it is reversible.

Every requested field is always present in `fields` with a tri-state `status`:

- `ok` — a real value.
- `absent` — valid no-data; the source answered "nothing here".
- `failed` — `value: null`, plus `error` (string) and `retryable` (bool). Also
  duplicated into the flat `partial_failures` array.

We mirror that: `absent` and `failed` fields become `Fact`s with `value=None` and the
status in `note`, so nothing is silently dropped and `FactSet.provenance()` still
covers every field we asked for.

A `failed` entry with `retryable: true` is a timeout or a metered quota reset.
`retryable: false` means a structured upstream refusal — don't retry it.

### `/v1/geocode`

```json
{
  "lat": 40.748377,
  "lng": -73.984854,
  "accuracy": 1.0,
  "accuracy_type": "rooftop",
  "match_type": "building_centroid",
  "normalized_address": "350 5th Ave, New York, NY 10118",
  "provider": "geocodio",
  "source": "City of New York"
}
```

`accuracy` is a 0–1 float (provider similarity: did it match the *right* address).
`accuracy_type` is a separate axis (how precisely the match was *placed*):

| `accuracy_type` | Grade | Safe for parcel work? |
|---|---|---|
| `rooftop`, `nearest_rooftop_match` | parcel | yes |
| `point`, `range_interpolation`, `intersection`, `street_center` | street | no |
| `place`, `county`, `state` | centroid | rejected server-side |

`range_interpolation` carries ~**2,872 m** error at the 95th percentile in rural areas.
Their own measurement against NC parcel polygons: every `rooftop` result landed inside
its own parcel; interpolated results landed outside, one by 1.1 km. For a permit screen
that is a different county's air district. So we refuse anything below parcel grade.

Their gates, which we inherit for free: below 0.8 similarity → refused; centroid-grade →
`404 address_too_coarse`; non-US → refused. `provider: "census"` means the primary
timed out and the free lower-precision fallback answered — treat as degraded.

Known hole they document honestly: Puerto Rico and Guam can return a *different*
address at rooftop tier and 0.99 accuracy. Compare `normalized_address` against input.

### `/v1/lookup`

This is the one we actually use to resolve, because it returns a real `confidence` float
*and* every join key the pathway engine needs in one call.

```json
{
  "disposition": "resolved",
  "lat": 30.199699, "lng": -97.496411,
  "resolved_address": "480 BERDOLL LN, CEDAR CREEK, TX 78612",
  "resolved_location": {"lat": 30.199699, "lng": -97.496411, "source": "address"},
  "county_fips": "48021", "county": "Bastrop County",
  "tract_geoid": "48021950400", "state_fips": "48", "state": "Texas",
  "block_group_geoid": "480219504001", "block_geoid": "480219504001000",
  "congressional_district": "TX-27",
  "cbsa_name": "Austin-Round Rock-San Marcos, TX Metro Area", "cbsa_code": "12420",
  "elevation_m": 152.3,
  "fema_flood_zone": "X", "within_floodplain": false, "coastal_high_hazard": false,
  "county_market": {"population": 106822, "population_growth_1yr_pct": 4.1, "...": "..."},
  "in_opportunity_zone": false, "opportunity_zone_tract_geoid": null,
  "timezone": "America/Chicago",
  "parcel": {"parcel_id": "R123456", "apn": "...", "area_m2": 20234.5,
             "owner": "PECAN GROVE FARMS #1 LLC", "zoning": "AG",
             "land_use": "Agricultural", "assessed_value_usd": 185000,
             "last_sale_date": "2019-03-14", "last_sale_price_usd": 210000,
             "match_type": "exact", "match_distance_m": 4.2, "source": "REGRID"},
  "match_method": "geocode_rooftop+point_in_parcel",
  "confidence": 0.95
}
```

Three dispositions, and they are the whole reason to prefer this over `/v1/geocode`:

- `resolved` — coordinate, plus a parcel when the geocode cleared parcel grade.
- `clarify` — genuinely ambiguous. Returns up to 3 `candidates`, never a silent pick.
- `no_match` — honest failure with a `reason` and often a `hint`.

`state` is the **full state name** ("Texas"), not the two-letter code
`pathway.SiteContext.state` wants. We convert. `county` is "Bastrop County", not
"Bastrop, TX". Both are easy to get wrong.

A parcel-lookup failure never demotes `disposition`; it comes back as
`parcel_unavailable: true` + `parcel_unavailable_reason`. APN-only input is
`no_match` / `apn_not_supported_in_v1`. A swapped lat/lng is a hard `422
resolve_coord_bounds`, deliberately — never a nearest match.

**`/v1/lookup` carries no per-field provenance.** One top-level `confidence` describes
the *resolution*, not `elevation_m` or `fema_flood_zone`. So in `lookup()` we attach
`source` from the documented source list (3DEP/EPQS for elevation, FEMA NFHL for flood,
Census Geocoder for the geoids, Regrid for the parcel, Census PEP/BPS/ACS + FHFA + BLS
QCEW for `county_market`) and leave per-fact `confidence` **None**. The resolution
confidence rides on `Location.confidence` where it belongs.

### `/v1/proximity`

Four ops on one body, discriminated on `op`: `distance`, `nearest`, `screen`,
`labor_shed`.

`nearest` — the only one we use — takes a curated `set`, and there are exactly **six**:

| `set` | Backing data | Default filter |
|---|---|---|
| `@airports` | FAA NASR (28-day cycle) | public-use airports only |
| `@substations` | EIA/HIFLD | `max_voltage_kv >= 115`; unpublished voltage excluded |
| `@power_plants` | EIA | none |
| `@rail` | BTS NTAD | none |
| `@ports` | BTS maritime | none |
| `@urban_areas` | Census TIGER | none |

```json
{"op": "nearest", "origin": "40.630973,-73.97228", "set": "@airports",
 "n": 3, "filters": null, "mode": "driving"}
```

```json
{
  "op": "nearest",
  "origin": {"query": "40.63,-73.97", "lat": 40.63, "lng": -73.97, "error": null},
  "candidates": [
    {"name": "JOHN F KENNEDY INTL", "lat": 40.6413, "lng": -73.7781,
     "attributes": {"facility_type": "airport", "use": "PU"},
     "distance_miles": 13.8, "distance_km": 22.2,
     "duration_seconds": 1650, "duration_minutes": 27.5}
  ],
  "applied_filters": null,
  "paid_driving_calcs": 15,
  "notes": ["coverage: US + Canada", "durations reflect typical traffic, not real-time"]
}
```

**There is no `@transmission`, no `@gas_pipeline`, no `@school`, no `@hospital`.** The
brief assumed proximity covered the whole power layer. It does not. Those distances are
`/v1/fetch` catalog fields instead — `nearest_transmission_line_distance_m`,
`nearest_gas_pipeline_distance_m`, `nearest_school_distance_m`,
`nearest_hospital_distance_m`. So `MireyeProvider.proximity()` routes each
`PROXIMITY_TARGETS` name to whichever surface actually answers it, and sets
`ProximityResult.by_road` accordingly. Fetch-backed distances are geodesic, always.

Other things that bite:

- `mode: "straightline"` never calls the router: free geodesic, `duration_*` null.
  Search radius on `nearest` is **fixed at 160 km** and not configurable.
- A locator is a `"lat,lng"` string or a US street address. **Never a place name.**
  `"SFO airport"` matches the town of Airport, NC at confidence 1.0; only their accuracy
  gate stops it. Always pass coordinates — they skip the gate and cost nothing.
- The snap guard: a driven leg shorter than 95% of the great-circle distance is a
  provider snapping an unreachable point to a road. Distance stays, durations are
  nulled, `flag: "unreachable_or_snapped"`. Never present that distance as drivable.
- A `200` can be missing rows you asked for. Read `notes` and the
  `resolved_*` arrays before summarising.
- `applied_filters` echoes what *you* sent, not the default that ran.

### `/v1/ask`

Body: `{lat, lng | address, question, include_trace?}`. Planner is Claude Haiku 4.5,
synthesiser Claude Sonnet 4.6. Response carries `answer`, a `confidence` bucket
(`high`/`medium`/`low`), `citations` grouped by source, `fields_used`, `data_gaps`, and
`trace` when asked — including `planner_reasoning`, `fields_requested` and
`preset_expanded`, which is exactly the "returns the plan it ran so you can replay it"
the brief wanted.

Two constraints the brief did not know:

- **The planner is capped at 15 fields per question**, and "preset expansions larger
  than the cap, e.g. `site_selection` or `data_center_siting`, are truncated to the
  first 15 fields of the preset." So `/v1/ask` is not a shortcut to a full site screen.
  Use it for the messy edges only, exactly as the brief says, and use `/v1/fetch` for
  anything the pathway engine depends on.
- **Set the client timeout to at least 120 s.** End-to-end is 6–20 s typical, ~90 s
  tail, hard-bounded at 110 s then `504 ask_timeout`. A 30 s client timeout aborts
  requests that keep running and keep billing on the server.

Confidence is auto-downgraded one bucket if >30% of planner-selected fields came back
null. That is a real signal — don't paper over it.

---

## 5. Errors and retries — VERIFIED

Uniform shape:

```json
{"detail": {"error": "coord_out_of_bounds", "message": "lat=10.0 outside US envelope [18.0, 72.0]", "retryable": false}}
```

Every response except unhandled 500s carries `X-Request-ID`, and the server echoes an
`X-Request-ID` you send. We set one per call so a support thread is one grep.

**Honour `detail.retryable`, not the status code.** A `502 ask_upstream_error` caused by
an upstream 4xx will never succeed on retry. Retryable failures carry `Retry-After`;
non-retryable ones deliberately do not.

Codes that matter to us:

| Code | HTTP | Retry | Note |
|---|---|---|---|
| `coord_out_of_bounds` | 400 | no | envelope is `lat ∈ [18,72]`, `lng ∈ [-180,-65]` |
| `fields_unknown` | 400 | no | one bad name kills the call — validate against the catalog first |
| `fields_too_many` | 400 | no | see §3 |
| `address_too_coarse` / `address_not_found` | 404 | no | a real refusal, cache it |
| `geocode_busy` | 429 | yes | `Retry-After: 2` |
| `resolve_busy` | 429 | yes | `Retry-After: 3` |
| `proximity_busy` | 429 | yes | `Retry-After: 5`, never billed |
| `ask_busy` / `ask_upstream_rate_limited` | 429 | yes | |
| `geocode_upstream_error` | 502 | yes | `Retry-After: 2` |
| `geocode_timeout` | 504 | yes | `Retry-After: 5` |
| `ask_timeout` | 504 | yes | 110 s deadline |
| `geocode_forbidden` | 503 | yes | their spend cap, not our key. `Retry-After: 3600` |
| `geocodio_distance_budget_exhausted` | 503 | yes | **billed anyway.** `Retry-After: 3600`. Do not retry in a loop |

That last one is the only place where a failure is billed for work that never happened,
and they say so explicitly. Our client refuses to retry it inside the backoff loop.

---

## 6. Credits and rate limits — MEASURED LIVE

This is the part the brief was most wrong about, and it changes the sweep budget.

### What each call type actually cost

Measured by reconciling `credits.used` across the whole session. 25 billable calls,
**884 credits**, and the model in `providers/mireye.py` predicts 884. Exact.

| Call | Measured credits |
|---|---|
| `POST /v1/geocode` | **1** |
| `POST /v1/lookup`, `include_parcel: false` | **1** |
| `POST /v1/lookup`, `include_parcel: true` | **300** |
| `POST /v1/fetch`, 1 field | **1** |
| `POST /v1/fetch`, `preset: terrain` (6 fields) | **6** |
| `POST /v1/fetch`, `preset: utilities` (27) | **27** |
| `POST /v1/fetch`, `preset: data_center_siting` (106) | **106** |
| `POST /v1/fetch`, `preset: terrain` + 2 extra fields (8) | **8** |
| `POST /v1/fetch`, 2 parcel-group fields, by address | **300** |
| `POST /v1/fetch/batch`, 2 fields × 2 valid locations | **4** |
| `POST /v1/ask` | **10** |
| `POST /v1/proximity` `nearest`, straightline | **2** |
| `POST /v1/proximity` `nearest` `n:1`, driving | **60** |
| `POST /v1/field-requests` (any disposition) | **0** — billed against the plan allowance |
| Any 400 / 404 / 422 / 503 we triggered | **0** |

Two corrections to what the docs implied:

**`/v1/proximity` echoes `credits_charged` in the response body.** It is not documented
in prose but it is there on every response, next to `paid_driving_calcs`. The straight-
line call reported `"paid_driving_calcs": 0, "credits_charged": 2`; the driving call
reported `"paid_driving_calcs": 5, "credits_charged": 60`. That confirms
`max(floor, 12 × calcs)` and it means proximity spend can be read rather than modelled.
No other endpoint reports a credit figure.

**Parcel-group fields are not also billed per field.** A fetch of exactly
`["parcel_id", "parcel_area_m2"]` — both parcel-group members — billed **300, not 302**.
The rule is: `resolve_credits` once per location, plus 1 credit for each *non*-parcel
field in the same request. So `site_selection` (72 fields, 9 of them parcel-group) is
`63 + 300 = 363` credits per location — not 72, and not the 372 I first computed.
`data_center_siting` has no parcel-group member and bills a flat 106.

The address on a fetch-by-address call billed nothing on top, because the same address
had already been geocoded in this session and geocode results cache for 30 days.

```json
{"costs": {
  "ask": 10, "ask_site": 10, "fetch_per_field": 1, "geocode": 1,
  "proximity_per_driving_calc": 12, "proximity_per_address_locator": 1,
  "proximity_distance_min": 2, "proximity_nearest_min": 2,
  "proximity_screen_min": 5, "proximity_labor_shed_min": 25,
  "resolve": null, "site_register": 10
}, "overage_rate_usd_per_1k": 1.0}
```

Plans:

| Plan | $/mo | Credits | Field requests | **rpm** | `resolve_credits` |
|---|---|---|---|---|---|
| free | 0 | 5,000 | 0 (+1 signup grant) | **20** | 300 |
| build | 19 | 25,000 | 1 | **60** | 300 |
| growth | 99 | 120,000 | 3 | **300** | 300 |
| scale | 499 | 750,000 | 15 | **600** | 150 |
| market | 4,000 | 10,000,000 | 999 | **1000** | 150 |

Overage is $1.00 per 1,000 credits on every tier. The contest prizes are quoted in
credits at exactly that rate ($2,500 = 2.5M credits), which confirms it.

### The two cost traps

**1. Parcel fields cost 300 credits, once per location.** From `/v1/meta/plans`:

> "These fields come from per-record-licensed county parcel data. A request that
> includes ANY of them bills `plan.resolve_credits` once per location — once, not per
> field — on top of `fetch_per_field` for the other fields in the request."

The parcel group is: `parcel_id`, `parcel_apn`, `parcel_address`, `parcel_area_m2`,
`parcel_owner`, `parcel_zoning`, `parcel_geometry_wkt`, `parcel_boundary_geojson`,
`parcel_data_source`, `parcel_match_type`, `parcel_match_distance_m`,
`parcel_match_radius_m`, `wetland_acres_on_parcel`, `wetland_fraction_of_parcel`,
`developable_acres_proxy`, `onsite_solar_potential_mwac_low/high`.

**`site_selection` contains nine of them.** So `preset: "site_selection"` is
72 + 300 = **372 credits per location**, not 72. `data_center_siting` contains none, so
it is 106 credits flat. Same trap on `/v1/lookup`: with `include_parcel` (the default)
it bills `resolve_credits` = 300; without it, it bills the geocode price = 1.

`MireyeProvider` therefore defaults `include_parcel=False` on resolve, and `fetch()`
warns and counts 300 whenever a parcel-group field is in the request.

**2. Proximity driving mode is 12 credits per driving calc.**

```
credits = max(op_floor, 12 × paid_driving_calcs) + 1 × address-form locators
```

`nearest` bills `paid_driving_calcs = min(25, n × 5)`, priced from the *request shape*,
before anything resolves. So one `nearest` with `n: 1` and `mode: "driving"` is
`max(2, 12 × 5)` = **60 credits**. The same call in `mode: "straightline"` is **2**.
Every response echoes `paid_driving_calcs`, so we read actual spend rather than guess.

Because of that, `MireyeProvider` defaults to `proximity_mode="straightline"` and makes
driving an explicit opt-in per call. Sweeps run geodesic; the single filmed project
screen can afford by-road.

### Rewritten credit budget for our runs

| Run | Composition | Credits |
|---|---|---|
| Per-project deep screen | `data_center_siting` (106) + `terrain` (6) + `utilities` (27) + resolve (1) + ~4 fetch-backed proximity fields + 1 `ask` (10) | **~155** |
| …with by-road proximity on 3 targets | + 3 × 60 | ~335 |
| Alternate-site search, 25 candidate parcels | 25 × ~110 (`data_center_siting` + resolve) | **~2,800** |
| National county sweep, 3,140 counties | 3,140 × ~110 | **~345,000** |
| 3,000 tracked projects, one pass | 3,000 × ~155 | **~465,000** |
| One weekly re-sweep of both | | **~810,000** |

Every per-call number above is now measured, not quoted. Build tier is 25,000
credits/month. **The national sweep alone is ~14× a month's Build allowance, and one
full weekly cycle is ~810k credits — roughly $810 at list.** That is the number for the
founders email, and it is a measured figure rather than a call count.

For the one-pager COGS line, the honest version: **a full project screen costs about
155 Mireye credits, or 15.5 cents.** At 3,000 tracked projects re-swept weekly that is
~465k credits a week, ~2M credits a month, ~$2,000/month of Mireye spend — against an
alt-data subscription priced at $50k–500k/year. The unit economics work, and the number
is theirs to keep.

**Rate limits: 60 rpm on Build.** The brief's ThreadPoolExecutor at 8 workers would blow
through that instantly. `MireyeProvider` has a shared minimum-interval limiter
defaulting to `MIREYE_RPM=60`, so 8 workers is safe: they queue on the limiter, not on
429s. Verified in practice — `refusals_24h.throttled_429s` was **0** across the whole
verification session. The authentication page's claim that "V1 has no metered request
quotas" is contradicted by the per-plan `rpm`; believe the machine-readable one.

**Reading spend back.** `/v1/proximity` reports `credits_charged` inline. Nothing else
does, so `MireyeProvider.usage()` computes from the price table — and that computation
was checked against the account's own meter and matched to the credit (884 = 884). Poll
`GET /v1/users/me/usage` at the end of a sweep to reconcile, never per call.

---

## 7. The fields we thought we'd have to build — VERIFIED, they already exist

This is the single biggest research finding and it changes §3 of the build brief.

`data_center_siting` already contains, cited to EPA:

| Field | Source | What it is |
|---|---|---|
| `in_air_quality_nonattainment` | `EPA_GREEN_BOOK` | bool — in any current NAAQS nonattainment area |
| `air_quality_nonattainment_pollutants` | `EPA_GREEN_BOOK` | e.g. `"Ozone (2015),PM2.5 (2012)"` |
| `in_air_quality_maintenance` | `EPA_GREEN_BOOK` | bool — former NA area under a maintenance plan |
| `air_quality_maintenance_pollutants` | `EPA_GREEN_BOOK` | comma-joined |
| `air_quality_worst_classification` | `EPA_GREEN_BOOK` | Extreme > Severe > Serious > Moderate > Marginal |
| `air_district_name` | `CARB_AIR_DISTRICTS` | California air district; null elsewhere |
| `nearest_class_i_area_distance_m` | `EPA_CLASS_I_AREAS` | geodesic m; 0 inside one |
| `nearest_class_i_area_name` | `EPA_CLASS_I_AREAS` | e.g. `"Yosemite NP"` |
| `nearest_class_i_area_agency` | `EPA_CLASS_I_AREAS` | USDI-NPS / USDA-FS / USDI-FWS / BIA |

Consequences for the build, for the orchestrator to decide on:

- **The EPA Green Book CSV ingest (Layer 3 of the brief) is redundant.** Mireye returns
  nonattainment status *and* classification *at a coordinate*, which is strictly better
  than our county-level join — nonattainment areas are sub-county in metros like
  Atlanta and Phoenix, and the brief's own state-overlay notes say so. Keep
  `ingest/greenbook.py` as a cross-check and a citation-independence story, not as the
  primary. It is one CSV; leaving it in costs nothing and makes "we validated their
  field against the federal source" a good line in the feedback field.
- **Two of the four planned field-requests turned out to be near-answered.** Filed for
  real; see §13 for the verbatim outcomes. Class I distance came back `matched_existing`
  with a live sample. County attainment came back `near_miss_confirm` — because
  `air_quality_worst_classification` is blank for every non-ozone, non-CO pollutant,
  which is a limitation we would not have found any other way.
- **The two that are genuinely missing, and were queued as builds:**
  1. **Background ambient PM2.5 / NO2 concentration at a coordinate** (EPA AQS design
     values). Nothing in the catalog measures ambient concentration. This is the input
     to a NAAQS compliance demonstration and it is pure public federal data.
  2. **Count and permitted emissions of major stationary sources within X km**
     (EPA NEI / Title V). Nothing in the catalog carries permitted emissions.
     `nearest_hazardous_facility_*` and the RCRA/superfund fields are facility
     *locations*, not emission rates. This is what PSD increment consumption is
     computed from, and it is the hardest gap in the whole build.
  3. Worth a third: **environmental-justice / overburdened-community indicators**. The
     catalog has `county_median_household_income`, `housing_units_within_1km` and
     `housing_units_density_per_km2` and nothing else demographic. NJ's EJ law
     (the Nebius failure mode) turns on exactly this and we cannot compute it.

Both #1 and #2 were accepted as new builds, exactly as predicted — neither tripped
`commercial_licensed`, `realtime_streaming` or `subjective_score`. Queue positions 2 and
3, both promised for 6 Aug, which is before the deadline.

Other gaps worth knowing about:

- **No nearest-surface-water distance field.** There is `nearest_waterbody_name` but no
  `nearest_waterbody_distance_m`. Closest usable proxy is
  `nearest_usgs_gage_distance_m`, which is the nearest *gauged* stream — different
  thing. `PROXIMITY_TARGETS["water_body"]` uses it with the caveat in the note.
- **No region search.** Their own ICP Finder skill says it: "Mireye has no
  region-search endpoint (no 'find sites in the Bay Area')". The alternate-site search
  must generate its own candidate coordinates — a ring/grid around the failed parcel —
  and screen them one by one. Plan the credits accordingly (see §6).
- **`/v1/fetch/batch` takes 25 locations per request**, one field selection, index-aligned
  results, each entry a full `/v1/fetch` body. The national sweep should use it:
  3,140 counties becomes 126 requests instead of 3,140. Same credits, 25× fewer round
  trips, and it fits inside 60 rpm comfortably. `/v1/runs` wraps the same thing
  asynchronously if we don't want to hold connections open.

---

## 8. `/v1/field-requests` — VERIFIED

Two required keys:

```json
{
  "description": "1-8000 chars, plain language: what the data IS, what decision it feeds",
  "example_locations": [{"address": "..."} | {"lat": .., "lng": ..} | {"polygon": {...}}]
}
```

1–10 example locations, each supplying **exactly one** of `address` / `lat`+`lng` /
`polygon`. Optional per entry: `claimed_value` (becomes a frozen eval case for the
build) and `note`.

Strongly worth filling in, because each answers a question the build otherwise stops to
ask a human: `use_case`, `decision_threshold`, `area_of_interest`, `expected_volume`,
`freshness`, `constraints` (`must_not_be` / `already_have`), `known_sources`,
`deadline`, `output_preference`. Plus plumbing: `requested_fields`, `idempotency_key`
(**send one — same key + same ask replays, same key + different ask is
`409 idempotency_key_reused`**), `callback`, `context_blob` (≤8 KB, echoed verbatim).

**Unknown keys are rejected `422 invalid_payload`, never ignored.**

Four outcomes per sub-ask, rolled up into a request-level `status`:

| `disposition` | rollup `status` | What we get |
|---|---|---|
| `matched_existing` | `matched` | `field_id`, a **live cited sample at our own first location**, and a `resume` call |
| `near_miss_confirm` | `awaiting_confirm` | closest field, `reason` naming the difference, a sample; re-POST with `constraints.must_not_be` to reject it |
| `clarify` | `awaiting_confirm` | candidate field ids to pick between |
| `accepted_new` | `queued` | `request_id`, `queue_position`, `estimated_ready_at` (~a day), `feasibility_class: "source_uncertain"`, and a `resume` call that will work once live |
| `rejected` | `rejected` | `rejection_code` + `routing_hint`; six codes: `pii_contact`, `commercial_licensed`, `realtime_streaming`, `subjective_score`, `non_us`, `routing_computation` |

HTTP 201 on create, 200 on idempotent replay or a location clarify, **202 when
screening (a ~10 s budget with one model call) can't finish** — then `status:
"received"` and the disposition lands in the poll.

Poll `GET /v1/field-requests/{request_id}`. Status walks
`received → screening → queued → claimed → building → in_review → approved → publishing
→ live`. Terminal: `live`, `blocked`, `expired`, `rejected`, plus `matched`.

The detail worth putting in the demo: **`live` means prod `/v1/fetch` returned a real
cited non-null value at our own example locations** — not "the PR merged". They say so
twice.

Filing does not consume fetch credits; it consumes the plan's
`field_requests_included` allowance. Build tier = 1. So we get **one** real build. Spend
it on the NEI/Title V major-source emissions field — it is the one that unblocks PSD
increment, which is the hardest number in `agent/pathway.py`.

---

## 9. MCP server — VERIFIED

Server name `com.mireye/earth`. Two distributions.

**Claude Code — hosted, OAuth, this is the one to use:**

```bash
claude mcp remove mireye-earth -s user     # only if a stdio one was configured before
claude mcp add --transport http --scope user mireye-earth https://api.mireye.com/mcp
# restart Claude Code, run /mcp, follow the browser login
```

**Claude Desktop / Cursor — local stdio adapter:**

```json
{"mcpServers": {"mireye-earth": {"command": "uvx", "args": ["mireye-mcp"]}}}
```

then `mireye-mcp login` (device flow) or set `MIREYE_BEARER_TOKEN`. macOS GUI apps get
a minimal PATH, so use the absolute path to `uvx` if it doesn't start. Config lives at
`~/Library/Application Support/Claude/claude_desktop_config.json` or `~/.cursor/mcp.json`.

Seven tools: `mireye_ask`, `mireye_fetch`, `mireye_geocode`, `mireye_lookup`,
`mireye_proximity`, `mireye_request_field`, `mireye_field_request_status`. Resources:
`mireye://catalog/fields`, `mireye://catalog/presets`, `mireye://catalog/us-envelope`.
Prompts include `mireye_site_report`, `mireye_flood_check`, `mireye_wildfire_underwrite`,
`mireye_pick_fields`.

Adapter env vars: `MIREYE_BASE_URL` (default `https://api.mireye.com`),
`MIREYE_TIMEOUT_S` (default 120, never set below 120), `MIREYE_BEARER_TOKEN`,
`MIREYE_MCP_CREDENTIALS_FILE`.

Two gotchas: the installation page's own smoke check says "tools list shows exactly two
entries" while the same page lists seven — stale copy, expect seven. And **MCP OAuth
tokens are not `/v1/*` tokens**; the agent loop in `agent/planner.py` needs a dashboard
token either way, so wiring MCP is for interactive work and the demo, not for the sweep.

---

## 10. Starter templates worth stealing

Nine "Agent Skills" at `/templates/<slug>`, each a real `SKILL.md` with frontmatter, a
recipe, a curl example and a full example response. The full skill text is embedded in
the page — the "Copy Skill" button just copies it.

Every one of them carries the same four lines of implementation guidance, and they are
worth honouring because they are effectively Mireye's own house style:

> - If `$MIREYE_API_TOKEN` isn't set, ask the user for their key. Don't fabricate a token.
> - Every value carries `source`, `source_url` and `confidence` — keep at least the
>   source name when relaying a result, so the citation trail isn't lost.
> - Treat any undocumented response status as a real failure. Never silently treat it as
>   "no data" or a non-match.
> - (list skills) This runs one request per row — mind your QPS limits and add
>   retry/backoff before scaling.

| # | Template | Endpoint / preset | Verdict for us |
|---|---|---|---|
| 1 | **Land Read** | `/v1/fetch`, `preset: terrain` + `fields: [lcms_class, land_use_class]` | **Steal directly.** This is our terrain + land-cover read for dispersion inputs (slope, relief, surface roughness). Also the source of the "preset members are exempt from the 50-field cap" line. |
| 2 | **Power Read** | `/v1/fetch`, `preset: utilities` | **Steal directly.** Nearest power plant, transmission line + kV, `max_transmission_line_voltage_kv_within_radius`, gas pipeline distance, sewer service area — one call. This is Stage 2 of the brief and it kills the EIA/HIFLD ingest exactly as planned. Their own comment: "the same data our internal power-tiering pipeline uses." |
| 3 | **Hazards Read** | `/v1/fetch`, `preset: flood_risk` + `fields: [tree_canopy_pct, ndvi_current]` | **Steal the pattern**, not the content. The preset-plus-extra-fields idiom is what we use everywhere. Flood matters less to a permit pathway than to an underwriter, but it is a real non-air blocker. |
| 4 | **ICP Finder** | `/v1/lookup` then `/v1/fetch preset: site_selection`, per row | **This is the alternate-site search, exactly.** Resolve each candidate, screen it, filter against our own predicate. Two things to take from it: route `clarify`/`no_match` to review rather than dropping them, and its admission that there is no region-search endpoint, which is why we generate our own candidate ring. Swap `site_selection` for `data_center_siting` — better fields for us and it dodges the 300-credit parcel group. |
| 5 | **Property Diligence Copilot** | `/v1/lookup` | **Steal directly.** This is Stage 1 Resolve. Its disposition-handling rule ("`clarify` means multiple plausible matches — surface candidates to a human, never silently pick one") is the same product decision as our `ResolutionError`, which is worth saying out loud in the feedback field. |
| 6 | **Lending & Appraisal Support** | `/v1/lookup`, reading `county_market` + `in_opportunity_zone` | **Partial.** We don't underwrite loans, but `county_market` (population growth, permits, employment, HPI) is free on every resolved lookup and is a decent proxy for local growth pressure and opposition posture. Take the fields, drop the framing. |
| 7 | **CRM Address Cleanup** | `/v1/lookup` per row, split by disposition | **Steal the error rule.** Its most useful line: a geocode-quality failure can arrive as `404 address_too_coarse` *or* as a `200` with `disposition: "no_match"` — treat both as a non-match, and treat **any other** status as a real failure. Our client does exactly this. |
| 8 | **Insurance Book Monitoring** | `/v1/fetch` per row, parallel, on a schedule | **Steal the shape.** This is our weekly re-sweep of 3,000 tracked projects: same screen, re-run on a cadence, alert when a value crosses a threshold. Their framing ("re-run on every renewal instead of trusting a stale one-time inspection") is almost verbatim our alt-data pitch. It should have used `/v1/fetch/batch`; ours will. |
| 9 | **Grounded Location Q&A** | `/v1/ask`, or `/v1/ask/stream` | **Use for the messy edges only**, per the brief — and note the 15-field planner cap, which means it cannot stand in for a full screen. `include_trace: true` returns `planner_reasoning` and `preset_expanded`, which is a genuinely good thing to show on camera. |

Net: 1, 2, 4, 5, 7 and 8 map onto the build directly. 3, 6 and 9 contribute a pattern or
a couple of fields each. None of the nine does anything with permitting — which is the
point of the entry.

---

## 11. The provenance shape — where source, fetched and confidence actually live

The README claims every fact carries a source, a timestamp and a confidence. Here is
exactly where those come from, per endpoint, verified against live responses.

### `/v1/fetch` — full per-field provenance

Every field record carries these twelve keys, and nothing else (measured across all 106
`data_center_siting` fields):

```
value  unit  source  source_url  confidence  fetched_at
dataset_vintage  ttl_seconds  notes  status      (+ error, retryable on failures)
```

A real record from the Ashburn site:

```json
"in_air_quality_nonattainment": {
  "value": true,
  "unit": null,
  "source": "EPA_GREEN_BOOK",
  "source_url": "https://www.epa.gov/green-book",
  "confidence": "high",
  "fetched_at": "2026-08-05T09:21:18.241184+00:00",
  "dataset_vintage": "EPA Green Book NAAQS nonattainment designations (local gpkg mirror of the EPA OAQPS FeatureServer)",
  "ttl_seconds": 2592000,
  "notes": "True if the point intersects any CURRENT-NAAQS nonattainment area (ozone/PM2.5/PM10/CO/SO2/NO2/lead combined layer); Maintenance/Attainment areas do not set it",
  "status": "ok"
}
```

So the mapping into `base.Fact` is direct: `source` ← `source`, `fetched` ← `fetched_at`
(falling back to the response-level `fetched_at`), `confidence` ← the bucket, translated.
`source_url`, `dataset_vintage` and `notes` are concatenated into `Fact.note` so the
citation trail survives to the output.

**`confidence` is a bucket string, never a number.** Across the 106-field response the
distribution was `medium` 62, `high` 42, `low` 1, `unknown` 1. The translation table in
`providers/mireye.py` is `high→0.9, medium→0.6, low→0.3, unknown→None`, the raw bucket
is preserved verbatim in `Fact.note`, and **`unknown` becomes None rather than a low
score** — "not measured" and "measured badly" are different claims.

Worth knowing: confidence tracks the *source*, not the value. `elevation` came back
`medium` because it was served from `USGS_3DEP_COG` (the static DEM) rather than
`USGS_EPQS` (the dynamic service, which reports `high`). Same number, different
provenance, honestly different confidence.

**Which fields lack a confidence:** none. Every field record carries the key. But a
`failed` field carries `"confidence": "unknown"` and `"fetched_at": null`, so it lands
as `confidence=None` with the response timestamp — which is the correct outcome and not
an invented score.

The tri-state `status` is real and all three appeared in one response: **98 `ok`,
7 `absent`, 1 `failed`**. The failure:

```json
"partial_failures": [
  {"field": "nearest_rail_line_distance_m", "source": "BTS_RAIL",
   "error": "source returned null at this coordinate", "retryable": false}
]
```

An `absent` field is not an error — it is a cited "nothing here", and it keeps its
source and a useful note (`in_opportunity_zone` absent carries "point does not intersect
any designated Opportunity Zone tract"). We keep all three as Facts with `value=None`
and the status in the note, mirroring Mireye's own rule that a field they could not
fetch is never silently dropped.

### `/v1/lookup` — no per-field provenance

Confirmed live: the response has one top-level `confidence` (0.95 at our test site,
alongside `match_method: "geocode_rooftop"`) and **no source, timestamp or confidence on
any individual value**. `elevation_m`, `fema_flood_zone` and `county_market` arrive bare.

So `MireyeProvider.lookup()` attributes source from Mireye's documented source list and
leaves per-fact `confidence` **None**. The resolution confidence rides on
`Location.confidence`, where it belongs. Reusing 0.95 as if it described the FEMA flood
zone would be inventing a number.

### `/v1/ask` — provenance by citation group

`confidence` is a three-bucket string on the answer as a whole. `citations` groups fields
by source, each with its own `source_url`, `fetched_at` and bucket. `fields_used` and
`data_gaps` say what the answer did and did not rest on.

### `/v1/proximity` — provenance is the curated set

Candidates carry `name`, `lat`, `lng`, `attributes`, distances and durations, but no
per-candidate source or confidence. The provenance is the set itself (`@substations` is
EIA/HIFLD), so we record it as the source string and leave confidence None.

---

## 12. Intent to preset mapping — every `PRESET_INTENTS` name, resolved

`providers/base.py` gives the planner fourteen intents. Here is what each one actually
becomes, and which have no Mireye equivalent.

| Intent (`base.PRESET_INTENTS`) | Mireye surface | Cost | Status |
|---|---|---|---|
| `terrain` | preset `terrain` (6 fields) | 6 | direct |
| `land_cover` | preset `land_cover` (5) | 5 | direct |
| `utilities` | preset `utilities` (27) | 27 | direct |
| `grid_interconnect` | preset `grid_interconnect` (29) | 29 | direct |
| `data_center_siting` | preset `data_center_siting` (106) | 106 | direct |
| `site_selection` | preset `site_selection` (72) | **363** | direct, but 9 parcel-group fields make it expensive |
| `flood_risk` | preset `flood_risk` (13) | 13 | direct |
| `natural_hazard` | preset `natural_hazard` (17) | 17 | direct |
| `wildfire` | preset **`wildfire_underwrite`** (6) | 6 | renamed — the brief called it `wildfire` |
| `points_of_interest` | preset `points_of_interest` (23) | 23 | direct |
| `parcel` | 6 explicit `parcel_*` fields | **300** | no preset isolates the parcel; all members are parcel-group |
| `demographics` | 7 explicit fields | 7 | **partial gap** — see below |
| `water` | 12 explicit fields | 12 | assembled from `utilities` + `flood_risk` + `data_center_siting` members |
| `soil` | 7 explicit fields | 7 | assembled; no soil preset exists |

Four of Mireye's fifteen presets are irrelevant to this build and are not mapped:
`solar_siting`, `wind_siting`, `storage_siting`, `building_lookup`, `boundaries`
(the jurisdiction fields we get free on `/v1/lookup`).

### Intents with a real gap

- **`demographics` is the weak one.** The catalog has `housing_units_within_1km`,
  `housing_units_density_per_km2`, `tract_population`, `tract_civilian_labor_force`,
  `county_population`, `county_population_growth_1yr_pct` and
  `county_median_household_income` — and **nothing else demographic**. There is no
  race, no poverty rate, no environmental-justice index, no overburdened-community flag.
  That is exactly what NJ's EJ law (N.J.S.A. 13:1D-157, the Nebius failure mode) turns
  on, and we cannot compute it from Mireye. **Candidate field request.**
- **`water_body` proximity has no distance field.** There is `nearest_waterbody_name`
  but no `nearest_waterbody_distance_m`. We use `nearest_usgs_gage_distance_m` — the
  nearest *gauged* stream — and say so in the result note. **Candidate field request.**

---

## 13. The four field requests — filed for real, outcomes verbatim

All four were filed at 09:24 UTC on 5 Aug 2026 against the Ashburn test site, with
`use_case`, `decision_threshold`, `area_of_interest`, `expected_volume`, `freshness`,
`known_sources` and `output_preference` filled in, and an `idempotency_key` each. No
`callback` was sent — this build does not notify anyone (see the guardrails section of
the build brief); we poll instead.

**They cost 0 credits.** Filing bills the plan's `field_requests_included` allowance,
not the credit pool. Our plan includes 1; two builds were queued anyway.

Full request and response bodies are in `docs/api-captures/fr1…fr4*.json`.

### 1. County attainment / nonattainment status by pollutant → `awaiting_confirm`

`request_id: fr_72ffcf9048684a17860be106e8590aa2` · HTTP 201 · `waiting_on: requester`

Three `near_miss_confirm` dispositions. Their screener explained the shortfall better
than I could have, and it is a genuine limitation we would otherwise have hit blind:

> **`air_quality_worst_classification`** — "This field supplies the worst classification
> among ozone/CO matches only; it is explicitly blank for PM2.5/PM10/lead/SO2/NO2
> nonattainment areas, so it answers only half of the per-pollutant severity
> requirement."

> **`air_quality_nonattainment_pollutants`** — "This field identifies pollutants for
> which the point is in nonattainment, but does not break them out individually per
> pollutant or supply the severity classification separately."

That matters directly. `agent/pathway.py` picks a nonattainment major-source threshold
from the classification (Marginal/Moderate 100 tpy, Serious 50, Severe 25, Extreme 10).
**For a PM2.5 nonattainment county, Mireye returns the pollutant but no classification,
so we cannot pick a threshold.** Ozone and CO are covered. This is the single most
useful thing the field-request flow told us, and it is feedback-field material.

Live samples came back with the near-misses: `"8-Hour Ozone (2015 Standard)"` and
`"Moderate"`, both cited to `EPA_GREEN_BOOK`.

### 2. Distance to nearest Class I area → `matched`

`request_id: fr_bf22e9def8294b34b427c7862b33828e` · HTTP 201 · terminal, zero cost

Three `matched_existing` dispositions, each with a **live cited sample at our own
location** — not a convenient one of theirs:

```json
{"disposition": "matched_existing", "field_id": "nearest_class_i_area_distance_m",
 "reason": "Field directly measures geodesic distance in meters to the nearest Class I federal area (national parks / wilderness > 6000 acres).",
 "sample": {"value": 63478.439179638815, "unit": "meters", "source": "EPA_CLASS_I_AREAS",
            "source_url": "https://www.epa.gov/visibility/mandatory-federal-class-i-areas",
            "fetched_at": "2026-08-05T09:21:18.354199+00:00"}}
```

Plus `nearest_class_i_area_name` = `"Shenandoah NP"` and `nearest_class_i_area_agency` =
`"USDI-NPS"`. Answered in 3.1 s, no build, no wait.

### 3. Background ambient PM2.5 / NO2 concentration → `queued`

`request_id: fr_42c2a7c653c84f30be9584644ce0c752` · HTTP 201 · **queue position 2** ·
`estimated_ready_at: 2026-08-06T09:24:52Z`

Four `accepted_new` sub-asks (PM2.5 and NO2, each decomposed). Their reason:

> "No candidate field addresses EPA AQS design values, PM2.5 background concentration,
> or regulatory monitor data. The hazard/utility layers offered do not include
> air-quality monitoring or NAAQS compliance fields."

Field id it will publish under:
`background_ambient_air_concentration_at_a_coordinate_for_pm2` (and `…_no2`).

### 4. Count and permitted emissions of major stationary sources within X km → `queued`

`request_id: fr_20b6653a4a584fd0ae00d022be197a49` · HTTP 201 · **queue position 3** ·
`estimated_ready_at: 2026-08-06T09:24:58Z`

Three `accepted_new` sub-asks. Their reasons:

> "No candidate field enumerates major stationary sources or their count within a
> radius; existing hazards candidates cover air quality nonattainment status and
> lightning, not source inventory."

> "No candidate field supplies pollutant-specific emission rates (tons/year) from major
> stationary sources; the candidate set includes utilities and climate layers but no EPA
> NEI or Title V permit emission data."

> "No candidate field provides facility-level attribution (name, distance) paired with
> emission totals; this requires source-specific detail beyond the current candidate
> catalog."

This is the one that matters most. PSD increment consumption is the hardest number in
`agent/pathway.py` and today we cannot compute it. Both ETAs are **before the Monday
deadline**, so there is a real chance one goes live in time to demo.

### What to do with these

- **Poll all four before recording the demo.** `GET /v1/field-requests/{request_id}`.
  `live` means prod `/v1/fetch` returned a real cited non-null value at *our* example
  location — not that a PR merged. The `resume` call in each response is the exact
  `/v1/fetch` body that answers the original ask.
- **fr1 needs a decision.** It is `awaiting_confirm` and blocks on us. Either accept the
  near-miss (use `air_quality_nonattainment_pollutants` + `air_quality_worst_classification`
  and accept that non-ozone classifications are blank), or re-POST with the offered
  fields in `constraints.must_not_be` to force it to screen as a new build. Given we
  have 1 included field request and two builds already queued, accepting the near-miss
  and documenting the PM2.5 classification gap is the better trade.

---

## 14. Things that are broken or surprising right now

Found by running against production. All of this is feedback-field material.

1. **The `@airports` curated set is down.** `mode: "driving"` against `@airports`
   returned `503 proximity_data_unavailable`, retryable:

   > "curated set @airports asset is missing column(s) ['use'] that its default filter
   > requires -- the filter would match every row and the set would return wrong
   > answers, so it is refused instead. Rebuild the asset."

   Refusing rather than returning wrong answers is the right call, and the error message
   is genuinely excellent — it names the column, the consequence and the fix. But it
   means one of six curated sets is unusable. `MireyeProvider.proximity()` catches
   `proximity_data_unavailable` and falls back to the geodesic fetch field.

2. **`nearest_airport_distance_m` and `@airports` disagree, and the fetch field is
   wrong for our use.** The curated set filters FAA NASR to public-use airports
   (heliports excluded). The fetch field does not filter at all. At Ashburn it returned
   **"INOVA LOUDOUN HOSPITAL" at 6.2 km** — a hospital helipad. For an FAR Part 77
   airspace review on a 60 m stack that is the wrong answer, and right now there is no
   working way to get the filtered one. Flagged in `_PROXIMITY_ROUTES`.

3. **The public field catalog omits 10 fields that presets return.**
   `GET /v1/meta/fields` publishes 304 fields, but `presets.data_center_siting` names
   106 — ten of which are absent from the `fields` list:
   `btm_gas_candidacy_flag`, `residential_context_class_1km`, `tax_incentive_stack`,
   `grading_difficulty_class`, `estimated_annual_power_cost_usd_per_mw`,
   `transmission_redundancy_flag`, `near_epa_repowering_site`,
   `free_cooling_hours_per_year_10c/15c`, `nearest_urban_area_rtt_floor_ms`.
   They return real values, sourced `MIREYE_DERIVED_SITING` and
   `MIREYE_MODELED_ENERGY_COST`. This bit us: naive catalog validation silently dropped
   them. `known_fields()` now unions the field list with every preset expansion.

   These are also the only non-federal fields in the catalog — derived and modelled
   values rather than a cited federal source. Worth knowing before quoting
   `estimated_annual_power_cost_usd_per_mw` to a buyer.

4. **`credits.used` is eventually consistent and can go backwards.** Observed 0 → 2 →
   160 → 115 → 536. It converges correctly; it is just not a live meter.

5. **`credits_charged` on `/v1/proximity` is undocumented in prose** but present on
   every response. It should be on every endpoint — it is the single thing that would
   make client-side credit accounting trivial instead of a modelling exercise.

6. **The 400s carry no `retryable` key.** `fields_unknown` and `coord_out_of_bounds`
   return `{"error", "message"}` only, while 404s and 422s include `retryable: false`.
   A client branching on `detail.retryable` has to handle its absence. Ours falls back
   to the status code.

---

## 15. Still unverified

Short list now, and none of it blocks the build.

1. **`/v1/runs`** — never called. The sweep uses `/v1/fetch/batch` synchronously, which
   is verified. If a 3,140-county sweep turns out to need async, `/v1/runs` wraps the
   same request shape and would need its own testing.
2. **`/v1/ask/stream`** — never called. Not needed; we use the blocking form.
3. **`screen` and `labor_shed` proximity ops** — never called. `labor_shed` has a
   25-credit floor and an `estimate: true` flag that prices it for free; if we ever want
   "who lives downwind", price it with `estimate` first.
4. **`clarify` and `no_match` dispositions on `/v1/lookup`** — the code paths exist and
   are exercised by the `404 address_too_coarse` case, but we never triggered a genuine
   two-candidate `clarify`. The handling follows their documented shape.
5. **Field-request `live` transition** — both builds are `queued`. We have not seen a
   `live` payload, so the resume-call flow after a build completes is coded to the docs,
   not to an observed response.
6. **Whether a second `/v1/fetch` of the same coordinate within 24 h is billed again.**
   Their layer orchestrators keep a 24-hour cache but the docs do not say it is free to
   the caller. Our own SQLite cache makes this moot for re-runs.

---

## 16. Capture index

Every call made during verification, with its raw request and response in
`docs/api-captures/`. `credits` are the verified model's numbers.

| File | Endpoint | HTTP | Credits | What it proves |
|---|---|---|---|---|
| `01-geocode.json` | `/v1/geocode` | 200 | 1 | rooftop match, `source: "Loudoun"` |
| `02-lookup-noparcel.json` | `/v1/lookup` | 200 | 1 | full join keys, `confidence: 0.95` |
| `03-fetch-one-field.json` | `/v1/fetch` | 200 | 1 | per-field provenance shape |
| `04-fetch-preset-terrain.json` | `/v1/fetch` | 200 | 6 | preset expansion |
| `05-fetch-preset-data_center_siting.json` | `/v1/fetch` | 200 | 106 | **106 fields, presets exempt from the 50 cap** |
| `06-fetch-preset-utilities.json` | `/v1/fetch` | 200 | 27 | the whole power layer in one call |
| `07-fetch-air-permit-fields.json` | `/v1/fetch` | 200 | 9 | nonattainment + Class I for 9 credits |
| `08-fetch-preset-plus-fields.json` | `/v1/fetch` | 200 | 8 | `preset` + `fields` together is legal |
| `09-err-fields-unknown.json` | `/v1/fetch` | 400 | 0 | names the bad fields, bills nothing |
| `10-err-out-of-bounds.json` | `/v1/fetch` | 400 | 0 | US envelope enforcement |
| `11-err-address-too-coarse.json` | `/v1/geocode` | 404 | 0 | centroid refusal, `retryable: false` |
| `12-proximity-…-straightline.json` | `/v1/proximity` | 200 | 2 | `credits_charged: 2`, 0.50 km to BEAUMEADE |
| `13-proximity-nearest-airports-driving.json` | `/v1/proximity` | 503 | 0 | **the `@airports` outage** |
| `14-err-proximity-unknown-set.json` | `/v1/proximity` | 422 | 0 | only six curated sets exist |
| `15-ask.json` | `/v1/ask` | 200 | 10 | cited answer, `confidence: high`, trace |
| `16-proximity-…-driving.json` | `/v1/proximity` | 200 | 60 | `paid_driving_calcs: 5`, `credits_charged: 60` |
| `17-lookup-with-parcel.json` | `/v1/lookup` | 200 | 300 | real Regrid parcel, 57,289 m² |
| `18-fetch-batch.json` | `/v1/fetch/batch` | 200 | 4 | index-aligned, bad location isolated |
| `19-fetch-by-address-parcel-group.json` | `/v1/fetch` | 200 | 300 | **parcel group billed once, not per field** |
| `fr1-nonattainment.json` + `-status` | `/v1/field-requests` | 201 | 0 | `near_miss_confirm` ×3 |
| `fr2-class-i.json` + `-status` | `/v1/field-requests` | 201 | 0 | `matched_existing` ×3, live sample |
| `fr3-ambient-background.json` + `-status` | `/v1/field-requests` | 201 | 0 | `accepted_new`, queue position 2 |
| `fr4-major-sources.json` + `-status` | `/v1/field-requests` | 201 | 0 | `accepted_new`, queue position 3 |

Everything above is also in `data/cache.sqlite`, keyed by endpoint and canonical params,
so re-running any of it costs nothing. `python -m providers.cache` reports the totals.

---

## 17. What the test site actually said — the thesis, on real data

Worth recording, because it is the demo. **21571 Beaumeade Cir, Ashburn, VA 20147**,
resolved at confidence 0.95, rooftop, Loudoun County (FIPS 51107):

| Fact | Value | Source |
|---|---|---|
| In NAAQS nonattainment | **true** | `EPA_GREEN_BOOK` |
| Nonattainment pollutants | **8-Hour Ozone (2015 Standard)** | `EPA_GREEN_BOOK` |
| Worst classification | **Moderate** | `EPA_GREEN_BOOK` |
| Also in maintenance for | 8-Hour Ozone (2008 Standard) | `EPA_GREEN_BOOK` |
| Nearest Class I area | **Shenandoah NP, 63.5 km, USDI-NPS** | `EPA_CLASS_I_AREAS` |
| Nearest transmission line | 120.7 m, VIRGINIA ELECTRIC & POWER CO, IN SERVICE | `EIA_POWER` |
| Max voltage within radius | 230 kV | `EIA_POWER` |
| Nearest substation | 504.5 m (BEAUMEADE, 230 kV) | `EIA_POWER` |
| Nearest gas pipeline | 3,751 m | `EIA_PIPELINES` |
| Nearest power plant | Potomac Energy Center, 8.9 km, 766 MW, natural gas | `EIA_POWER` |
| County interconnection queue | 715 MW active | `LBNL_QUEUED_UP` |
| Housing units within 1 km | 1,575 (`residential_context_class_1km: dense`) | `CENSUS_TIGERWEB` |
| Modelled annual power cost | $863,736 per MW | `MIREYE_MODELED_ENERGY_COST` |

Feed that to `agent/pathway.py` and two triggers fire immediately: **ozone nonattainment
(Moderate → 100 tpy threshold for NOx and VOC, plus 1.15:1 offsets)** and **a Class I
area at 63 km, inside the 100 km FLM notification radius under 40 CFR 52.21(p)**. On top
of Virginia DEQ's 1.25× multiplier and the fact that DEQ has approved exactly one air
permit for a data center campus with on-site gas generation.

The grid facts say this is a superb site — 120 m to a 230 kV line, half a kilometre to a
substation. That is what Mireye's own deck screens for, and it says yes. The permit
facts say a 500 MW gas plant here is a multi-year fight. **That gap, on one real parcel,
is the entire product.**
