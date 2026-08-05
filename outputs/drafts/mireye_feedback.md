# DRAFT: "Feedback for Mireye" form field

**Status: NOT SUBMITTED. Akshat pastes this in himself.**

Read it once before pasting. Every number below was measured against the live API on
5 August 2026 and is traceable to `docs/mireye-api-notes.md` §6, §11, §13A and §14, and
to the raw bodies in `docs/api-captures/`. If you change a number here, change it there
too. Everything between the rules is the pasteable text.

---

Four days building an air-permit pathway agent for data center power projects. It takes
a parcel and a generation config, works out which permit the plant actually needs and
how long it takes, and when the answer is bad it searches outward for a parcel or a
config where the answer flips. Mireye is the entire physical layer. I built no
EIA/HIFLD ingest and no routing. Notes in the order I hit them.

**What worked**

Per-field provenance on `/v1/fetch` is the reason this product can exist. Twelve keys
per field, consistent across all 106 `data_center_siting` fields: `value`, `unit`,
`source`, `source_url`, `confidence`, `fetched_at`, `dataset_vintage`, `ttl_seconds`,
`notes`, `status`, plus `error`/`retryable` on failures. My output is a memo a
permitting engineer has to defend to a state agency, and every line of it carries a
federal source and a vintage because you put them there.

