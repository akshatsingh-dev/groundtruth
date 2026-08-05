# Screen — 39.4862,-75.0257

400 MW simple_cycle_turbine on natural_gas (uncontrolled), no enforceable hour cap (PTE at 8760)

## 2% probability of energizing on the announced schedule

- 16 months to the announced date. 3 months to prepare a complete application plus 36 months of agency review = 39 months required.
- Slack -23 months against a sigma of 8.5 months, taken from the 23-57 month range for Major nonattainment NSR.

*Model:* The air permit is treated as the critical path. Months available is the target energization date minus today. Months required is the pre-application preparation period plus the pathway's likely duration for that state agency. The pathway's own optimistic-to-pessimistic spread is read as roughly plus or minus two standard deviations, so sigma = (high - low) / 4, floored at one month. The probability is the normal CDF of slack over sigma, clipped to [0.02, 0.97] because nothing here justifies claiming certainty. Hard stops are a hard cap at 0.05: a moratorium, an unavailable offset market or a consumed increment is not a schedule risk, it is a different outcome. Turbine delivery, construction and interconnection are not modelled — they are separate constraints and each is documented as binding on its own.

## Pathway

**Major nonattainment NSR** — 23–57 months, likely 36.

Controlling pollutant: NOx at 5,887 tpy against a 50 tpy threshold.

Source category: Simple cycle, no steam cycle, so not a 'steam electric plant' and no boiler. Not a listed category despite 4,200 MMBtu/hr of heat input. Major source threshold is 250 tpy. Worth confirming with the state — a few agencies read the boiler entry more broadly than EPA does.

*40 CFR 52.21(b)(1)(i)(a); the 'List of 28' named source categories*

## Triggers that fired

| Trigger | Months added | Detail | Citation |
|---|---:|---|---|
| nonattainment designation | 0 | Cumberland County County, NE is designated nonattainment for: ozone (serious, Philadelphia-Atlantic City, PA-NJ); ozone (marginal, Philadelphia-Atlantic City, PA-NJ). | EPA Green Book, 40 CFR 81 |
| major nonattainment nsr | 6 | NOx PTE of 5,887 tpy is over the 50 tpy major threshold for a serious ozone nonattainment area. Requires LAER (no cost defense, unlike BACT) and 1.20:1 emission offsets — 7,064 tons of verified reductions bought from existing sources in the area. | CAA 173; 40 CFR 51.165(a)(1)(iv)(A) |
| title v | 0 | Title V operating permit required — criteria pollutant PTE 5,887 tpy over 100 tpy. Runs after the construction permit; usually does not block construction but does add annual compliance cost and a public comment window of its own. | 40 CFR Part 70 |
| nsps turbine | 0 | NSPS Subpart KKKK applies, and EPA's 15 January 2026 rule (91 Fed. Reg. 1910) added Subpart KKKKa. That rule did not settle the trailer-mounted question, and it did not settle it in the direction most coverage claims. It finalised a conditional exclusion removing turbines from the 'stationary combustion turbine' definition where the unit qualifies as a nonroad engine and is certified under Title II. The exclusion is not operative: it takes effect only if EPA adopts Title II standards for portable turbines, a separate rulemaking that has not happened. Meanwhile the NAACP is asking a federal court in Mississippi to shut down 27 unpermitted turbines at xAI's Colossus 2, with a preliminary injunction hearing set for late August 2026. Underwriting a trailer-mounted fast path today means underwriting an open legal question, not a loophole. | 40 CFR 60 Subpart KKKK and new Subpart KKKKa; 91 Fed. Reg. 1910 (15 Jan 2026); NAACP v. xAI (N.D. Miss.), PI hearing late Aug 2026 |

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

- Stopped at candidate 14: lookup x1 costs 1 credits, 0 left
- Screened 13 parcels out to 120 km and none improved on Major nonattainment NSR. The constraint is not the parcel; it is the config or the region.

## Config alternatives at this parcel

