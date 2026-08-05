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

**Move 37 miles NW to Delaware County, PA. Save ~27 months.**

- Delaware County, PA at 39.9220, -75.4393
- Major nonattainment NSR, 24–62 months
- 37 miles from the announced site
- Clears: ej_denial_authority, ozone_transport_region, state_toxics
- Screened 14 of 17 parcels out to 120 km for 80 credits

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

## Agent's read

I'll work this in order. Step 1 is potential to emit — free, and it decides what physical facts are worth buying.

Step 1 done, and it's decisive. **NOx PTE = 5,887 tpy** at 8760 hr/yr, uncontrolled. CO 1,509 tpy, PM2.5 121 tpy, CO2e 2.02 Mtpy, HAPs 13.1 tpy (single HAP formaldehyde). Every one of those is above its significant emission rate by one to two orders of magnitude.

Step 2, source category: a simple-cycle turbine is **not** a fossil fuel-fired steam electric plant, so it is not on the List of 28 and the PSD major threshold is **250 tpy**, not 100. That does not help — NOx is 24× the 250 tpy line either way. Note the corollary for later: converting to combined cycle would *drop* the threshold to 100 tpy.

Step 3, site: resolved cleanly to **Cumberland County, NJ (FIPS 34011)**, NJ DEP, matching the caller's declaration. No unverified label needed. The resolver already flags two things that decide this case: the whole state is in the **Ozone Transport Region**, so NOx is regulated as nonattainment regardless of local monitors, and NJ has an **environmental justice denial statute** (N.J.S.A. 13:1D-157).

Now the provider calls. I'm buying: **demographics and points_of_interest** because the NJ EJ statute is a denial authority and overburdened-community status is the single fact most likely to hard-stop this, and receptors drive it; **utilities** plus **gas_pipeline** because a 4,200 MMBtu/hr gas machine that cannot reach a pipeline is dead on a non-air failure mode; **school/urban_area/airport** as receptor and stack-height inputs. I'm **skipping terrain and land_cover** — the site is at 32.6 m on the flat Atlantic coastal plain (USGS 3DEP, fetched 2026-08-05T09:56:53Z), so complex-terrain receptors are very unlikely to drive AERMOD here, and I'd rather hold those credits for the alternate-site search that a failing site is going to need. Skipping grid_interconnect: declared not grid-tied. And I'm requesting Class I distance, which no preset covers and which matters because Brigantine Wilderness is in this state.

Step 4 and 5 are where this breaks. Two things landed:

**Attainment**: Cumberland is in the Philadelphia–Atlantic City PA-NJ nonattainment area, classified **serious** for the 2015 8-hour ozone NAAQS (EPA Green Book, fetched 2026-07-31). Serious ozone drops the NOx major threshold to 50 tpy. PTE is 5,887. That is 118× the line, and it triggers nonattainment NSR — LAER plus emission offsets, not PSD's BACT.

**Location**: the site is *inside* a Census urban area (0.0 m, CENSUS_TIGER_URBAN, fetched 2026-08-05T09:30:54Z), 344 m from Vineland Public Schools, 178 m from a medical facility, with 476 POIs within 1 km (OVERTURE_PLACES, fetched 2026-08-05T09:30:50Z). This is not a greenfield edge parcel. It is downtown Vineland, and NJ DEP holds outright denial authority in an overburdened community.

Two gaps I have to flag rather than paper over: **gas_pipeline came back `missing`** from the proximity provider — that is unresolved, not "no pipeline" and not "pipeline present." And the Class I field request was rejected on a schema error (needs a seeded example location), so **nearest Class I area distance remains unknown**, alongside PSD increment consumed and background ambient — all three named as unindexed gaps by the regulatory source itself.

Running the tree now.

Pathway is **major nonattainment NSR**: 41–104 months, 66 likely. Announced energization is 16 months. That gap is not closeable by working harder.

The binding number is offsets: **7,064 tons of verified NOx reductions at 1.2:1**, bought from existing sources inside the Philadelphia–Atlantic City area. That is a very thin market. Synthetic minor is already ruled out — a 50 tpy NOx cap means 67 run-hours a year, which is 1% availability.

Step 7, act. Testing whether any config at *this* parcel gets under the 50 tpy NOx line. These are free.

Only the fuel cell changes the pathway. Controls help enormously on the *offset bill* — SCR + DLN takes NOx from 5,887 to 182 tpy, and the offset requirement from 7,064 tons to 219 — but 182 is still over 50, so the pathway and the 66-month clock do not move.

The site fails. That is the condition for searching outward. I'm also testing how much gas capacity actually fits under the 50 tpy line, because that sizes a hybrid.

## Closing assessment

**The pathway is major nonattainment NSR. Likely 66 months, range 41 to 104. The announced date is 16 months. This project cannot be switched on as designed, and no amount of schedule pressure changes that.**

Here is what actually decides it.