The tri-state `status` is the right design: one response gave me 98 `ok`, 7 `absent`,
1 `failed`. An `absent` field keeps its source and a reason ("point does not intersect
any designated Opportunity Zone tract") instead of vanishing. That is the difference
between "no" and "we didn't look", which are different facts in a permit file. The
`503` on `@airports` has the same instinct: it names the missing column, what that
costs, and the fix. Refusing beats answering wrong.

Typed refusals on low-confidence geocodes were right. I kept them and put my own 0.80
floor on top. A street-interpolated coordinate can be ~2.9 km out, routinely a different
county, and county decides the permit pathway. A refusal costs me a retry; a wrong
parcel costs a land option.

**Where I lost time**

*Modelling credits.* I reverse-engineered the meter call by call against
`GET /v1/users/me/usage`: 25 billable calls, 884 billed, 884 predicted. Re-checked later
on an independent run, 18 and 18. Two things made that a day's work instead of an hour.
One, `/v1/proximity` returns `credits_charged` in the response body and **nothing else
does**. That one field turns client-side accounting from a modelling exercise into a
read, so please put it on every endpoint. Two, parcel-group fields bill
`resolve_credits` **once per location, not per field**: a fetch of exactly
`["parcel_id", "parcel_area_m2"]` billed 300, not 302. Neither is obvious, and the
second one changes how you plan a sweep. `site_selection` is 72 fields, 9 of them
parcel-group, so 63 + 300 = 363 per location, not 72 and not 372. Worth saying next to
`parcel_field_group` in the plans payload. Separately, `credits.used` is eventually
consistent and went *backwards* mid-run (0 → 2 → 160 → 115 → 536). It converges. It
just isn't a live meter.

*The published catalog and the presets disagree.* `GET /v1/meta/fields` publishes 304
fields; `presets.data_center_siting` names 106, and 10 of those are absent from the
published list: `btm_gas_candidacy_flag`, `residential_context_class_1km`,
`estimated_annual_power_cost_usd_per_mw`, `tax_incentive_stack`,
`grading_difficulty_class`, `transmission_redundancy_flag`, `near_epa_repowering_site`,
`free_cooling_hours_per_year_10c`/`_15c`, `nearest_urban_area_rtt_floor_ms`. Thirteen
across all presets. They return real values, sourced `MIREYE_DERIVED_SITING` and
`MIREYE_MODELED_ENERGY_COST`. `fields_unknown` is a hard 400 that kills the whole
request, so I validate names locally first, and validating against the published list
silently dropped ten good fields until I unioned the preset expansions in. Publish them
or mark them derived, but the two lists should not disagree. (Related: I had 90 and 54
written down for `data_center_siting` and `site_selection`; they are 106 and 72. And I
assumed a preset called `wildfire`; it is `wildfire_underwrite`. `/v1/meta/fields` is
the only expansion size I would trust now.)

*`nearest_airport_distance_m` is unfiltered and wrong for the obvious use.* At
39.022183, -77.453578 it returns 6,197.5 m to **"INOVA LOUDOUN HOSPITAL"**, source
`FAA_NASR`. That is a hospital helipad. The `@airports` curated set does filter FAA
NASR to public-use airports, and it has been 503 for my entire build. So right now
there is no working way to get a public-use airport distance, which is exactly what a
FAR Part 77 stack-height review needs, and everyone siting generation does that review.
Either apply the same filter to the fetch field or rename it "nearest aviation
facility".

*`confidence` is a bucket string, not a number.* `high`/`medium`/`low`/`unknown`. I
translate through an explicit table (0.9/0.6/0.3) and keep the raw bucket alongside it.
`unknown` maps to null rather than to a low score, because "not measured" and "measured
badly" are different claims, and collapsing them would be a lie in a permit memo. I'd
prefer a number. Failing that, publish the mapping so everyone's table is the same one.
(One thing you did get right here: confidence tracks the source, not the value.
`elevation` came back `medium` from `USGS_3DEP_COG` where `USGS_EPQS` reports `high`.)

*`/v1/lookup` has no per-field provenance while `/v1/fetch` has a rich one.*
`elevation_m`, `fema_flood_zone` and `county_market` arrive bare under a single
top-level `confidence` that describes the *resolution*, not the elevation reading.
Reusing 0.95 as if it described the flood zone would be inventing a number, so I
attribute from your published source list and leave per-fact confidence null. The
inconsistency means the same fact is citable or not depending on which endpoint returned
it, which is awkward when provenance is the product.

**`/v1/field-requests`: the best thing in the API, and the one part of it that does not
work**

I filed four. Three outcomes, all useful.

*Nearest Class I area distance* → `matched` in 3.1 seconds, no build: three
`matched_existing` dispositions each with a live cited sample **at my own coordinate**,
not a convenient one of yours. 63,478.44 m to Shenandoah NP, `USDI-NPS`, from
`EPA_CLASS_I_AREAS`. I re-ran the `resume` call against prod an hour later and got the
same values to the last digit. That put my demo site inside the 100 km Federal Land Manager
notification radius of 40 CFR 52.21(p), which I didn't know when I filed.

*Background ambient PM2.5/NO2 design values* → `accepted_new`, queue position 2. *Count
and permitted emissions of major stationary sources within a radius* → `accepted_new`,
position 3. Both ETA'd for the next day. The second is PSD increment consumption, the
hardest number in my product, which today I cannot compute at all.

*County attainment status per pollutant* → three `near_miss_confirm`. Your screener's
reason was better than anything I would have worked out alone:
`air_quality_worst_classification` *"supplies the worst classification among ozone/CO
matches only; it is explicitly blank for PM2.5/PM10/lead/SO2/NO2 nonattainment areas."*
I verified it. Indiana County PA and St. Bernard Parish LA both return `"Sulfur Dioxide
(2010 Standard)"` for the pollutant and `null`/`status: "absent"` for the
classification. My engine picks a nonattainment major-source threshold from the
classification, so in an SO2 or PM2.5 county it can't pick one. Worse, at a
multi-pollutant site the scalar is silently attributable to the wrong pollutant. Fresno
CA returns `"8-Hour Ozone (2008 Standard),8-Hour Ozone (2015 Standard),PM-2.5 (2012
Standard)"` and `"Extreme"`. That is the *ozone* class; San Joaquin Valley's PM-2.5
class is Serious. I need (pollutant → classification) pairs, not one worst-of. I kept an
EPA Green Book parse as my authority for classification and use your fields as the
coordinate-level cross-check they are genuinely better at: a FIPS table can't tell me
which side of a partial-county boundary a parcel sits on, and your polygon can.

Three concrete bugs in that flow:

1. **A `near_miss_confirm` asks for a confirmation the API cannot accept.** It sits at
   `status: "awaiting_confirm"`, `waiting_on: "requester"`, `confirm_required: true`.
   Nothing clears it. `/v1/openapi.json` lists exactly two field-request routes;
   `FieldRequestPayload` has no confirm/accept/reject key; `POST`/`PATCH`/`PUT` on
   `/v1/field-requests/{request_id}` and `POST .../confirm` and `.../accept` all 404;
   re-POSTing the same idempotency key with a `constraints` block added is `409
   idempotency_key_reused`. Accepting is a no-op I record on my own side; rejecting
   costs a whole new request under a new key. That request will sit in
   `awaiting_confirm` forever.

2. **Generated `field_id`s truncate at 60 characters and collide.** My background
   request decomposed into four distinct sub-asks (PM2.5 annual, PM2.5 24-hour, NO2
   annual, NO2 1-hour design value) and produced two ids:
   `background_ambient_air_concentration_at_a_coordinate_for_pm2` twice and `…_for_no2`
   twice. Same in the other: `count_of_permitted_major_stationary_air_pollution_sources_wi`
   (cut mid-word) and `permitted_or_reported_annual_emissions_in_tons_per_year_for_`.
   The averaging period is the entire content of a design value. Annual PM2.5 is
   9.0 µg/m³, 24-hour is 35. If two builds publish under one id, one silently
   overwrites the other. And `resume` names one id for the whole request, so I can't
   tell which sub-ask it answers.

3. **Nothing signals how load-bearing `example_locations` is.** It is `minItems: 1` in
   the schema, but the ask reads like a catalog question, so my agent called without one
   and that was the single thing that broke on its first live run. It is the most
   important field in the payload: near-miss samples get taken there and the build is
   verified against it. Picking the right coordinate is what made the near-miss reason
   above useful to me instead of generic. That belongs in the first sentence of the
   endpoint docs, not in the schema.

**What I needed and could not get**

Demographic and environmental-justice indicators. The catalog has
`housing_units_within_1km`, `housing_units_density_per_km2`, `tract_population`,
`tract_civilian_labor_force`, `county_population`, `county_population_growth_1yr_pct`
and `county_median_household_income`. Nothing else demographic. No race, no poverty
rate, no EJ index, no overburdened-community flag. New Jersey's EJ statute
(N.J.S.A. 13:1D-157) lets NJDEP deny a permit outright in an overburdened community
regardless of whether the modelling passes. That is the single statute most likely to
kill a project in my space, and it is public Census and EPA EJScreen geometry.

Nearest-waterbody distance. There is `nearest_waterbody_name` but no
`nearest_waterbody_distance_m`, so I proxy with `nearest_usgs_gage_distance_m` and
label it as a proxy. The nearest *gauged* stream is a different thing. Cooling-water
intake and NPDES thermal discharge both key off the real distance.

**One concrete API change**

Let `/v1/fetch` take a bounding box, or a centre plus radius and spacing, and return a
grid. My alternate-site search is the single biggest credit consumer in the product:
when a parcel fails, the agent generates 24 candidate points on rings around it and
screens each one, and every candidate is its own `/v1/lookup` plus `/v1/fetch` plus
`/v1/proximity`. `/v1/fetch/batch` covers the fetch leg at 25 locations, but I still
have to invent the points and there is no batch form for lookup or proximity. A radius
form collapses that into one call. It also gives you one clean thing to price.

**The thing I would want most**

Coverage outside the US. The pattern is identical everywhere: announced capacity versus
deliverable capacity. India is next on my roadmap. Announced 6–8 GW by 2030 is
realistically 3.4–3.6 GW, same gap, same causes. I wrote my provider layer as an
interface with Mireye as the US implementation, so a second country is a new file
rather than a rewrite. The architecture is already waiting for you. The day you go
international I am a customer.

---

**Notes for Akshat before pasting**

- Poll the two queued field requests first:
  `GET /v1/field-requests/fr_42c2a7c653c84f30be9584644ce0c752` and
  `.../fr_20b6653a4a584fd0ae00d022be197a49`. Both ETAs were 6 Aug. If either has gone
  `live`, that turns "queued" into "shipped in a day", which is a much better sentence.
- Re-check `@airports` before submitting. If it has been rebuilt, move that paragraph to
  past tense rather than cutting it. The `nearest_airport_distance_m` filtering point
  stands either way.
- The credit numbers (884/884, 18/18) are in `docs/mireye-api-notes.md` §6 and §13A. Do
  not round them.
- If the field has a length limit, cut in this order: the `confidence` parenthetical,
  the preset-discovery parenthetical, then the waterbody paragraph. Keep the
  field-request section and its three bugs. That is the part nobody else will have.