| Change | Pathway | Likely | Months saved | Availability | What it costs |
|---|---|---:|---:|---:|---|
| Switch to solid oxide fuel cells | Minor NSR construction permit | 6 | +30 | 100% | Solid oxide fuel cells emit almost no criteria pollutants, which usually takes the air permit off the critical path entirely. CO2 is not solved — they still burn gas. Much higher capital cost per MW, a supplier list you can count on one hand, and lead times that are themselves the constraint at data center scale. |
| Add SCR | Major nonattainment NSR | 36 | +0 | 100% | SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. |
| Add oxidation catalyst | Major nonattainment NSR | 36 | +0 | 100% | An oxidation catalyst cuts CO by about 90% and VOC by about half. No reagent, no storage tank, small pressure drop, and it is cheap next to SCR. Worth checking first whenever CO is the pollutant sitting over the threshold — on an uncontrolled turbine that is more often the case than people expect. |
| Add SCR + oxidation catalyst | Major nonattainment NSR | 36 | +0 | 100% | SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. An oxidation catalyst cuts CO by about 90% and VOC by about half. No reagent, no storage tank, small pressure drop, and it is cheap next to SCR. Worth checking first whenever CO is the pollutant sitting over the threshold — on an uncontrolled turbine that is more often the case than people expect. |
| Add dry low-NOx combustors | Major nonattainment NSR | 36 | +0 | 100% | Dry low-NOx combustors are a turbine specification, not an add-on: you order the machine that way. No reagent and no aftertreatment, but the reduction is smaller than SCR and there are turndown and CO trade-offs at part load. |
| Switch simple cycle to combined cycle | Major nonattainment NSR | 36 | +0 | 100% | Combined cycle burns roughly two thirds the fuel per MWh, so tons per year drop with no control equipment at all. The catch is legal, not thermal: the HRSG and steam turbine make the plant a 'fossil fuel-fired steam electric plant' over 250 MMBtu/hr, which drops the PSD major threshold from 250 tpy to 100 tpy. Check both directions before assuming it helps. Also adds water, a longer build, and a second machine in an order book already full. |
| Combined cycle + SCR + oxidation catalyst | Major nonattainment NSR | 36 | +0 | 100% | Combined cycle burns roughly two thirds the fuel per MWh, so tons per year drop with no control equipment at all. The catch is legal, not thermal: the HRSG and steam turbine make the plant a 'fossil fuel-fired steam electric plant' over 250 MMBtu/hr, which drops the PSD major threshold from 250 tpy to 100 tpy. Check both directions before assuming it helps. Also adds water, a longer build, and a second machine in an order book already full. SCR is the standard NOx answer and it is also the expensive one: catalyst, reactor volume in the exhaust path, and an ammonia or urea storage and handling system on site, which brings its own safety review and often its own local permit. Small heat-rate penalty from the pressure drop. It does nothing for CO. |
| Split into two separate sources | Major nonattainment NSR | 39 | -3 | 100% | Splitting the plant only works if the pieces are genuinely separate stationary sources. Units serving one campus, under one owner, will be aggregated. Treat this as a conversation with the agency, not a design decision. |

> Accept a run-hour cap (as designed): Holding NOx under 50 tpy would need a cap of 67 hr/yr (1% availability). That is not a data center power plant, it is a peaker.

> Accept a run-hour cap, with SCR and oxidation catalyst: Holding NOx under 50 tpy would need a cap of 670 hr/yr (8% availability). That is not a data center power plant, it is a peaker.

## Field requests

- `class_i_area_distance_km` — error. field_request needs at least one example location — it is what seeds the build's eval cases and where the field is verified on prod
- `class_i_area_distance_km` — error. field_request needs at least one example location — it is what seeds the build's eval cases and where the field is verified on prod

## Agent's read

I'll start with step 1 — potential to emit — because that's free and it decides which physical facts are worth buying. In parallel I'll resolve the site, since everything after step 1 depends on the county.

**Step 1 — PTE. Done, and it settles most of this.** Uncontrolled 400 MW simple-cycle gas turbine at 8760 hr/yr: **NOx 5,886.7 tpy**, CO 1,508.5 tpy, PM2.5 121.4 tpy, CO2e 2.02 Mtpy (AP-42 Table 3.1-1/3.1-2a/3.1-3, module default heat rate 10,500 Btu/kWh, fetched 2026-08-05T09:30:09Z). There is no enforceable cap, so 8760 is the correct basis. NOx is ~147× the 40 tpy PSD significant emission rate and ~23× the 250 tpy major-source threshold. This is not a close call.

**Step 2 — source category.** A simple-cycle combustion turbine is not a "fossil fuel-fired steam electric plant," so it is not on the List of 28 and the PSD major threshold stays 250 tpy rather than dropping to 100. Irrelevant to the outcome at 5,887 tpy, but it matters for the combined-cycle option later.

