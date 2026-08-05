# DRAFT — "Feedback for Mireye" form field

**Status: NOT SUBMITTED. The agent never submits the form. Akshat pastes this in
himself.**

Read it once before pasting. Every number below was measured against the live API on
5 August 2026 and is traceable to `docs/mireye-api-notes.md` and the raw bodies in
`docs/api-captures/`. If you change a number here, change it there too. Everything
between the rules is the pasteable text.

---

Four days building an air-permit pathway agent for data center power projects. It takes
a parcel and a generation config, works out which permit the plant actually needs and
how long that takes, and when the answer is bad it searches outward for a parcel or a
config where the answer flips. Mireye is the entire physical layer — I did not build
EIA/HIFLD ingest, I did not build routing. Notes below in the order I hit them.

**What worked**

Per-field provenance on `/v1/fetch` is the reason this product can exist. Twelve keys
per field — `value`, `unit`, `source`, `source_url`, `confidence`, `fetched_at`,
`dataset_vintage`, `ttl_seconds`, `notes`, `status`, plus `error`/`retryable` on
failures — measured consistent across all 106 `data_center_siting` fields. My output is
a memo a permitting engineer has to defend to a state agency, and every line of it
carries the federal source and the vintage it came from because you put them there.

The tri-state `status` is the right design. One response gave me 98 `ok`, 7 `absent`,
1 `failed`. `absent` carrying a source and a reason ("point does not intersect any
designated Opportunity Zone tract") rather than being silently dropped is the difference
between "no" and "we didn't look", and those are different facts in a permit file.

Typed refusals on low-confidence geocodes were the right call. I kept them and added my
own 0.80 floor on top of yours. A street-interpolated coordinate can be ~2.9 km out,
which is routinely a different county, and county is what decides the permit pathway. A
refusal costs me a retry; a wrong parcel costs a land option. I would rather have the
refusal.

`confidence` tracking the source rather than the value is subtle and correct —
`elevation` came back `medium` from `USGS_3DEP_COG` where `USGS_EPQS` reports `high`.
Same number, honestly different provenance.

And `503 proximity_data_unavailable` on `@airports` names the missing column, the
consequence, and the fix: *"asset is missing column(s) ['use'] that its default filter
requires -- the filter would match every row and the set would return wrong answers, so
it is refused instead. Rebuild the asset."* Refusing beats answering wrong. More on the
consequence below.

**Where I lost time**

*Modelling credits.* I had to reverse-engineer the meter call by call and reconcile
against `GET /v1/users/me/usage`: 25 billable calls, 884 credits billed, 884 predicted.
Re-checked on an independent run later the same day — 18 modelled, 18 billed. It is
exact now, but getting there cost most of a day, for two reasons. First, `/v1/proximity`
returns `credits_charged` in the response body and nothing else does. That one field
makes client-side accounting trivial instead of a modelling exercise; please put it on
every endpoint. Second, parcel-group fields bill `resolve_credits` **once per location,
not per field** — a fetch of exactly `["parcel_id", "parcel_area_m2"]` billed 300, not
302. That is not obvious and it changes how you plan a sweep: `site_selection` is 72
fields, 9 of them parcel-group, so it is 63 + 300 = 363 per location, not 72 and not
372. Worth stating in the plans payload next to `parcel_field_group`. Also,
`credits.used` is eventually consistent and went *backwards* mid-run (0 → 2 → 160 → 115
→ 536). It converges; it just is not a live meter, and I burned time thinking I had a
billing bug.

*The public catalog and the presets disagree.* `GET /v1/meta/fields` publishes 304
fields. `presets.data_center_siting` names 106, and 10 of those are absent from the
published `fields` list — `btm_gas_candidacy_flag`, `residential_context_class_1km`,
`estimated_annual_power_cost_usd_per_mw`, `tax_incentive_stack`,
`grading_difficulty_class`, `transmission_redundancy_flag`, `near_epa_repowering_site`,
`free_cooling_hours_per_year_10c` / `_15c`, `nearest_urban_area_rtt_floor_ms`. Thirteen
across all presets. They return real values, sourced `MIREYE_DERIVED_SITING` and
`MIREYE_MODELED_ENERGY_COST`. Since `fields_unknown` is a hard 400 that kills the whole
request, I validate names locally before sending — and validating against the published
`fields` list silently dropped ten good fields. I now union in every preset expansion.
Either publish them or mark them derived, but the two lists should not disagree.

*`nearest_airport_distance_m` is unfiltered and it is wrong for the obvious use.* At
39.022183, -77.453578 it returns 6,197.5 m to **"INOVA LOUDOUN HOSPITAL"**, source
`FAA_NASR`. That is a hospital helipad. The `@airports` curated set does filter FAA NASR
to public-use airports — and it has been 503 for my entire build. So today there is no
working way to get a public-use airport distance, and that is exactly what a FAR Part 77
stack-height review needs. Anyone siting generation does that review. The fetch field
should either apply the same filter or be renamed to "nearest aviation facility".

*Preset shape was hard to discover.* I had 90 and 54 written down for
`data_center_siting` and `site_selection` before I started; they are 106 and 72. I had
assumed a preset called `wildfire`; it is `wildfire_underwrite`. `/v1/meta/fields` is
the only expansion size I would trust now — it would help to point at it from wherever
people first read about presets.

*`confidence` is a bucket string, not a number.* `high` / `medium` / `low` / `unknown`.
My `Fact` type wants a float, so I translate through an explicit table (0.9 / 0.6 / 0.3),
keep the raw bucket verbatim alongside it, and map `unknown` to null rather than to a
low score — "not measured" and "measured badly" are different claims and collapsing them
would be a lie in a permit memo. I would prefer a number. Failing that, publish the
mapping so everyone's table is the same one.

*`/v1/lookup` has no per-field provenance and `/v1/fetch` has a rich one.*
`elevation_m`, `fema_flood_zone` and `county_market` arrive bare, under a single
top-level `confidence` that describes the *resolution*, not the elevation reading.
Reusing 0.95 as if it described the FEMA flood zone would be inventing a number, so I
attribute from your published source list and leave per-fact confidence null. The
inconsistency means the same fact is citable or not depending on which endpoint I got it
from, which is awkward when provenance is the product.

**`/v1/field-requests` — the best thing in the API, and the one thing in it that does
not work**

I filed four. Three outcomes, all useful, and I do not think many people in this contest
will have touched it.

*Nearest Class I area distance* → `matched`, in 3.1 seconds, no build. Three
`matched_existing` dispositions each with a live cited sample **at my own coordinate**,
not a convenient one of yours: 63,478.44 m to Shenandoah NP, `USDI-NPS`, from
`EPA_CLASS_I_AREAS`. I re-ran the `resume` call days later and got the same values to the
last digit. That answer put my demo site inside the 100 km Federal Land Manager
notification radius of 40 CFR 52.21(p), which I did not know when I filed.

*Background ambient PM2.5 / NO2 design values* → `accepted_new`, queued at position 2.
*Count and permitted emissions of major stationary sources within a radius* →
`accepted_new`, queued at position 3. Both with ETAs the next day. The second one is the
hardest number in my product — PSD increment consumption — and I currently cannot
compute it at all.

*County attainment status per pollutant* → three `near_miss_confirm`. Your screener's
reason was more useful than anything I would have worked out myself:
`air_quality_worst_classification` *"supplies the worst classification among ozone/CO
matches only; it is explicitly blank for PM2.5/PM10/lead/SO2/NO2 nonattainment areas."*
That is correct, and I verified it: Indiana County PA and St. Bernard Parish LA both
return `"Sulfur Dioxide (2010 Standard)"` for the pollutant and `null` /
`status: "absent"` for the classification. My engine picks a nonattainment major-source
threshold from the classification, so in an SO2 or PM2.5 county it cannot pick one.

Worse, at a multi-pollutant site the single scalar is silently attributable to the wrong
pollutant. Fresno, CA returns pollutants `"8-Hour Ozone (2008 Standard),8-Hour Ozone
(2015 Standard),PM-2.5 (2012 Standard)"` and classification `"Extreme"` — that is the
ozone class. San Joaquin Valley's PM-2.5 class is Serious. Nothing in the response says
which pollutant the scalar belongs to. What I need is (pollutant → classification)
pairs, not one worst-of. I ended up keeping an EPA Green Book parse as my authority for
classification and using your fields as the coordinate-level cross-check they are
genuinely better at — a FIPS table cannot tell me which side of a partial-county
boundary a parcel sits on, and your polygon can.

**Three concrete bugs in that flow:**

1. **A `near_miss_confirm` asks for a confirmation the API cannot accept.** The request
   sits at `status: "awaiting_confirm"`, `waiting_on: "requester"`, `confirm_required:
   true` on all three dispositions — and there is no route that clears it.
   `/v1/openapi.json` lists exactly two field-request routes; `FieldRequestPayload` has
   no confirm/accept/reject key; `POST`, `PATCH` and `PUT` on
   `/v1/field-requests/{request_id}`, and `POST .../confirm` and `.../accept`, all 404;
   and re-POSTing the same idempotency key with a `constraints` block added is `409
   idempotency_key_reused`. So accepting is a no-op I record on my own side, and
   rejecting costs a whole new request under a new key. That request will sit in
   `awaiting_confirm` forever.

2. **Generated `field_id`s are truncated to 60 characters and collide.** My ambient
   background request decomposed into four distinct `accepted_new` sub-asks — PM2.5
   annual, PM2.5 24-hour, NO2 annual, NO2 1-hour design value — and produced two ids:
   `background_ambient_air_concentration_at_a_coordinate_for_pm2` twice and `…_for_no2`
   twice. Same in the other request:
   `count_of_permitted_major_stationary_air_pollution_sources_wi` (cut mid-word) and
   `permitted_or_reported_annual_emissions_in_tons_per_year_for_`. The averaging period
   is the entire content of a design value — annual PM2.5 is 9.0 µg/m³, 24-hour is 35 —
   so if two of those builds publish under one id, one silently overwrites the other.
   The `resume` block names only one id for the whole request, so I cannot tell which
   sub-ask it will answer.

3. **Nothing hints that `example_locations` is required until you send the request.**
   It is `minItems: 1` in the schema and the ask reads like a catalog question, so my
   agent called it without one and got a validation error on the first live attempt. It
   turns out to be the most load-bearing field in the payload — it is where the near-miss
   samples get taken and what the build gets verified against — and it deserves to be
   the first thing the docs say about that endpoint, not a schema detail.

**What I needed and could not get**

Demographic and environmental-justice indicators. The catalog has
`housing_units_within_1km`, `housing_units_density_per_km2`, `tract_population`,
`tract_civilian_labor_force`, `county_population`, `county_population_growth_1yr_pct`
and `county_median_household_income` — and nothing else demographic. No race, no poverty
rate, no EJ index, no overburdened-community flag. New Jersey's EJ statute
(N.J.S.A. 13:1D-157) lets NJDEP deny a permit outright in an overburdened community
regardless of whether the modelling passes. That is the single statute most likely to
kill a project in my space and I cannot screen for it from your data. It is public
Census and EPA EJScreen geometry.

Nearest-waterbody distance. There is `nearest_waterbody_name` but no
`nearest_waterbody_distance_m`, so I proxy with `nearest_usgs_gage_distance_m` — the
nearest *gauged* stream, which is a different thing — and label it as a proxy in the
output. Cooling-water intake and NPDES thermal discharge both key off the real distance.

**One concrete API change**

Let `/v1/fetch` take a bounding box, or a centre plus radius and spacing, and return a
grid. My alternate-site search is the single biggest credit consumer in the product:
when a parcel fails, the agent generates 24 candidate points on rings around it and
screens each one, and each candidate is its own `/v1/lookup` plus `/v1/fetch` plus
`/v1/proximity`. `/v1/fetch/batch` covers the fetch leg at 25 locations, but I still
have to invent the points myself and there is no batch form for lookup or proximity. A
radius form collapses that to one call, and it gives you something clean to price as one
call.

**The thing I would want most**

Coverage outside the US. The pattern I am selling is identical everywhere: announced
capacity versus deliverable capacity. India is next on my roadmap — announced 6–8 GW by
2030 is realistically 3.4–3.6 GW, the same gap, the same causes. I wrote my provider
layer as an interface with Mireye as the US implementation specifically so that a second
country is a new file rather than a rewrite. The architecture is already waiting for
you. The day you go international I am a customer.

---

**Notes for Akshat before pasting**

- Poll the two queued field requests before you submit — `GET
  /v1/field-requests/fr_42c2a7c653c84f30be9584644ce0c752` and
  `.../fr_20b6653a4a584fd0ae00d022be197a49`. Both ETAs were 6 Aug. If either has gone
  `live`, that changes a paragraph from "queued" to "shipped in a day", which is a much
  better sentence.
- Re-check `@airports` before you submit. If it has been rebuilt, soften that paragraph
  to past tense rather than deleting it — the `nearest_airport_distance_m` filtering
  point stands either way.
- The credit numbers (884/884, 18/18) are in `docs/mireye-api-notes.md` §6 and §13A. Do
  not round them.
- If the form field has a length limit, cut in this order: the `confidence`-tracks-the-
  source paragraph, the preset-discovery paragraph, then the waterbody paragraph. Keep
  the field-request section and the three bugs — that is the part nobody else will have.
