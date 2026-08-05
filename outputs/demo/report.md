# Screen — 39.4862,-75.0257

400 MW simple_cycle_turbine on natural_gas (uncontrolled), no enforceable hour cap (PTE at 8760)

## 2% probability of energizing on the announced schedule

- 16 months to the announced date. 3 months to prepare a complete application plus 66 months of agency review = 69 months required.
- Slack -53 months against a sigma of 15.7 months, taken from the 41-104 month range for Major nonattainment NSR.

*Model:* The air permit is treated as the critical path. Months available is the target energization date minus today. Months required is the pre-application preparation period plus the pathway's likely duration for that state agency. The pathway's own optimistic-to-pessimistic spread is read as roughly plus or minus two standard deviations, so sigma = (high - low) / 4, floored at one month. The probability is the normal CDF of slack over sigma, clipped to [0.02, 0.97] because nothing here justifies claiming certainty. Hard stops are a hard cap at 0.05: a moratorium, an unavailable offset market or a consumed increment is not a schedule risk, it is a different outcome. Turbine delivery, construction and interconnection are not modelled — they are separate constraints and each is documented as binding on its own.

## Pathway

**Major nonattainment NSR** — 41–104 months, likely 66.

Controlling pollutant: NOx at 5,887 tpy against a 50 tpy threshold.

Source category: Simple cycle, no steam cycle, so not a 'steam electric plant' and no boiler. Not a listed category despite 4,200 MMBtu/hr of heat input. Major source threshold is 250 tpy. Worth confirming with the state — a few agencies read the boiler entry more broadly than EPA does.

*40 CFR 52.21(b)(1)(i)(a); the 'List of 28' named source categories*

## Triggers that fired

| Trigger | Months added | Detail | Citation |
|---|---:|---|---|
| nonattainment designation | 0 | Cumberland County, NJ is designated nonattainment for: ozone (serious, Philadelphia-Atlantic City, PA-NJ); ozone (marginal, Philadelphia-Atlantic City, PA-NJ). | EPA Green Book, 40 CFR 81 |
| major nonattainment nsr | 6 | NOx PTE of 5,887 tpy is over the 50 tpy major threshold for a serious ozone nonattainment area. Requires LAER (no cost defense, unlike BACT) and 1.20:1 emission offsets — 7,064 tons of verified reductions bought from existing sources in the area. | CAA 173; 40 CFR 51.165(a)(1)(iv)(A) |
| title v | 0 | Title V operating permit required — criteria pollutant PTE 5,887 tpy over 100 tpy. Runs after the construction permit; usually does not block construction but does add annual compliance cost and a public comment window of its own. | 40 CFR Part 70 |
| nsps turbine | 0 | NSPS Subpart KKKK applies, and EPA's 15 January 2026 rule (91 Fed. Reg. 1910) added Subpart KKKKa. That rule did not settle the trailer-mounted question, and it did not settle it in the direction most coverage claims. It finalised a conditional exclusion removing turbines from the 'stationary combustion turbine' definition where the unit qualifies as a nonroad engine and is certified under Title II. The exclusion is not operative: it takes effect only if EPA adopts Title II standards for portable turbines, a separate rulemaking that has not happened. Meanwhile the NAACP is asking a federal court in Mississippi to shut down 27 unpermitted turbines at xAI's Colossus 2, with a preliminary injunction hearing set for late August 2026. Underwriting a trailer-mounted fast path today means underwriting an open legal question, not a loophole. | 40 CFR 60 Subpart KKKK and new Subpart KKKKa; 91 Fed. Reg. 1910 (15 Jan 2026); NAACP v. xAI (N.D. Miss.), PI hearing late Aug 2026 |
| state toxics | 2 | NJ runs a state air toxics program on top of the federal HAP rules. Expect a separate modeling demonstration for formaldehyde and, for engines, acrolein. This often drives stack height more than the NAAQS analysis does. | NJ DEP EJ Law N.J.S.A. 13:1D-157, effective April 2023 |
| ozone transport region | 3 | NJ is in the Ozone Transport Region. NOx is subject to nonattainment-style requirements statewide regardless of local monitor data, and the major source threshold for VOC/NOx is 50 tpy. | CAA 184; 40 CFR 51.165 |
| ej denial authority | 4 | NJ gives the agency authority to deny a permit outright in an overburdened community, independent of whether the emissions modeling passes. This is a discretionary denial risk, not a timeline risk. | NJ DEP EJ Law N.J.S.A. 13:1D-157, effective April 2023 |
| litigation | 3 | 2 federal case(s) touching this developer or county: MONTGOMERY v. DATAONE USA LLC — 1:26-cv-05972 — D.N.J. — filed 2026-05-26 — 28:1332 Diversity-Torts to Land; MOTLEY v. COSMED GROUP, INC. — 2:24-cv-09063 — D.N.J. — filed 2024-09-09 — 28:1441 Notice of Removal- Product Liability | CourtListener / RECAP |