**Step 3 — site.** Resolved to county FIPS 34011 = **Cumberland County, New Jersey** (US Census Geocoder, fetched 2026-08-05T09:30:11Z), consistent with the caller's declared jurisdiction. One flag: the resolver's top-level `state` field returned "NE" while `state_fips`=34 and `state`="New Jersey" in the lookup facts. FIPS 34011 is unambiguously Cumberland County NJ, so I'm proceeding on that, but the inconsistency is a data-quality gap. Second flag: the tool says NJ is **not one of the eight individually modelled agencies**, so the timeline it returns is a federal default with no NJDEP-specific adjustment. That is a real gap, and NJDEP is one of the slower and more aggressive agencies in the country.

**Provider calls I'm choosing, and why:** attainment status first — NOx is an ozone precursor and Cumberland County sits in the Philadelphia ozone region, which is the fact most likely to flip this from PSD to nonattainment NSR. Terrain and land cover because AERMOD is certain at this emission level and coastal-plain surface roughness drives the dispersion run. Demographics and points of interest because New Jersey has an actual EJ denial statute (N.J.S.A. 13:1D-157) and Cumberland is a low-income county — this is the one state where EJ can kill a permit outright, not just delay it. Utilities plus gas pipeline distance because it is a gas config and fuel reachability is the classic non-air failure. Airport for stack height review. Skipping flood, soil, wildfire, grid_interconnect (not grid-tied, per the brief).

Three things jump out before I run the pathway, and I want them on the record.

**Attainment is the flip.** Cumberland County is in the Philadelphia-Atlantic City PA-NJ **serious** ozone nonattainment area under the 2015 8-hour standard (EPA Green Book / 40 CFR 81, fetched 2026-07-31). NOx is an ozone precursor. In a serious ozone area the major-source threshold for NOx drops from 250 tpy to **50 tpy**. This project's NOx PTE is 5,886.7 tpy — roughly 118× the applicable threshold. That is nonattainment NSR, not PSD.

**The parcel is in the middle of a city.** Land cover comes back "Developed / High Intensity," tree canopy 1%, and the point sits *inside* a Census urban area (USFS LCMS and Census TIGER, fetched 2026-08-05T09:30:43Z and 09:30:54Z). Nearest school 344 m, nearest hospital 178 m, nearest restaurant 38 m, 476 POIs within 1 km (Overture Places, fetched 09:30:50Z). This is downtown Vineland.

**Gas pipeline came back `missing`.** For a 4,200 MMBtu/hr gas turbine that is the single most important non-air fact and I do not have it. Chasing it now.

I'm also correcting two of the tool's own overlay flags below, and requesting the Class I distance it lists as an unknown.

**Step 6 — the pathway is in, and it does not clear the schedule.** Major nonattainment NSR: 23 months best case, 36 likely, 57 high. Announced energization is 16 months away. And the gas answer is bad: nearest interstate transmission pipeline is Columbia Gas Transmission at **34.0 km** (HIFLD, fetched 2026-08-05T09:30:54Z), with EIA's 10 km buffer returning null. A 4,200 MMBtu/hr turbine needs a dedicated ~34 km lateral through developed southern New Jersey — that is a second permitting program on its own critical path.

**Step 7 — acting on it.** Two free config probes, and a retry of the Class I request, which failed on a tooling technicality rather than a data gap.

SCR + DLN + oxidation catalyst cuts NOx from 5,887 to 182.5 tpy and drops the offset obligation from 7,064 tons to 219 tons — that is the difference between an impossible ERC purchase and a merely expensive one. But it does **not** change the pathway. 182.5 tpy is still over the 50 tpy serious-ozone threshold, so it is still major nonattainment NSR at 23/36/57 months. No control package gets a real 400 MW gas turbine under 50 tpy NOx.

The site fails on schedule, not on a fixable detail. That is the condition for searching outward. Retrying the fuel cell probe alongside it.

I've used 13 of 14 calls. Stopping here.

## Closing assessment

**The pathway is major nonattainment NSR. Likely 36 months, range 23 to 57. The announced date is 16 months out. It does not fit.**

