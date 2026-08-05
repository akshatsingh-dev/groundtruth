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

**Move 37 miles SSW to Kent County, DE. Major PSD instead of Major nonattainment NSR. Save ~39 months.**

- Kent County, DE at 39.0184, -75.3729
- Major PSD, 16–40 months
- 37 miles from the announced site
- Clears: ej_denial_authority, major_nonattainment_nsr, nonattainment_designation, ozone_transport_region, state_toxics
- Adds: major_psd
- Screened 21 of 24 parcels out to 120 km for 120 credits

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

- `nearest_class_i_area_km` — error. field_request needs at least one example location — it is what seeds the build's eval cases and where the field is verified on prod
- `background_pm25_ug_m3` — error. field_request needs at least one example location — it is what seeds the build's eval cases and where the field is verified on prod

## Agent's read

Major nonattainment NSR: 41-104 months (likely 66) Deciding factors: major nonattainment nsr (+6 mo); ej denial authority (+4 mo); ozone transport region (+3 mo)

## What this does not know

- Nearest Class I area distance is unknown. It was requested via the provider's field-request route. A Class I area inside 100 km adds a Federal Land Manager review that can stop a project on visibility grounds alone.
- PSD increment consumption by existing major sources is unknown. A consumed increment can make a site un-permittable at any timeline.
- This is a screen, not an applicability determination. A licensed professional signs that opinion and carries the liability.
- The agent drafts and ranks. It does not contact agencies, file anything, or send anything. Drafts land in outputs/drafts/ for a person to review.

## Provenance

Every physical fact with its source, fetch timestamp and confidence.