## Potential to emit

| Pollutant | tpy | lb/hr |
|---|---:|---:|
| CO2e | 2,023,560.0 | 462,000.00 |
| NOx | 5,886.7 | 1,344.00 |
| CO | 1,508.5 | 344.40 |
| PM10 | 121.4 | 27.72 |
| PM2.5 | 121.4 | 27.72 |
| SO2 | 62.5 | 14.28 |
| VOC | 38.6 | 8.82 |
| HCHO | 13.1 | 2.98 |

PTE (tpy) = EF (lb/MMBtu) x heat input (MMBtu/hr) x hours (hr/yr) / 2000

- Heat input: 400 MW x 1000 kW/MW x 10,500 Btu/kWh / 1e6 = 4,200 MMBtu/hr
- Hours: 8,760 hr/yr — no enforceable cap, so PTE is computed at full-time operation regardless of intended dispatch
- Emission factors: AP-42 Table 3.1-1 / 3.1-2a / 3.1-3, uncontrolled natural gas turbine > 3 MW
- Controls: none

## Alternate site

**Move 37 miles W to New Castle County, DE. Save ~24 months.**

- New Castle County, DE at 39.3905, -75.7133
- Major nonattainment NSR, 26–66 months
- 37 miles from the announced site
- Clears: ej_denial_authority, state_toxics
- Screened 13 of 16 parcels out to 120 km for 80 credits

## Config alternatives at this parcel

| Change | Pathway | Likely | Months saved | Availability | What it costs |
|---|---|---:|---:|---:|---|
| Switch to solid oxide fuel cells | Minor NSR construction permit | 22 | +44 | 100% | Solid oxide fuel cells emit almost no criteria pollutants, which usually takes the air permit off the critical path entirely. CO2 is not solved — they still burn gas. Much higher capital cost per MW, a supplier list you can count on one hand, and lead times that are themselves the constraint at data center scale. |
| Add SCR | Major nonattainment NSR | 66 | +0 | 100% | SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. |
| Add oxidation catalyst | Major nonattainment NSR | 66 | +0 | 100% | An oxidation catalyst cuts CO by about 90% and VOC by about half. No reagent, no storage tank, small pressure drop, and it is cheap next to SCR. Worth checking first whenever CO is the pollutant sitting over the threshold — on an uncontrolled turbine that is more often the case than people expect. |
| Add SCR + oxidation catalyst | Major nonattainment NSR | 66 | +0 | 100% | SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. An oxidation catalyst cuts CO by about 90% and VOC by about half. No reagent, no storage tank, small pressure drop, and it is cheap next to SCR. Worth checking first whenever CO is the pollutant sitting over the threshold — on an uncontrolled turbine that is more often the case than people expect. |
| Add dry low-NOx combustors | Major nonattainment NSR | 66 | +0 | 100% | Dry low-NOx combustors are a turbine specification, not an add-on: you order the machine that way. No reagent and no aftertreatment, but the reduction is smaller than SCR and there are turndown and CO trade-offs at part load. |
| Switch simple cycle to combined cycle | Major nonattainment NSR | 66 | +0 | 100% | Combined cycle burns roughly two thirds the fuel per MWh, so tons per year drop with no control equipment at all. The catch is legal, not thermal: the HRSG and steam turbine make the plant a 'fossil fuel-fired steam electric plant' over 250 MMBtu/hr, which drops the PSD major threshold from 250 tpy to 100 tpy. Check both directions before assuming it helps. Also adds water, a longer build, and a second machine in an order book already full. |
| Combined cycle + SCR + oxidation catalyst | Major nonattainment NSR | 66 | +0 | 100% | Combined cycle burns roughly two thirds the fuel per MWh, so tons per year drop with no control equipment at all. The catch is legal, not thermal: the HRSG and steam turbine make the plant a 'fossil fuel-fired steam electric plant' over 250 MMBtu/hr, which drops the PSD major threshold from 250 tpy to 100 tpy. Check both directions before assuming it helps. Also adds water, a longer build, and a second machine in an order book already full. SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. |
| Split into two separate sources | Major nonattainment NSR | 69 | -3 | 100% | Splitting the plant only works if the pieces are genuinely separate stationary sources. Units serving one campus, under one owner, will be aggregated. Treat this as a conversation with the agency, not a design decision. |