Here is the chain. A 400 MW uncontrolled simple-cycle gas turbine has a NOx potential to emit of 5,886.7 tpy at 8760 hours. The turbine is not a steam electric plant, so it is not on the List of 28 and the PSD threshold stays 250 tpy — but that never governs, because Cumberland County is in the Philadelphia-Atlantic City **serious** ozone nonattainment area, which drops the NOx major-source threshold to 50 tpy. NOx is the ozone precursor. The project is 118× over. That brings LAER, which has no cost defense, and 1.2:1 offsets: **7,064 tons of verified reductions bought from existing sources in the Philadelphia airshed.**

**Three things actually decide this.**

First, offsets. Uncontrolled, you need 7,064 tons of ERCs. I do not believe that quantity exists for sale in this nonattainment area, and I do not have market data to prove it either way — that is a gap you should close with a broker before anything else. Add SCR, dry low NOx and an oxidation catalyst and NOx falls to 182.5 tpy and the offset obligation falls to 219 tons. That is procurable. It is the single highest-leverage change available and it costs you nothing in availability. It still does not change the pathway — 182.5 is still over 50 — but it converts an impossible transaction into a merely expensive one.

Second, the parcel. This is not a greenfield. The point sits inside a Census urban area, land cover is Developed/High Intensity, canopy 1%, with a school 344 m away, a hospital 178 m away, a restaurant 38 m away and 476 points of interest within 1 km. This is downtown Vineland. Putting a 4,200 MMBtu/hr turbine here means a dispersion model full of close-in receptors and a public process that will be contested. I asked the provider whether the coordinate falls in an NJDEP-designated overburdened community under the state EJ law and **it has no data for that field**. Given the demographics of this county, assume it does until someone checks the NJDEP mapping tool. New Jersey's EJ statute carries actual denial authority, not just a comment requirement.

Third, gas. The nearest interstate pipeline is Columbia Gas Transmission at 34 km. EIA's 10 km buffer returned null. You would be building a 34 km lateral through developed South Jersey, with its own routing, wetlands and easement process, in parallel. That is the classic non-air failure mode and it is on the critical path.

**Two corrections to the engine output that you should not skip.**

The tool reports the state as "NE" and describes the permitting authority as "a state agency not individually modelled," with the Ozone Transport Region flag false and EJ denial authority false. FIPS 34011 is New Jersey. All of New Jersey is in the statutory Ozone Transport Region under CAA §184(a), and New Jersey does have an EJ denial statute. So the 23/36/57 month range is a bare federal default with no NJDEP adjustment applied. Treat it as a floor, not an estimate.

The engine also lists `class_i_aqrv` as clear while listing `class_i_area_distance` as an unknown in the same response. That is a false negative, not a clean result. Brigantine Wilderness sits on the South Jersey coast and is plausibly inside the 100 km radius that triggers Federal Land Manager notification and visibility analysis. I tried twice to request that field and the request tool errored both times on its own input validation. Unresolved. Also unresolved: consumed PSD increment and background ambient ozone/NO2 at this coordinate.

**What I would change.** Searching outward does not rescue this. Every resolved candidate out to the searched rings came back on the same pathway with zero months saved, because the nonattainment area and the Ozone Transport Region are regional, not local — you cannot drive far enough within reach to escape them. The lever is the prime mover, not the parcel. A 400 MW fuel cell on the same site drops NOx to 3.2 tpy and CO to 9.1 tpy, lands on **minor NSR at 4 to 10 months**, clears Title V, and saves 30 months. That is the only configuration screened here that fits the announced energization date. It is not free — heat rate, capital cost and vendor scale for 400 MW of solid oxide are real questions I have not priced, and CO2e is still 1.43 Mtpy — but on air deliverability alone it is the only thing that works at this address.

If the turbine is non-negotiable, then the honest answer is that energization slips to roughly 2029 to 2031, and you should be buying ERC options now rather than optioning land.

I have not contacted NJDEP, filed anything, or reserved any offsets. These are screening conclusions for a human to act on.

## What this does not know

- Nearest Class I area distance is unknown. It was requested via the provider's field-request route. A Class I area inside 100 km adds a Federal Land Manager review that can stop a project on visibility grounds alone.
- PSD increment consumption by existing major sources is unknown. A consumed increment can make a site un-permittable at any timeline.
- This is a screen, not an applicability determination. A licensed professional signs that opinion and carries the liability.
- The agent drafts and ranks. It does not contact agencies, file anything, or send anything. Drafts land in outputs/drafts/ for a person to review.

## Provenance

Every physical fact with its source, fetch timestamp and confidence.