**Serious ozone nonattainment sets the threshold at 50 tpy.** Cumberland County sits in the Philadelphia–Atlantic City PA-NJ area, serious for the 2015 8-hour ozone NAAQS (EPA Green Book, fetched 2026-07-31). New Jersey is also entirely inside the Ozone Transport Region, so that 50 tpy line applies statewide regardless of local monitors. Uncontrolled NOx PTE is 5,887 tpy. That is 118 times over. Note the threshold question I checked in step 2: a simple-cycle turbine is not a steam electric plant, so it is not on the List of 28 and PSD would be 250 tpy — but nonattainment NSR governs here and it is 50, so the source-category analysis never gets to matter.

**The offset requirement is the practical killer, not the paperwork.** Uncontrolled, this needs 7,064 tons of verified NOx reductions at 1.2:1, purchased from existing sources inside the Philadelphia area. That market does not have 7,064 tons in it. Adding SCR, dry low-NOx and an oxidation catalyst is genuinely worth doing — it takes NOx to 182 tpy and the offset bill to 219 tons, which is a purchasable quantity — but 182 is still above 50, so the pathway, the LAER obligation and the 66-month clock all stay exactly where they were.

**Then there is the discretionary denial risk, which no engineering fixes.** The site is inside a Census urban area (0.0 m, CENSUS_TIGER_URBAN, 2026-08-05T09:30:54Z), 344 m from Vineland Public Schools and 178 m from a medical facility, with 476 POIs within 1 km (OVERTURE_PLACES, 2026-08-05T09:30:50Z). This is a downtown parcel. NJ DEP holds authority under N.J.S.A. 13:1D-157 to deny a permit outright in an overburdened community, independent of whether the modeling passes. Siting a 4,200 MMBtu/hr uncontrolled turbine 344 m from a school district in an OTR state with a denial statute is the Nebius failure mode, and I would treat approval here as unlikely rather than slow.

**What I would change.** Two configs cross to minor NSR at this parcel, and both land at 21.6 months likely, 12.4 at the optimistic end. A 400 MW fuel cell drops criteria pollutants to near nothing (CO 9 tpy) — though CO2e stays at 1.43 Mtpy, which is a climate-disclosure and state-policy exposure, not an NSR one. Or roughly 150 MW of combined cycle with SCR and DLN, which comes in at 41.7 tpy NOx. That second number is the useful one: it tells you about 150 MW is all the gas capacity that fits under the line at this site. A hybrid — 150 MW gas plus fuel cells or grid import for the balance — is the only shape of a 400 MW project that permits here on a sane timeline. Watch the trap I tested for: combined cycle pulls you onto the List of 28 and drops the PSD threshold from 250 to 100 tpy. It works at 150 MW anyway, but it narrows your headroom.

**Relocation does not rescue this one.** I searched 17 candidates out to 120 km. The best alternates are Delaware County, PA and New Castle County, DE, both about 60 km out, both at 39 months. They clear the EJ denial authority and the state toxics overlay, saving 27 months, and Delaware County has gas 0.6 km away. But both are *still* major nonattainment NSR. There is no attainment parcel within 120 km of here. Moving is worth 27 months; it is not worth a pathway change. Config is the lever in this region, not geography.

**Three gaps you should not read as clean results.** Gas pipeline distance came back `missing` from the proximity provider for this site — that is unresolved, not "no pipeline." Nearest Class I area distance is unknown; my field request was rejected on a schema error because it needs a seeded example location, and Brigantine Wilderness is in this state, so this could add 6 to 12 months if the site falls within range. PSD increment consumed and background ambient concentrations are also unindexed, confirmed as gaps by the regulatory source itself. I skipped terrain and land cover deliberately — 32.6 m elevation on flat coastal plain (USGS 3DEP, 2026-08-05T09:56:53Z) means complex-terrain receptors almost certainly do not drive the modeling, and I spent those credits on the site search instead.

One more thing to price in: there are two active federal cases in D.N.J. touching this county or developer, including a torts-to-land action filed 2026-05-26 (CourtListener/RECAP). And if anyone proposes trailer-mounted turbines as a fast path — the January 2026 rule did not create that loophole. The exclusion is conditional and not operative, and there is a preliminary injunction hearing in the xAI Colossus 2 matter late this month.

I have not contacted NJ DEP or filed anything. This is a screen for you to act on, not an action.

## What this does not know

- Nearest Class I area distance is unknown. It was requested via the provider's field-request route. A Class I area inside 100 km adds a Federal Land Manager review that can stop a project on visibility grounds alone.
- PSD increment consumption by existing major sources is unknown. A consumed increment can make a site un-permittable at any timeline.
- This is a screen, not an applicability determination. A licensed professional signs that opinion and carries the liability.
- The agent drafts and ranks. It does not contact agencies, file anything, or send anything. Drafts land in outputs/drafts/ for a person to review.

## Provenance

Every physical fact with its source, fetch timestamp and confidence.