> Accept a run-hour cap (as designed): Holding NOx under 50 tpy would need a cap of 67 hr/yr (1% availability). That is not a data center power plant, it is a peaker.

> Accept a run-hour cap, with SCR and oxidation catalyst: Holding NOx under 50 tpy would need a cap of 670 hr/yr (8% availability). That is not a data center power plant, it is a peaker.

## Field requests

- `class_i_area_distance_km` — error. field_request needs at least one example location — it is what seeds the build's eval cases and where the field is verified on prod
- `class_i_area_distance_km` — error. field_request needs at least one example location — it is what seeds the build's eval cases and where the field is verified on prod

## Agent's read

I'll work this in order. Step 1 is potential to emit — free, and it decides what physical facts are worth buying.

PTE is 5,887 tpy NOx uncontrolled — roughly 24x the 250 tpy major threshold, and formaldehyde at 13.1 tpy is over the 10 tpy single-HAP major line. This is a major source on any reading. Step 2 on category: a simple-cycle turbine with no heat recovery is **not** a "fossil fuel-fired steam electric plant," so the List-of-28 100 tpy threshold does not apply — it's 250 tpy. Irrelevant here; it clears both.

Step 3 — resolve the site before buying anything.

Resolved: Cumberland County, NJ (FIPS 34011), NJ DEP — matches the caller's declared jurisdiction, so this is a verified screen.

**My provider-call choices, and why:** I'm buying regulatory context (attainment is the fact most likely to flip the pathway, and NJ sits in the Ozone Transport Region), demographics (NJ's EJ statute N.J.S.A. 13:1D-157 is a *denial* authority, not a comment step — this is the single decisive fact here), points_of_interest (receptors feed both EJ review and NNSR modeling), utilities plus gas_pipeline proximity (no gas, no plant — the New Mexico failure mode), and terrain plus land_cover because at 5,887 tpy NOx a full AERMOD exercise is certain and both are AERMOD inputs. I'm skipping grid_interconnect (project is not grid-tied), flood_risk (already returned Zone X in the lookup), wildfire, soil and water — none of them touch the air pathway.

Step 4 is the one that decides this. Cumberland County is in **serious** nonattainment for the 2015 8-hour ozone NAAQS (Philadelphia-Atlantic City, PA-NJ — EPA Green Book, fetched 2026-07-31), and the whole state sits in the Ozone Transport Region. Serious classification drops the NOx major-source threshold to 50 tpy. The project is at 5,887 tpy.

Two gaps I need to close before the pathway is honest: the gas pipeline came back `missing` from the preset, and Class I area distance isn't indexed by any wired source. NJ has a Class I area (Brigantine Wilderness), so that is not a rounding error.

Step 6: **major nonattainment NSR**, 41–104 months, 66 likely. Announced energization is 16 months out. That is the headline.

Two things I need to fix or note before I act on it: the Class I request errored (it needs an example location), and the pipeline answer came back — nearest interstate trunkline is 34 km away.

Step 7 — testing config changes at this parcel. These are free, so I'll probe the three levers that could actually defend themselves: SCR on the simple cycle, combined cycle with SCR (checking whether the steam cycle drops the PSD threshold and makes things worse), and a fuel cell.