| Field | Value | Source | Fetched | Confidence |
|---|---|---|---|---:|
| ask.answer | **Interstate Natural Gas Transmission Pipeline:** The nearest EIA interstate natural-gas transmission pipeline is operated by Columbia Gas Trans Co, located approximately 34,019 meters (34.0 km) from the coordinate. Note that the EIA 10 km proximity buffer returned null (no pipeline within 10 km), consistent with this greater distance; the unbounded HIFLD search confirmed the 34.0 km figure. Diameter, operating pressure, and firm transport capacity are pipeline-operator confirmations and cannot be determined from geospatial data — those specifics would require direct inquiry with Columbia Gas Transmission. For context, the nearest electric transmission line (69.0 kV, sub-transmission grade) is only 723.4 meters away, but that is an electric, not gas, asset.

**NJ DEP Overburdened Community (N.J.S.A. 13:1D-157):** We do not have data for NJ DEP Environmental Justice overburdened community block group designation at this coordinate. No field covering NJ DEP EJ overburdened community status was returned in the fetched data, so no determination can be made from available sources. For underwriting or permitting purposes, this should be verified directly via the NJ DEP Environmental Justice mapping tool or the official overburdened communities list published under the NJ Environmental Justice Law. | Mireye /v1/ask over EIA_POWER, HIFLD_GAS_TRANSMISSION_PIPELINES | 2026-08-05T09:31:25.627991+00:00 | 0.60 |
| ask.citations | [{'source': 'EIA_POWER', 'source_url': 'https://atlas.eia.gov/', 'fields': ['nearest_transmission_line_distance_m', 'nearest_transmission_line_voltage_kv'], 'fetched_at': '2026-08-05T09:30:51.042494+00:00', 'confidence': 'high'}, {'source': 'HIFLD_GAS_TRANSMISSION_PIPELINES', 'source_url': 'https://atlas.eia.gov/', 'fields': ['nearest_interstate_gas_pipeline_distance_m', 'nearest_interstate_gas_pipeline_operator'], 'fetched_at': '2026-08-05T09:30:54.576798+00:00', 'confidence': 'high'}] | Mireye /v1/ask | 2026-08-05T09:31:25.627991+00:00 | — |
| ask.data_gaps | [{'field': 'nearest_gas_pipeline_distance_m', 'reason': 'source returned null: no gas pipeline within 10 km'}] | Mireye /v1/ask | 2026-08-05T09:31:25.627991+00:00 | — |
| ask.plan | {'fields_requested': ['nearest_transmission_line_distance_m', 'nearest_transmission_line_voltage_kv', 'nearest_gas_pipeline_distance_m', 'nearest_interstate_gas_pipeline_distance_m', 'nearest_interstate_gas_pipeline_operator'], 'preset_expanded': None, 'planner_model': 'claude-haiku-4-5', 'synthesizer_model': 'claude-sonnet-4-6'} | Mireye /v1/ask trace | 2026-08-05T09:31:25.627991+00:00 | — |
| aspect_cardinal | S | USGS_3DEP_COG | 2026-08-05T09:30:42.700466+00:00 | 0.60 |
| bedrock_depth_cm | 4800.0 centimeters | PELLETIER_DTB | 2026-08-05T09:30:43.496043+00:00 | 0.30 |
| block_geoid | 340110411012017 | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| block_group_geoid | 340110411012 | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| cbsa_code | 47220 | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| cbsa_name | Vineland, NJ Metro Area | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| cdl_class | Developed/High Intensity | USDA_NASS_CDL | 2026-08-05T09:30:43.577539+00:00 | 0.60 |
| coast_distance_m | 9618.396788994687 meters | NOAA_CUSP | 2026-08-05T09:30:42.703785+00:00 | 0.90 |
| coastal_high_hazard | False | FEMA NFHL | 2026-08-05T09:30:11+00:00 | — |
| congressional_district | NJ-02 | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| county | Cumberland County | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| county_fips | 34011 | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| county_market.building_permits_sf_annual | 143 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.building_permits_total_annual | 143 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.building_permits_yoy_pct | -43.4783 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.employment_total | 60285 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.employment_yoy_pct | 1.0002 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.hpi_yoy_pct | 9.61 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.median_household_income_usd | 64499 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.net_domestic_migration | 148 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.population | 157148 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_market.population_growth_1yr_pct | 0.4738 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:30:11+00:00 | — |
| county_median_household_income | 64499 USD | CENSUS_ACS | 2026-08-05T09:30:52.349617+00:00 | 0.60 |
| county_population | 157148 people | CENSUS_PEP | 2026-08-05T09:30:52.349412+00:00 | 0.60 |
| county_population_growth_1yr_pct | 0.4738 percent | CENSUS_PEP | 2026-08-05T09:30:52.349507+00:00 | 0.60 |
| domestic_well_household_density_class | none | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992867+00:00 | 0.60 |
| domestic_well_households_per_km2 | 0.0 households/km2 | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992791+00:00 | 0.60 |
| dominant_crop_5y | None | USDA_NASS_CDL | 2026-08-05T09:30:43.579999+00:00 | 0.60 |
| elevation | 32.64278030395508 meters | USGS_3DEP_COG | 2026-08-05T09:30:42.699564+00:00 | 0.60 |
| elevation_m | 32.64278030395508 meters | USGS 3DEP/EPQS | 2026-08-05T09:30:11+00:00 | — |
| fema_flood_zone | X | FEMA NFHL | 2026-08-05T09:30:11+00:00 | — |
| housing_units_density_per_km2 | 653.818075328233 units/km2 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568353+00:00 | 0.60 |
| housing_units_within_1km | 3148 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568270+00:00 | 0.60 |
| in_opportunity_zone | True | US Treasury Qualified Opportunity Zones | 2026-08-05T09:30:11+00:00 | — |
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
| opportunity_zone_tract_geoid | 34011041100 | US Treasury Qualified Opportunity Zones | 2026-08-05T09:30:11+00:00 | — |
| parcel | 39.4862,-75.0257 | caller-supplied coordinate | 2026-08-05T09:30:09+00:00 | — |
| poi_count_1km | 476 | OVERTURE_PLACES | 2026-08-05T09:30:50.528304+00:00 | 0.60 |
| proximity.airport | 4.56 km | FAA_NASR | 2026-08-05T09:30:54.040210+00:00 | — |
| proximity.school | 0.34 km | OVERTURE_PLACES | 2026-08-05T09:30:50.528061+00:00 | — |
| proximity.urban_area | 0.0 km | CENSUS_TIGER_URBAN | 2026-08-05T09:30:54.608346+00:00 | — |
| sewer_service_area_provenance | utility_sourced | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932089+00:00 | 0.90 |
| sewer_service_area_provider | Landis Sewerage Authority - CS/STP | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932078+00:00 | 0.90 |
| slope_degrees | 0.8287137746810913 degrees | USGS_3DEP_COG | 2026-08-05T09:30:42.700429+00:00 | 0.60 |
| soil_drainage_class | Well drained | NRCS_gNATSGO | 2026-08-05T09:30:43.489526+00:00 | 0.90 |
| state | New Jersey | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| state_fips | 34 | US Census Geocoder | 2026-08-05T09:30:11+00:00 | — |
| timezone | America/New_York | IANA tz database | 2026-08-05T09:30:11+00:00 | — |
| tract_civilian_labor_force | 1300 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805330+00:00 | 0.60 |
| tract_geoid | 34011041101 | US Census Geocoder (2020 vintage) | 2026-08-05T09:30:11+00:00 | — |
| tract_population | 3259 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805388+00:00 | 0.60 |
| transmission_lines_within_radius_count | 1 | EIA_POWER | 2026-08-05T09:30:51.042584+00:00 | 0.90 |
| tree_canopy_pct | 1.0 percent | USFS_NLCD_TCC | 2026-08-05T09:30:43.587699+00:00 | 0.90 |
| water_service_area_provenance | utility_sourced | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977658+00:00 | 0.90 |
| water_system_name | VINELAND WATER & SEWER UTILITY | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977646+00:00 | 0.90 |
| within_floodplain | False | FEMA NFHL | 2026-08-05T09:30:11+00:00 | — |
| within_sewer_service_area | True | EPA_SEWERSHEDS | 2026-08-05T09:30:51.931970+00:00 | 0.90 |
| within_water_service_area | True | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977539+00:00 | 0.90 |

*Generated 2026-08-05T09:36:30+00:00 · Claude Agent SDK tool-calling loop (claude-opus-5) · 13 tool calls · 80 credits.*

*Screen, not an applicability determination. The agent does not contact agencies, file anything, or send anything.*