| Field | Value | Source | Fetched | Confidence |
|---|---|---|---|---:|
| aspect_cardinal | S | USGS_3DEP_COG | 2026-08-05T09:30:42.700466+00:00 | 0.60 |
| bedrock_depth_cm | 4800.0 centimeters | PELLETIER_DTB | 2026-08-05T09:30:43.496043+00:00 | 0.30 |
| block_geoid | 340110411012017 | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| block_group_geoid | 340110411012 | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| cbsa_code | 47220 | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| cbsa_name | Vineland, NJ Metro Area | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| cdl_class | Developed/High Intensity | USDA_NASS_CDL | 2026-08-05T09:30:43.577539+00:00 | 0.60 |
| coast_distance_m | 9618.396788994687 meters | NOAA_CUSP | 2026-08-05T09:30:42.703785+00:00 | 0.90 |
| coastal_high_hazard | False | FEMA NFHL | 2026-08-05T09:50:28+00:00 | — |
| congressional_district | NJ-02 | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| county | Cumberland County | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| county_fips | 34011 | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| county_market.building_permits_sf_annual | 143 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.building_permits_total_annual | 143 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.building_permits_yoy_pct | -43.4783 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.employment_total | 60285 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.employment_yoy_pct | 1.0002 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.hpi_yoy_pct | 9.61 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.median_household_income_usd | 64499 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.net_domestic_migration | 148 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.population | 157148 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_market.population_growth_1yr_pct | 0.4738 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:50:28+00:00 | — |
| county_median_household_income | 64499 USD | CENSUS_ACS | 2026-08-05T09:50:29.525453+00:00 | 0.60 |
| county_population | 157148 people | CENSUS_PEP | 2026-08-05T09:50:29.525216+00:00 | 0.60 |
| county_population_growth_1yr_pct | 0.4738 percent | CENSUS_PEP | 2026-08-05T09:50:29.525334+00:00 | 0.60 |
| domestic_well_household_density_class | none | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992867+00:00 | 0.60 |
| domestic_well_households_per_km2 | 0.0 households/km2 | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992791+00:00 | 0.60 |
| dominant_crop_5y | None | USDA_NASS_CDL | 2026-08-05T09:30:43.579999+00:00 | 0.60 |
| egrid_subregion | RFCE | EPA_EGRID | 2026-08-05T09:50:28.786868+00:00 | 0.90 |
| electric_utility_service_territory | CITY OF VINELAND - (NJ) | EIA_POWER | 2026-08-05T09:30:51.039971+00:00 | 0.90 |
| elevation | 32.64278030395508 meters | USGS_3DEP_COG | 2026-08-05T09:30:42.699564+00:00 | 0.60 |
| elevation_m | 32.64278030395508 meters | USGS 3DEP/EPQS | 2026-08-05T09:50:28+00:00 | — |
| fema_flood_zone | X | FEMA NFHL | 2026-08-05T09:50:28+00:00 | — |
| housing_units_density_per_km2 | 653.818075328233 units/km2 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568353+00:00 | 0.60 |
| housing_units_within_1km | 3148 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568270+00:00 | 0.60 |
| in_opportunity_zone | True | US Treasury Qualified Opportunity Zones | 2026-08-05T09:50:28+00:00 | — |
| interconnection_queue_active_capacity_caiso_mw | None MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784876+00:00 | 0.60 |
| interconnection_queue_active_capacity_county_mw | 106.35 MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784780+00:00 | 0.60 |
| interconnection_queue_active_capacity_ercot_mw | None MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784865+00:00 | 0.60 |
| interconnection_queue_active_capacity_isone_mw | None MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784919+00:00 | 0.60 |
| interconnection_queue_active_capacity_miso_mw | None MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784853+00:00 | 0.60 |
| interconnection_queue_active_capacity_nyiso_mw | None MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784909+00:00 | 0.60 |
| interconnection_queue_active_capacity_pjm_mw | 106.35 MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784836+00:00 | 0.60 |
| interconnection_queue_active_capacity_southeast_mw | None MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784938+00:00 | 0.60 |
| interconnection_queue_active_capacity_spp_mw | None MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784886+00:00 | 0.60 |
| interconnection_queue_active_capacity_west_mw | None MW | LBNL_QUEUED_UP | 2026-08-05T09:50:28.784928+00:00 | 0.60 |
| iso_rto | PJM | HIFLD_ISO_RTO | 2026-08-05T09:50:28.773719+00:00 | 0.60 |
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
| nearest_power_plant_operator | City of Vineland - (NJ) | EIA_POWER | 2026-08-05T09:30:51.245639+00:00 | 0.90 |
| nearest_power_plant_primary_fuel | natural gas | EIA_POWER | 2026-08-05T09:30:51.245617+00:00 | 0.90 |
| nearest_power_plant_technology | Natural Gas Fired Combustion Turbine | EIA_POWER | 2026-08-05T09:30:51.245649+00:00 | 0.90 |
| nearest_proposed_generator_capacity_mw | 7.0 megawatts | EIA_860M | 2026-08-05T09:50:28.775632+00:00 | 0.60 |
| nearest_proposed_generator_distance_m | 29009.4 meters | EIA_860M | 2026-08-05T09:50:28.775590+00:00 | 0.60 |
| nearest_proposed_generator_status | TS) CONSTRUCTION COMPLETE, BUT NOT YET IN COMMERCIAL OPERATION | EIA_860M | 2026-08-05T09:50:28.775645+00:00 | 0.60 |
| nearest_restaurant_distance_m | 37.72996305035379 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528102+00:00 | 0.60 |
| nearest_restaurant_name | Carolyn's Bistro | OVERTURE_PLACES | 2026-08-05T09:30:50.528111+00:00 | 0.60 |
| nearest_school_distance_m | 343.806679659307 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528061+00:00 | 0.60 |
| nearest_school_name | Vineland Public Schools | OVERTURE_PLACES | 2026-08-05T09:30:50.528070+00:00 | 0.60 |
| nearest_sewer_service_area_distance_m | 0.0 meters | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932099+00:00 | 0.90 |
| nearest_shopping_center_distance_m | 296.00006868374055 meters | OVERTURE_PLACES | 2026-08-05T09:30:50.528270+00:00 | 0.60 |
| nearest_shopping_center_name | The Spot At The Ave | OVERTURE_PLACES | 2026-08-05T09:30:50.528282+00:00 | 0.60 |
| nearest_substation_distance_m | 723.4 meters | EIA_POWER | 2026-08-05T09:30:51.052008+00:00 | 0.90 |
| nearest_substation_max_voltage_kv | None kV | EIA_POWER | 2026-08-05T09:30:51.052030+00:00 | 0.90 |
| nearest_substation_status | IN SERVICE | EIA_POWER | 2026-08-05T09:30:51.052040+00:00 | 0.90 |
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
| opportunity_zone_tract_geoid | 34011041100 | US Treasury Qualified Opportunity Zones | 2026-08-05T09:50:28+00:00 | — |
| parcel | 39.4862,-75.0257 | caller-supplied coordinate | 2026-08-05T09:50:28+00:00 | — |
| parcel_apn | 0614_2926_1 | REGRID | 2026-08-05T09:50:30.946011+00:00 | 0.60 |
| parcel_area_m2 | 837.051782409216 square_meters | REGRID | 2026-08-05T09:50:30.945903+00:00 | 0.60 |
| parcel_boundary_geojson | {"type":"Polygon","coordinates":[[[-75.025912,39.4871495],[-75.0259755,39.486327],[-75.0258695,39.486322],[-75.0258055,39.4871445],[-75.025912,39.4871495]]]} | REGRID | 2026-08-05T09:50:30.946110+00:00 | 0.60 |
| parcel_id | 9d65f767-3976-40eb-8733-c273c7b55859 | REGRID | 2026-08-05T09:50:30.945978+00:00 | 0.60 |
| parcel_owner | CITY OF VINELAND | REGRID | 2026-08-05T09:50:30.946120+00:00 | 0.60 |
| parcel_zoning | LMS | REGRID | 2026-08-05T09:50:30.946131+00:00 | 0.60 |
| poi_count_1km | 476 | OVERTURE_PLACES | 2026-08-05T09:30:50.528304+00:00 | 0.60 |
| proximity.airport | 4.56 km | FAA_NASR | 2026-08-05T09:30:54.040210+00:00 | — |
| proximity.school | 0.34 km | OVERTURE_PLACES | 2026-08-05T09:30:50.528061+00:00 | — |
| proximity.substation | 0.72 km | EIA_POWER | 2026-08-05T09:30:51.052008+00:00 | — |
| proximity.transmission | 0.72 km | EIA_POWER | 2026-08-05T09:30:51.042494+00:00 | — |
| proximity.urban_area | 0.0 km | CENSUS_TIGER_URBAN | 2026-08-05T09:30:54.608346+00:00 | — |
| sewer_service_area_provenance | utility_sourced | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932089+00:00 | 0.90 |
| sewer_service_area_provider | Landis Sewerage Authority - CS/STP | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932078+00:00 | 0.90 |
| slope_degrees | 0.8287137746810913 degrees | USGS_3DEP_COG | 2026-08-05T09:30:42.700429+00:00 | 0.60 |
| soil_drainage_class | Well drained | NRCS_gNATSGO | 2026-08-05T09:30:43.489526+00:00 | 0.90 |
| state | New Jersey | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| state_fips | 34 | US Census Geocoder | 2026-08-05T09:50:28+00:00 | — |
| substations_radius_m | 10000.0 meters | EIA_POWER | 2026-08-05T09:30:51.051967+00:00 | 0.90 |
| substations_within_radius_count | 8 | EIA_POWER | 2026-08-05T09:30:51.052048+00:00 | 0.90 |
| timezone | America/New_York | IANA tz database | 2026-08-05T09:50:28+00:00 | — |
| tract_civilian_labor_force | 1300 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805330+00:00 | 0.60 |
| tract_geoid | 34011041101 | US Census Geocoder (2020 vintage) | 2026-08-05T09:50:28+00:00 | — |
| tract_population | 3259 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805388+00:00 | 0.60 |
| transmission_lines_within_radius_count | 1 | EIA_POWER | 2026-08-05T09:30:51.042584+00:00 | 0.90 |
| transmission_redundancy_flag | False | MIREYE_DERIVED_SITING | 2026-08-05T09:30:51.245933+00:00 | 0.60 |
| tree_canopy_pct | 1.0 percent | USFS_NLCD_TCC | 2026-08-05T09:30:43.587699+00:00 | 0.90 |
| water_service_area_provenance | utility_sourced | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977658+00:00 | 0.90 |
| water_system_name | VINELAND WATER & SEWER UTILITY | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977646+00:00 | 0.90 |
| wind_least_cost_interconnect_distance_m | 25731.597385039327 m | NREL_REV_LANDBASED_WIND_SC_2024 | 2026-08-05T09:50:28.804589+00:00 | 0.60 |
| within_floodplain | False | FEMA NFHL | 2026-08-05T09:50:28+00:00 | — |
| within_sewer_service_area | True | EPA_SEWERSHEDS | 2026-08-05T09:30:51.931970+00:00 | 0.90 |
| within_water_service_area | True | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977539+00:00 | 0.90 |

*Generated 2026-08-05T09:54:11+00:00 · deterministic fallback (no LLM) · 9 tool calls · 135 credits.*

*Screen, not an applicability determination. The agent does not contact agencies, file anything, or send anything.*