Config testing is decisive. SCR plus dry-low-NOx cuts NOx from 5,887 to 182 tpy and drops offsets from 7,064 tons to 219 — a real change in whether this is financeable — but it does not change the pathway, because the serious-ozone threshold is 50 tpy. Combined cycle gets to 111 tpy but pulls the plant onto the List of 28 as a steam electric plant, dropping the PSD threshold to 100 tpy. Only the fuel cell flips the pathway to minor NSR.

The site fails on major nonattainment NSR, which is the condition for searching outward. Let me do that, and retry the Class I request with the example location it needs.

I've spent 13 tool calls and I have what I need. Two field requests failed on a tool defect, which I'm reporting as a gap rather than papering over.

---

## Closing assessment

**The pathway is major nonattainment NSR. Likely 66 months, range 41 to 104. The announced energization is 16 months away. This project does not switch on in 2027 as configured.**

**What decides it — three things.**

First, the county designation. Cumberland County is in **serious** nonattainment for the 2015 8-hour ozone NAAQS, Philadelphia-Atlantic City PA-NJ area (EPA Green Book, 40 CFR 81, fetched 2026-07-31). Serious classification sets the NOx major-source threshold at 50 tpy, not 250. New Jersey is also entirely inside the Ozone Transport Region under CAA 184, so that 50 tpy applies statewide regardless of what any local monitor says. There is no version of a 400 MW gas turbine that gets under 50 tpy NOx. Uncontrolled PTE is 5,887 tpy at 8760 hours. Synthetic minor is arithmetically real but commercially dead: it needs a 67 hr/yr cap, which is one percent availability. That is not a data center plant.

Second, the offsets. At 1.2:1 you must buy 7,064 tons of verified NOx reductions from existing sources inside the nonattainment area (CAA 173). LAER applies with no cost defense. This is the item I would underwrite first, because it is the one that can be simply unavailable at any price in a mature Northeast airshed.

Third, and this is the one that can kill it outright rather than delay it — **NJ DEP holds environmental justice denial authority under N.J.S.A. 13:1D-157**. That is a discretionary denial, independent of whether your modeling passes. Look at where this coordinate actually sits: inside a Census-designated urban area, 344 m from Vineland Public Schools, 178 m from a medical facility, 476 points of interest within one kilometre (Overture Places and Census TIGER, fetched 2026-08-05T09:30). This is not an industrial edge parcel. It is central Vineland. For an overburdened-community determination that is close to a worst case. This is the Nebius failure mode and it is the reason I would not spend money on this parcel before getting a written EJ read.

**What actually changes the answer.**

Controls change the economics but not the pathway. SCR plus dry-low-NOx plus oxidation catalyst takes NOx from 5,887 to 182 tpy and offsets from 7,064 tons to 219. That is a thirty-fold reduction in your hardest procurement problem, and you should carry it regardless. But 182 is still over 50, so you are still in major NNSR and still at 66 months.

Combined cycle is a trap worth naming. It gets NOx to 111 tpy on the better heat rate, but the HRSG and steam turbine make the plant a fossil fuel-fired steam electric plant over 250 MMBtu/hr — it joins the List of 28 and the PSD major threshold drops from 250 tpy to 100. You improve the emissions and worsen the category. Still major NNSR.

The only config that flips the pathway is the fuel cell: minor NSR, 21.6 months likely, 44 months saved. Non-combustion, so criteria pollutants collapse to 9 tpy CO and 3 tpy NOx. Note it does not clear the EJ trigger and it does not clear CO2e at 1.43 million tpy. And 21.6 months still misses December 2027.

Moving does less than you would hope. The best alternates at 60 km — New Castle County DE and Delaware County PA — are still major nonattainment NSR. They clear the NJ EJ denial statute and NJ state toxics and save 24 months, landing at 42 likely. They do not escape the OTR, because the entire region from Virginia north is in it. You cannot drive out of the 50 tpy threshold inside 120 km.

**One non-air item that is close to a hard stop.** The nearest interstate gas transmission line is **34 km away**, Columbia Gas Transmission (HIFLD Gas Transmission Pipelines, fetched 2026-08-05T09:30). EIA's 10 km buffer returned null, confirming nothing closer. A 34 km lateral for a 400 MW plant is its own multi-year permitting and construction project with its own eminent domain exposure. Diameter, pressure and firm capacity are not in the dataset and must come from the operator. Both alternate sites have pipeline within 2 km. This alone is a strong argument against the parcel.

