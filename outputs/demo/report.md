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

**Move 25 miles SW to Kent County, DE. Save ~24 months.**

- Kent County, DE at 39.2314, -75.3541
- Major nonattainment NSR, 26–66 months
- 25 miles from the announced site
- Clears: ej_denial_authority, nonattainment_designation, state_toxics
- Screened 20 of 24 parcels out to 120 km for 120 credits

## Config alternatives at this parcel

| Change | Pathway | Likely | Months saved | Availability | What it costs |
|---|---|---:|---:|---:|---|
| Switch to solid oxide fuel cells | Minor NSR construction permit | 9 | +57 | 100% | Solid oxide fuel cells emit almost no criteria pollutants, which usually takes the air permit off the critical path entirely. CO2 is not solved — they still burn gas. Much higher capital cost per MW, a supplier list you can count on one hand, and lead times that are themselves the constraint at data center scale. |
| Add SCR | Major nonattainment NSR | 39 | +27 | 100% | SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. |
| Add oxidation catalyst | Major nonattainment NSR | 39 | +27 | 100% | An oxidation catalyst cuts CO by about 90% and VOC by about half. No reagent, no storage tank, small pressure drop, and it is cheap next to SCR. Worth checking first whenever CO is the pollutant sitting over the threshold — on an uncontrolled turbine that is more often the case than people expect. |
| Add SCR + oxidation catalyst | Major nonattainment NSR | 39 | +27 | 100% | SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. An oxidation catalyst cuts CO by about 90% and VOC by about half. No reagent, no storage tank, small pressure drop, and it is cheap next to SCR. Worth checking first whenever CO is the pollutant sitting over the threshold — on an uncontrolled turbine that is more often the case than people expect. |
| Add dry low-NOx combustors | Major nonattainment NSR | 39 | +27 | 100% | Dry low-NOx combustors are a turbine specification, not an add-on: you order the machine that way. No reagent and no aftertreatment, but the reduction is smaller than SCR and there are turndown and CO trade-offs at part load. |
| Switch simple cycle to combined cycle | Major nonattainment NSR | 39 | +27 | 100% | Combined cycle burns roughly two thirds the fuel per MWh, so tons per year drop with no control equipment at all. The catch is legal, not thermal: the HRSG and steam turbine make the plant a 'fossil fuel-fired steam electric plant' over 250 MMBtu/hr, which drops the PSD major threshold from 250 tpy to 100 tpy. Check both directions before assuming it helps. Also adds water, a longer build, and a second machine in an order book already full. |
| Combined cycle + SCR + oxidation catalyst | Major nonattainment NSR | 39 | +27 | 100% | Combined cycle burns roughly two thirds the fuel per MWh, so tons per year drop with no control equipment at all. The catch is legal, not thermal: the HRSG and steam turbine make the plant a 'fossil fuel-fired steam electric plant' over 250 MMBtu/hr, which drops the PSD major threshold from 250 tpy to 100 tpy. Check both directions before assuming it helps. Also adds water, a longer build, and a second machine in an order book already full. SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. |
| Accept a run-hour cap, with SCR and oxidation catalyst | Major nonattainment NSR | 39 | +27 | 38% | A federally enforceable run-hour cap is the cheapest way to become a minor source and the most expensive way to run a data center. The cap becomes a permit condition with continuous recordkeeping and real enforcement exposure. At 3,348 hr/yr the plant is available 38% of the year. That is a peaker, not a data center plant — it cannot carry the load on its own. |
| Split into two separate sources | Major nonattainment NSR | 42 | +24 | 100% | Splitting the plant only works if the pieces are genuinely separate stationary sources. Units serving one campus, under one owner, will be aggregated. Treat this as a conversation with the agency, not a design decision. |

> Accept a run-hour cap (as designed): Holding NOx under 250 tpy would need a cap of 335 hr/yr (4% availability). That is not a data center power plant, it is a peaker.

## Field requests

- `nj_overburdened_community_designation` — queued. 
- `class_i_area_distance_km` — near_miss. 

## Agent's read

I'll work this in order. Step 1 is potential to emit — free, and it decides what physical facts are worth buying.

PTE is NOx 5,887 tpy — roughly 24× the 250 tpy major threshold, and single-HAP formaldehyde at 13.1 tpy is over the 10 tpy major HAP line. This is a major source under any attainment status. That settles what I buy: this project is going to dispersion modelling, so terrain and land cover become worth credits rather than waste.