| Field | Value | Source | Fetched | Confidence |
|---|---|---|---|---:|
| block_geoid | 340110411012017 | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| block_group_geoid | 340110411012 | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| cbsa_code | 47220 | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| cbsa_name | Vineland, NJ Metro Area | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| coastal_high_hazard | False | FEMA NFHL | 2026-08-05T09:56:53+00:00 | — |
| congressional_district | NJ-02 | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| county | Cumberland County | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| county_fips | 34011 | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| county_market.building_permits_sf_annual | 143 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.building_permits_total_annual | 143 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.building_permits_yoy_pct | -43.4783 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.employment_total | 60285 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.employment_yoy_pct | 1.0002 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.hpi_yoy_pct | 9.61 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.median_household_income_usd | 64499 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.net_domestic_migration | 148 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.population | 157148 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_market.population_growth_1yr_pct | 0.4738 | US Census PEP/BPS/ACS, FHFA, BLS QCEW | 2026-08-05T09:56:53+00:00 | — |
| county_median_household_income | 64499 USD | CENSUS_ACS | 2026-08-05T09:30:52.349617+00:00 | 0.60 |
| county_population | 157148 people | CENSUS_PEP | 2026-08-05T09:30:52.349412+00:00 | 0.60 |
| county_population_growth_1yr_pct | 0.4738 percent | CENSUS_PEP | 2026-08-05T09:30:52.349507+00:00 | 0.60 |
| domestic_well_household_density_class | none | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992867+00:00 | 0.60 |
| domestic_well_households_per_km2 | 0.0 households/km2 | USGS_SELF_SUPPLIED_HOUSEHOLDS | 2026-08-05T09:30:50.992791+00:00 | 0.60 |
| elevation_m | 32.64278030395508 meters | USGS 3DEP/EPQS | 2026-08-05T09:56:53+00:00 | — |
| fema_flood_zone | X | FEMA NFHL | 2026-08-05T09:56:53+00:00 | — |
| housing_units_density_per_km2 | 653.818075328233 units/km2 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568353+00:00 | 0.60 |
| housing_units_within_1km | 3148 | CENSUS_TIGERWEB | 2026-08-05T09:30:52.568270+00:00 | 0.60 |
| in_opportunity_zone | True | US Treasury Qualified Opportunity Zones | 2026-08-05T09:56:53+00:00 | — |
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
| opportunity_zone_tract_geoid | 34011041100 | US Treasury Qualified Opportunity Zones | 2026-08-05T09:56:53+00:00 | — |
| parcel | 39.4862,-75.0257 | caller-supplied coordinate | 2026-08-05T09:56:53+00:00 | — |
| poi_count_1km | 476 | OVERTURE_PLACES | 2026-08-05T09:30:50.528304+00:00 | 0.60 |
| proximity.airport | 4.56 km | FAA_NASR | 2026-08-05T09:30:54.040210+00:00 | — |
| proximity.school | 0.34 km | OVERTURE_PLACES | 2026-08-05T09:30:50.528061+00:00 | — |
| proximity.urban_area | 0.0 km | CENSUS_TIGER_URBAN | 2026-08-05T09:30:54.608346+00:00 | — |
| sewer_service_area_provenance | utility_sourced | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932089+00:00 | 0.90 |
| sewer_service_area_provider | Landis Sewerage Authority - CS/STP | EPA_SEWERSHEDS | 2026-08-05T09:30:51.932078+00:00 | 0.90 |
| state | New Jersey | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| state_fips | 34 | US Census Geocoder | 2026-08-05T09:56:53+00:00 | — |
| timezone | America/New_York | IANA tz database | 2026-08-05T09:56:53+00:00 | — |
| tract_civilian_labor_force | 1300 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805330+00:00 | 0.60 |
| tract_geoid | 34011041101 | US Census Geocoder (2020 vintage) | 2026-08-05T09:56:53+00:00 | — |
| tract_population | 3259 people | CENSUS_TRACT_WORKFORCE | 2026-08-05T09:30:52.805388+00:00 | 0.60 |
| transmission_lines_within_radius_count | 1 | EIA_POWER | 2026-08-05T09:30:51.042584+00:00 | 0.90 |
| water_service_area_provenance | utility_sourced | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977658+00:00 | 0.90 |
| water_system_name | VINELAND WATER & SEWER UTILITY | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977646+00:00 | 0.90 |
| within_floodplain | False | FEMA NFHL | 2026-08-05T09:56:53+00:00 | — |
| within_sewer_service_area | True | EPA_SEWERSHEDS | 2026-08-05T09:30:51.931970+00:00 | 0.90 |
| within_water_service_area | True | EPA_CWS_SERVICE_AREAS | 2026-08-05T09:30:51.977539+00:00 | 0.90 |

*Generated 2026-08-05T09:58:54+00:00 · Claude Agent SDK tool-calling loop (claude-opus-5) · 12 tool calls · 90 credits.*

*Screen, not an applicability determination. The agent does not contact agencies, file anything, or send anything.*