**Gaps you should not read as clears.**

The engine reports Class I AQRV as "clear" with no distance behind it. Class I area distance is not indexed by any wired source, and my two attempts to queue the field both failed on a tool error, not on a data judgment. Brigantine Wilderness is a Class I area roughly 50–60 km east of this coordinate by my own reckoning, which would put a PSD major source inside the 100 km Federal Land Manager review radius. Treat that "clear" as unverified. PSD increment already consumed and background ambient NO2 and PM2.5 at the coordinate are also unindexed. In a mature airshed, consumed increment is a live risk.

I also paid for demographics, terrain and land cover, and the returned field set surfaced points of interest, power and water/sewer but no EJ indicator values and no terrain relief or land cover values. So I have not confirmed the overburdened-community designation from data — I am inferring elevated risk from the receptor density, and you should get the designation confirmed directly.

**What I would change, in order.** Move the site — the parcel is urban, EJ-exposed and 34 km from gas, and all three are fixable by relocating. Carry SCR and dry-low-NOx in any case for the offset reduction. Get a written NJ DEP EJ read before optioning anything here. And reset the December 2027 date now; nothing in this analysis supports it, and the honest floor even on the fuel cell path is about 12 months with a likely case near 22.

One flag on the fast path someone will raise: NSPS Subpart KKKKa was added by the 15 January 2026 rule (91 Fed. Reg. 1910), and the trailer-mounted turbine exclusion in it is **not operative** — it takes effect only if EPA later adopts Title II standards for portable turbines, which has not happened. The NAACP is seeking to shut down 27 unpermitted turbines at xAI's Colossus 2 with a PI hearing late this month. That is an open legal question, not a loophole.

I have not contacted NJ DEP or anyone else, and I cannot. This is a screen for you to act on.

## What this does not know

- Nearest Class I area distance is unknown. It was requested via the provider's field-request route. A Class I area inside 100 km adds a Federal Land Manager review that can stop a project on visibility grounds alone.
- PSD increment consumption by existing major sources is unknown. A consumed increment can make a site un-permittable at any timeline.
- This is a screen, not an applicability determination. A licensed professional signs that opinion and carries the liability.
- The agent drafts and ranks. It does not contact agencies, file anything, or send anything. Drafts land in outputs/drafts/ for a person to review.

## Provenance

Every physical fact with its source, fetch timestamp and confidence.