Step 3 — resolve the site before anything site-dependent.

Site resolves to Cumberland County, NJ — whole state is in the Ozone Transport Region, and NJ has an EJ denial statute. That shapes my buying.

**Provider calls I'm choosing and why:** `demographics` (NJ's EJ law N.J.S.A. 13:1D-157 can deny outright in an overburdened community — this is the single highest-consequence fact here); `points_of_interest` (receptors and opposition for a 5,887 tpy NOx source); `terrain` + `land_cover` (AERMOD is certain at this PTE — complex-terrain receptors and surface roughness are direct model inputs); `utilities` + `gas_pipeline` proximity (gas config, pipeline reachability is the classic non-air failure). **Skipping** `grid_interconnect` (behind-the-meter, not grid tied), flood/wildfire/soil/water (don't touch the air pathway).

Step 4/5 findings are severe, so let me run the decision tree before probing fixes.

Step 6 result: **Major nonattainment NSR, 66 months likely** against a 16-month announced energization. Step 7 — test whether any config at this parcel moves it.

Only the fuel cell moves the pathway. Even full LAER-grade control (SCR + DLN + ox-cat) lands NOx at 182 tpy against a **50 tpy** threshold — still major NNSR, zero months saved. The site fails, so I'm spending the expensive call. I'm also filing two gaps the engine flagged as not-wired.

Class I is the material correction: **Brigantine Wilderness, 50.0 km, USDI-FWS** (EPA_CLASS_I_AREAS, fetched 2026-08-05T10:38:53Z). The pathway engine listed `class_i_aqrv` as *cleared* — that clear was returned with no underlying data source, and it is wrong. At 50 km, FLM notification and AQRV/visibility modelling are effectively certain.

The alternate search found nothing that escapes major NNSR — because the entire Mid-Atlantic OTR carries the same 50 tpy NOx threshold. Best candidate is Kent County, DE at 42 months. Let me test the one config that did move the pathway, at that better jurisdiction.

## Closing assessment

**The pathway.** Major nonattainment NSR. As announced — 400 MW simple-cycle turbine, uncontrolled, no hour cap — this is not a close call. NOx potential to emit is 5,887 tpy against a 50 tpy threshold. That is 118× over. Formaldehyde at 13.1 tpy also crosses the 10 tpy single-HAP line, so Title V and major-source MACT come with it.

**The timeline.** 66 months likely, 41 to 104 months range, under NJ DEP's 1.6× multiplier. Announced energization is 16 months out. The gap is about four years, and it is not a scheduling problem you can compress.

**The three things that actually decide it.**

First, the 50 tpy threshold, and the fact that it does not move. New Jersey is entirely in the Ozone Transport Region, and Cumberland County is separately designated serious nonattainment for the 2015 ozone standard (Philadelphia-Atlantic City PA-NJ; EPA Green Book, fetched 2026-07-31). I tested the full LAER-grade control stack — dry low-NOx plus SCR plus oxidation catalyst. It cuts NOx from 5,887 to 182 tpy, a 97% reduction, and saves exactly zero months. Still major. Combined cycle at 6,400 Btu/kWh gets to 111 tpy and is also still major, and it makes one thing worse: adding the HRSG turns the plant into a fossil fuel-fired steam electric plant over 250 MMBtu/hr, which drops the PSD threshold from 250 to 100 tpy. No gas turbine at any size or control level clears this bar. Combustion is the problem, not the controls.

Second, the EJ denial authority. N.J.S.A. 13:1D-157 lets NJ DEP deny the permit outright in an overburdened community, regardless of whether the modelling passes. The site sits inside a Census urban area with 476 points of interest within 1 km, a school at 344 m and a hospital at 178 m (OVERTURE_PLACES, fetched 2026-08-05T09:30:50Z). This is downtown Vineland. That is a discretionary denial risk, not a delay — no amount of engineering answers it. I could not verify the block-group designation: the demographics preset returned market and POI fields but no EJ indicator, and the provider confirmed it does not index the NJ DEP overburdened community list. I have queued that field (request fr_826bce473c1a46e393471a2902413323, estimated 2026-08-06). Treat it as the open question that governs the site.

Third, offsets. 7,064 tons of verified NOx reductions bought from existing sources in the Philadelphia-Atlantic City area, at 1.2:1. I have no data on whether that many credits exist in this registry. My judgment is that they very likely do not at that volume, but I am not going to put a number on it I cannot cite.

**One correction to the engine output.** The decision tree reported the Class I trigger as *cleared*. It is not. Brigantine Wilderness is 50.0 km from the site, managed by USDI-FWS (EPA_CLASS_I_AREAS, fetched 2026-08-05T10:38:53Z). The regulatory context had separately flagged Class I distance as not indexed by any wired source, so that "clear" was returned with nothing behind it. At 50 km, Federal Land Manager notification and an AQRV visibility analysis are effectively certain, and that adds months on top of the 66.

**What I would change.**

The only lever that moves the pathway is the prime mover. A 400 MW fuel cell drops the controlling pollutant to 9 tpy CO, lands on minor NSR, and clears Title V entirely — 21.6 months at this parcel, saving 44. Moving it to the Kent County, DE candidate the search surfaced gets to 9 months likely, which is the only combination I found that meets a December 2027 date. Note the caveat: Delaware is not one of the eight state agencies modelled in detail, so that range is a federal default and is wider than it looks. Delaware is also still in the OTR, so the 50 tpy NOx threshold follows you there — the DE advantage is that it clears the EJ denial statute, the nonattainment designation and the state toxics program, not that it relaxes the threshold.

If the turbine is non-negotiable, relocation alone does not save it. The best alternate parcel in a 120 km sweep is still major NNSR at 42 months. Every county in that radius is inside the Mid-Atlantic OTR. You would have to leave the region entirely, which is a different question than the one asked.

**Gaps I am reporting as gaps, not as clean results.** Gas pipeline distance did not return for this site — for a gas-fired config that is a live unknown, and it is the failure mode that killed the New Mexico project. PSD increment already consumed and background ambient NO2/PM2.5 are not indexed by any wired source; both feed the modelling demonstration directly. The county zoning and moratorium file does not contain Cumberland County, so I have no read on local posture. Two federal cases touch this county or developer, including MONTGOMERY v. DATAONE USA LLC (1:26-cv-05972, D.N.J., filed 2026-05-26, torts to land), which the engine scored at three months.

I have not contacted anyone, filed anything, or committed to any agency. This is a screen for you to act on.

## What this does not know

- DE is not one of the states modelled in detail. The timeline is the federal default with no agency-specific adjustment, and state toxics programs, transport-region membership and any EJ statute are not evaluated. Treat the range as wider than shown and the trigger list as incomplete.
- No nonattainment designation was loaded for this county. If the Green Book ingest is not wired up, treat 'attainment' as unread rather than confirmed — it is the single fact most likely to flip the pathway.
- Nearest Class I area distance is unknown. It was requested via the provider's field-request route. A Class I area inside 100 km adds a Federal Land Manager review that can stop a project on visibility grounds alone.
- PSD increment consumption by existing major sources is unknown. A consumed increment can make a site un-permittable at any timeline.
- This is a screen, not an applicability determination. A licensed professional signs that opinion and carries the liability.
- Timelines are agency review time from a complete application. Turbine delivery, construction and interconnection are separate constraints and each can bind first.

## Provenance

Every physical fact with its source, fetch timestamp and confidence.

| Field | Value | Source | Fetched | Confidence |
|---|---|---|---|---:|
| aspect_cardinal | S | USGS_3DEP_COG | 2026-08-05T09:30:42.700466+00:00 | 0.60 |
| bedrock_depth_cm | 4800.0 centimeters | PELLETIER_DTB | 2026-08-05T09:30:43.496043+00:00 | 0.30 |
| block_geoid | 100010401002002 | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| block_group_geoid | 100010401002 | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| cbsa_code | 20100 | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| cbsa_name | Dover, DE Metro Area | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| cdl_class | Developed/High Intensity | USDA_NASS_CDL | 2026-08-05T09:30:43.577539+00:00 | 0.60 |
| coast_distance_m | 9618.396788994687 meters | NOAA_CUSP | 2026-08-05T09:30:42.703785+00:00 | 0.90 |
| coastal_high_hazard | False | FEMA NFHL | 2026-08-05T10:39:08+00:00 | — |
| congressional_district | DE-00 | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| county | Kent County | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| county_fips | 10001 | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| county_market.building_permits_sf_annual | 1030 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.building_permits_total_annual | 1261 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.building_permits_yoy_pct | 4.9958 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.employment_total | 70834 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.employment_yoy_pct | -0.3335 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.hpi_yoy_pct | 5.58 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.median_household_income_usd | 72872 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.net_domestic_migration | 1393 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.population | 194786 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_market.population_growth_1yr_pct | 0.9903 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T10:39:08+00:00 | — |
| county_median_household_income | 64499 USD | CENSUS_ACS | 2026-08-05T09:30:52.349617+00:00 | 0.60 |
| county_population | 157148 people | CENSUS_PEP | 2026-08-05T09:30:52.349412+00:00 | 0.60 |
| county_population_growth_1yr_pct | 0.4738 percent | CENSUS_PEP | 2026-08-05T09:30:52.349507+00:00 | 0.60 |
| domestic_well_household_density_class | none | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992867+00:00 | 0.60 |
| domestic_well_households_per_km2 | 0.0 households/km2 | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992791+00:00 | 0.60 |
| dominant_crop_5y | None | USDA_NASS_CDL | 2026-08-05T09:30:43.579999+00:00 | 0.60 |
| elevation | 32.64278030395508 meters | USGS_3DEP_COG | 2026-08-05T09:30:42.699564+00:00 | 0.60 |
| elevation_m | 15.475613594055176 meters | USGS 3DEP/EPQS | 2026-08-05T10:39:08+00:00 | — |
| fema_flood_zone | X | FEMA NFHL | 2026-08-05T10:39:08+00:00 | — |
| housing_units_density_per_km2 | 653.818075328233 units/km2 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568353+00:00 | 0.60 |
| housing_units_within_1km | 3148 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568270+00:00 | 0.60 |
| in_opportunity_zone | False | US Treasury Qualified Opportunity Zones | 2026-08-05T10:39:08+00:00 | — |
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
| opportunity_zone_tract_geoid | 34011041100 | US Treasury Qualified Opportunity Zones | 2026-08-05T10:34:24+00:00 | — |
| parcel | 39.214843,-75.628841 | caller-supplied coordinate | 2026-08-05T10:39:08+00:00 | — |
| poi_count_1km | 476 | OVERTURE_PLACES | 2026-08-05T09:30:50.528304+00:00 | 0.60 |
| proximity.airport | 4.56 km | FAA_NASR | 2026-08-05T09:30:54.040210+00:00 | — |
| proximity.school | 0.34 km | OVERTURE_PLACES | 2026-08-05T09:30:50.528061+00:00 | — |
| proximity.urban_area | 0.0 km | CENSUS_TIGER_URBAN | 2026-08-05T09:30:54.608346+00:00 | — |
| sewer_service_area_provenance | utility_sourced | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932089+00:00 | 0.90 |
| sewer_service_area_provider | Landis Sewerage Authority - CS/STP | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932078+00:00 | 0.90 |
| slope_degrees | 0.8287137746810913 degrees | USGS_3DEP_COG | 2026-08-05T09:30:42.700429+00:00 | 0.60 |
| soil_drainage_class | Well drained | NRCS_gNATSGO | 2026-08-05T09:30:43.489526+00:00 | 0.90 |
| state | Delaware | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| state_fips | 10 | US Census Geocoder | 2026-08-05T10:39:08+00:00 | — |
| timezone | America/New_York | IANA tz database | 2026-08-05T10:39:08+00:00 | — |
| tract_civilian_labor_force | 1300 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805330+00:00 | 0.60 |
| tract_geoid | 10001040100 | US Census Geocoder (2020 vintage) | 2026-08-05T10:39:08+00:00 | — |
| tract_population | 3259 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805388+00:00 | 0.60 |
| transmission_lines_within_radius_count | 1 | EIA_POWER | 2026-08-05T09:30:51.042584+00:00 | 0.90 |
| tree_canopy_pct | 1.0 percent | USFS_NLCD_TCC | 2026-08-05T09:30:43.587699+00:00 | 0.90 |
| water_service_area_provenance | utility_sourced | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977658+00:00 | 0.90 |
| water_system_name | VINELAND WATER & SEWER UTILITY | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977646+00:00 | 0.90 |
| within_floodplain | False | FEMA NFHL | 2026-08-05T10:39:08+00:00 | — |
| within_sewer_service_area | True | EPA_SEWERSHEDS | 2026-08-05T09:30:51.931970+00:00 | 0.90 |
| within_water_service_area | True | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977539+00:00 | 0.90 |

*Generated 2026-08-05T10:39:47+00:00 · Claude Agent SDK tool-calling loop (claude-opus-5) · 14 tool calls · 133 credits.*

*Screen, not an applicability determination. A licensed professional signs that opinion and carries the liability.*