| Field | Value | Source | Fetched | Confidence |
|---|---|---|---|---:|
| ask.answer | The nearest interstate natural gas transmission pipeline to 39.4862, -75.0257 is 34,019 meters (approximately 34 km) away, operated by Columbia Gas Trans Co, per the HIFLD Gas Transmission Pipelines dataset. The EIA's 10 km proximity buffer returned null — confirming no interstate pipeline exists within that tighter radius — but the unbounded HIFLD query resolved a real distance at ~34 km. Diameter, line pressure, and firm transport capacity are not geospatial attributes and were not returned by the dataset; these must be confirmed directly with Columbia Gas Trans Co as part of any tap feasibility assessment. For a 400 MW gas-fired plant, a 34 km lateral to the nearest interstate trunkline represents a material infrastructure gap requiring operator-confirmed capacity, tap lead time, and lateral construction cost before fuel supply can be assumed viable. | Mireye /v1/ask over EIA_POWER, HIFLD_GAS_TRANSMISSION_PIPELINES | 2026-08-05T10:08:03.624847+00:00 | 0.60 |
| ask.citations | [{'source': 'EIA_POWER', 'source_url': 'https://atlas.eia.gov/', 'fields': ['nearest_transmission_line_distance_m', 'nearest_transmission_line_voltage_kv'], 'fetched_at': '2026-08-05T09:30:51.042494+00:00', 'confidence': 'high'}, {'source': 'HIFLD_GAS_TRANSMISSION_PIPELINES', 'source_url': 'https://atlas.eia.gov/', 'fields': ['nearest_interstate_gas_pipeline_distance_m', 'nearest_interstate_gas_pipeline_operator'], 'fetched_at': '2026-08-05T09:30:54.576798+00:00', 'confidence': 'high'}] | Mireye /v1/ask | 2026-08-05T10:08:03.624847+00:00 | — |
| ask.data_gaps | [{'field': 'nearest_gas_pipeline_distance_m', 'reason': 'source returned null: no gas pipeline within 10 km'}] | Mireye /v1/ask | 2026-08-05T10:08:03.624847+00:00 | — |
| ask.plan | {'fields_requested': ['nearest_transmission_line_distance_m', 'nearest_transmission_line_voltage_kv', 'nearest_gas_pipeline_distance_m', 'nearest_interstate_gas_pipeline_distance_m', 'nearest_interstate_gas_pipeline_operator'], 'preset_expanded': None, 'planner_model': 'claude-haiku-4-5', 'synthesizer_model': 'claude-sonnet-4-6'} | Mireye /v1/ask trace | 2026-08-05T10:08:03.624847+00:00 | — |
| aspect_cardinal | S | USGS_3DEP_COG | 2026-08-05T09:30:42.700466+00:00 | 0.60 |
| bedrock_depth_cm | 4800.0 centimeters | PELLETIER_DTB | 2026-08-05T09:30:43.496043+00:00 | 0.30 |
| block_geoid | 340110411012017 | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| block_group_geoid | 340110411012 | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| cbsa_code | 47220 | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| cbsa_name | Vineland, NJ Metro Area | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| cdl_class | Developed/High Intensity | USDA_NASS_CDL | 2026-08-05T09:30:43.577539+00:00 | 0.60 |
| coast_distance_m | 9618.396788994687 meters | NOAA_CUSP | 2026-08-05T09:30:42.703785+00:00 | 0.90 |
| coastal_high_hazard | False | FEMA NFHL | 2026-08-05T10:07:20+00:00 | — |
| congressional_district | NJ-02 | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| county | Cumberland County | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| county_fips | 34011 | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| county_market.building_permits_sf_annual | 143 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.building_permits_total_annual | 143 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.building_permits_yoy_pct | -43.4783 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.employment_total | 60285 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.employment_yoy_pct | 1.0002 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.hpi_yoy_pct | 9.61 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.median_household_income_usd | 64499 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.net_domestic_migration | 148 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.population | 157148 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_market.population_growth_1yr_pct | 0.4738 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:07:20+00:00 | — |
| county_median_household_income | 64499 USD | CENSUS_ACS | 2026-08-05T09:30:52.349617+00:00 | 0.60 |
| county_population | 157148 people | CENSUS_PEP | 2026-08-05T09:30:52.349412+00:00 | 0.60 |
| county_population_growth_1yr_pct | 0.4738 percent | CENSUS_PEP | 2026-08-05T09:30:52.349507+00:00 | 0.60 |
| domestic_well_household_density_class | none | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992867+00:00 | 0.60 |
| domestic_well_households_per_km2 | 0.0 households/km2 | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992791+00:00 | 0.60 |
| dominant_crop_5y | None | USDA_NASS_CDL | 2026-08-05T09:30:43.579999+00:00 | 0.60 |
| elevation | 32.64278030395508 meters | USGS_3DEP_COG | 2026-08-05T09:30:42.699564+00:00 | 0.60 |
| elevation_m | 32.64278030395508 meters | USGS 3DEP/EPQS | 2026-08-05T10:07:20+00:00 | — |
| fema_flood_zone | X | FEMA NFHL | 2026-08-05T10:07:20+00:00 | — |
| housing_units_density_per_km2 | 653.818075328233 units/km2 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568353+00:00 | 0.60 |
| housing_units_within_1km | 3148 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568270+00:00 | 0.60 |
| in_opportunity_zone | True | US Treasury Qualified Opportunity Zones | 2026-08-05T10:07:20+00:00 | — |
| land_use_class | Developed | USFS_LCMS | 2026-08-05T09:30:43.584374+00:00 | 0.60 |
| lcms_class | Barren or Impervious | USFS_LCMS | 2026-08-05T09:30:43.582662+00:00 | 0.60 |
| max_transmission_line_voltage_class_within_radius | UNDER 100 | EIA_POWER | 2026-08-05T09:30:51.042574+00:00 | 0.90 |
| max_transmission_line_voltage_kv_within_radius | 69.0 kilovolts | EIA_POWER | 2026-08-05T09:30:51.042566+00:00 | 0.90 |
| nearest_bank_distance_m | 174.54205333608326 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528242+00:00 | 0.60 |
| nearest_bank_name | Newfield Bank | OVERTURE_PLACES | 2026-08-05T09:30:50.528254+00:00 | 0.60 |
| nearest_bar_distance_m | 248.18639189937016 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528152+00:00 | 0.60 |
| nearest_bar_name | Brinx Jones Brewing Company | OVERTURE_PLACES | 2026-08-05T09:30:50.528164+00:00 | 0.60 |
| nearest_cafe_distance_m | 2135.559832105021 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528122+00:00 | 0.60 |
| nearest_cafe_name | Krumbs Café | OVERTURE_PLACES | 2026-08-05T09:30:50.528135+00:00 | 0.60 |
| nearest_fire_station_distance_m | 276.08318583230084 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528039+00:00 | 0.60 |
| nearest_fire_station_name | Vineland Fire Dept. HQ | OVERTURE_PLACES | 2026-08-05T09:30:50.528049+00:00 | 0.60 |
| nearest_gas_pipeline_distance_m | None meters | EIA_PIPELINES | 2026-08-05T09:30:52.010253+00:00 | — |
| nearest_gas_station_distance_m | 231.07933505077324 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528181+00:00 | 0.60 |
| nearest_gas_station_name | US Petroleum | OVERTURE_PLACES | 2026-08-05T09:30:50.528195+00:00 | 0.60 |
| nearest_grocery_store_distance_m | 87.34968613867358 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528081+00:00 | 0.60 |
| nearest_hospital_distance_m | 177.5622323830132 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.527915+00:00 | 0.60 |
| nearest_hospital_name | Quality Care Resource & Referral Services | OVERTURE_PLACES | 2026-08-05T09:30:50.528023+00:00 | 0.60 |
| nearest_lodging_distance_m | 1248.6655385231193 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528091+00:00 | 0.60 |
| nearest_pharmacy_distance_m | 580.4681785686847 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528213+00:00 | 0.60 |
| nearest_pharmacy_name | Hernando's Hometown Pharmacy | OVERTURE_PLACES | 2026-08-05T09:30:50.528226+00:00 | 0.60 |
| nearest_power_plant_capacity_mw | 55.0 megawatts | EIA_POWER | 2026-08-05T09:30:51.245628+00:00 | 0.90 |
| nearest_power_plant_distance_m | 830.3 meters | EIA_POWER | 2026-08-05T09:30:51.245588+00:00 | 0.90 |
| nearest_power_plant_name | Howard Down | EIA_POWER | 2026-08-05T09:30:51.245604+00:00 | 0.90 |
| nearest_power_plant_primary_fuel | natural gas | EIA_POWER | 2026-08-05T09:30:51.245617+00:00 | 0.90 |
| nearest_restaurant_distance_m | 37.72996305035379 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528102+00:00 | 0.60 |
| nearest_restaurant_name | Carolyn's Bistro | OVERTURE_PLACES | 2026-08-05T09:30:50.528111+00:00 | 0.60 |
| nearest_school_distance_m | 343.806679659307 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528061+00:00 | 0.60 |
| nearest_school_name | Vineland Public Schools | OVERTURE_PLACES | 2026-08-05T09:30:50.528070+00:00 | 0.60 |
| nearest_sewer_service_area_distance_m | 0.0 meters | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932099+00:00 | 0.90 |
| nearest_shopping_center_distance_m | 296.00006868374055 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528270+00:00 | 0.60 |
| nearest_shopping_center_name | The Spot At The Ave | OVERTURE_PLACES | 2026-08-05T09:30:50.528282+00:00 | 0.60 |
| nearest_transmission_line_distance_m | 723.4 meters | EIA_POWER | 2026-08-05T09:30:51.042494+00:00 | 0.90 |
| nearest_transmission_line_owner | None | EIA_POWER | 2026-08-05T09:30:52.010253+00:00 | — |
| nearest_transmission_line_status | None | EIA_POWER | 2026-08-05T09:30:52.010253+00:00 | — |
| nearest_transmission_line_voltage_basis | numeric | EIA_POWER | 2026-08-05T09:30:51.042540+00:00 | 0.90 |
| nearest_transmission_line_voltage_class | UNDER 100 | EIA_POWER | 2026-08-05T09:30:51.042531+00:00 | 0.90 |
| nearest_transmission_line_voltage_kv | 69.0 kilovolts | EIA_POWER | 2026-08-05T09:30:51.042520+00:00 | 0.90 |
| nearest_wastewater_plant_distance_m | 4216.516311557331 meters | EPA_CWNS | 2026-08-05T09:30:51.019490+00:00 | 0.60 |
| nearest_wastewater_plant_name | Landis Sewerage Authority - CS/STP | EPA_CWNS | 2026-08-05T09:30:51.019556+00:00 | 0.60 |
| nearest_wastewater_plant_population_served | 74954 | EPA_CWNS | 2026-08-05T09:30:51.019566+00:00 | 0.60 |
| nearest_water_service_area_distance_m | 0.0 meters | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977618+00:00 | 0.90 |
| nonattainment.ozone | marginal — Philadelphia-Atlantic City, PA-NJ | EPA Green Book (8-Hour Ozone (2008)) | 2026-07-31 | — |
| nonattainment.ozone | serious — Philadelphia-Atlantic City, PA-NJ | EPA Green Book (8-Hour Ozone (2015)) | 2026-07-31 | — |
| opportunity_zone_tract_geoid | 34011041100 | US Treasury Qualified Opportunity Zones | 2026-08-05T10:07:20+00:00 | — |
| parcel | 39.4862,-75.0257 | caller-supplied coordinate | 2026-08-05T10:07:20+00:00 | — |
| poi_count_1km | 476 | OVERTURE_PLACES | 2026-08-05T09:30:50.528304+00:00 | 0.60 |
| proximity.airport | 4.56 km | FAA_NASR | 2026-08-05T09:30:54.040210+00:00 | — |
| proximity.school | 0.34 km | OVERTURE_PLACES | 2026-08-05T09:30:50.528061+00:00 | — |
| proximity.urban_area | 0.0 km | CENSUS_TIGER_URBAN | 2026-08-05T09:30:54.608346+00:00 | — |
| sewer_service_area_provenance | utility_sourced | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932089+00:00 | 0.90 |
| sewer_service_area_provider | Landis Sewerage Authority - CS/STP | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932078+00:00 | 0.90 |
| slope_degrees | 0.8287137746810913 degrees | USGS_3DEP_COG | 2026-08-05T09:30:42.700429+00:00 | 0.60 |
| soil_drainage_class | Well drained | NRCS_gNATSGO | 2026-08-05T09:30:43.489526+00:00 | 0.90 |
| state | New Jersey | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| state_fips | 34 | US Census Geocoder | 2026-08-05T10:07:20+00:00 | — |
| timezone | America/New_York | IANA tz database | 2026-08-05T10:07:20+00:00 | — |
| tract_civilian_labor_force | 1300 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805330+00:00 | 0.60 |
| tract_geoid | 34011041101 | US Census Geocoder (2020 vintage) | 2026-08-05T10:07:20+00:00 | — |
| tract_population | 3259 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805388+00:00 | 0.60 |
| transmission_lines_within_radius_count | 1 | EIA_POWER | 2026-08-05T09:30:51.042584+00:00 | 0.90 |
| tree_canopy_pct | 1.0 percent | USFS_NLCD_TCC | 2026-08-05T09:30:43.587699+00:00 | 0.90 |
| water_service_area_provenance | utility_sourced | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977658+00:00 | 0.90 |
| water_system_name | VINELAND WATER & SEWER UTILITY | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977646+00:00 | 0.90 |
| within_floodplain | False | FEMA NFHL | 2026-08-05T10:07:20+00:00 | — |
| within_sewer_service_area | True | EPA_SEWERSHEDS | 2026-08-05T09:30:51.931970+00:00 | 0.90 |
| within_water_service_area | True | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977539+00:00 | 0.90 |

*Generated 2026-08-05T10:12:36+00:00 · Claude Agent SDK tool-calling loop (claude-opus-5) · 13 tool calls · 94 credits.*

*Screen, not an applicability determination. The agent does not contact agencies, file anything, or send anything.*