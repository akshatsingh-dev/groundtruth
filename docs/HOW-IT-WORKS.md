# How it works

One example, all the way through. Every number below came out of the code in this
repo, run on 5 August 2026. You can point at any of them under questioning.

**The project:** a 500 MW combined-cycle natural gas plant powering a data center
campus at 21571 Beaumeade Circle, Ashburn, Virginia. Loudoun County. Dry low-NOx
combustors, selective catalytic reduction, oxidation catalyst. Best available
controls, nothing exotic.

**The answer:** major nonattainment New Source Review. 33.5 to 85.5 months, most
likely 54.5. About 1,660 days until legal power.

Two versions of this site show up in the docs and they aren't the same number. The
parcel run above includes Shenandoah at 63 km. The national sweep scores Loudoun from
county-level facts only, with no Class I distance, and gets 30.5 to 76.5 months,
likely 48.5. The six-month gap is the Class I trigger. Know which one you're quoting.

---

## Stage 1. Address to parcel, and the refusal

**In:** a string. "21571 Beaumeade Cir, Ashburn, VA 20147."
**Out:** latitude, longitude, county, state, FIPS, parcel ID, confidence.
**File:** `providers/base.py`, `geocode` on `PhysicalFactsProvider`.

The signature is `geocode(query, min_confidence=0.8)`. Below that it raises
`ResolutionError` instead of returning the best guess.

Defend the refusal out loud. A centroid that's actually the county seat, silently
substituted for a parcel, produces a permit answer for the wrong county. A refusal
costs a retry. A wrong parcel costs a land option. Every downstream answer is keyed on
county, so this is the one stage that could fail silently. It fails loudly instead.

`NullProvider` in the same file lets the engine and tests run with no API key and no
network. Every method raises or returns empty. Any code path that produces a plausible
answer against a provider with no data would fabricate against a real one.

---

## Stage 2. Megawatts to heat input

**In:** 500 MW, combined-cycle turbine.
**Out:** 3,400 MMBtu/hr of heat input.
**File:** `agent/emissions.py`, `GenerationConfig.heat_input_mmbtu_hr`.

Emissions don't scale with megawatts. They scale with fuel burned. The bridge is
**heat rate**, Btu of fuel per kWh of electricity. Lower is more efficient, less fuel,
fewer tons.

| Prime mover | Heat rate (Btu/kWh) |
|---|---|
| Simple-cycle turbine | 10,500 |
| Combined-cycle turbine | 6,800 |
| Lean-burn gas engine | 8,500 |
| Rich-burn gas engine | 9,200 |
| Diesel reciprocating | 7,500 |
| Fuel cell | 7,400 |

The code prints the arithmetic in its own output:

```
500 MW x 1000 kW/MW x 6,800 Btu/kWh / 1e6 = 3,400 MMBtu/hr
```

Swap combined-cycle for simple-cycle at the same 500 MW and heat input goes to 5,250
MMBtu/hr. Same electricity, 54% more fuel, 54% more of every pollutant. That's why a
design change can move a project across a permit line without touching its nameplate
rating.

---

## Stage 3. Heat input to pounds per hour

**In:** 3,400 MMBtu/hr plus a controls list.
**Out:** pounds per hour of each pollutant.
**File:** `agent/emissions.py`, the `_EF` table and `_apply_controls`.

Emission factors come from AP-42, EPA's published compilation. Every factor carries its
AP-42 table reference in the `citation` field, so the output shows its work the same
way Mireye's does.

Uncontrolled natural gas turbine, AP-42 Table 3.1-1:

| Pollutant | lb/MMBtu |
|---|---|
| NOx | 0.32 |
| CO | 0.082 |
| PM10 / PM2.5 | 0.0066 |
| SO2 | 0.0034 |
| VOC | 0.0021 |
| Formaldehyde | 0.00071 |
| CO2e | 110 |

Controls apply as fractional reductions, in sequence. Straight from the `basis` block
the code emits:

```
DLN:                NOx 0.3200 -> 0.0992 lb/MMBtu (69% reduction)
SCR:                NOx 0.0992 -> 0.0099 lb/MMBtu (90% reduction)
oxidation catalyst: CO  0.0820 -> 0.0082 lb/MMBtu (90% reduction)
oxidation catalyst: VOC 0.0021 -> 0.0010 lb/MMBtu (50% reduction)
oxidation catalyst: HCHO 0.0007 -> 0.0002 lb/MMBtu (70% reduction)
```

NOx at 0.0099 lb/MMBtu times 3,400 MMBtu/hr is **33.73 lb/hr**.

Tier 4 diesel engines work differently. EPA certifies them on engine output in grams
per kWh, not on fuel input, so the code replaces the AP-42 factors outright instead of
discounting them. Values from 40 CFR 1039.101 Table 7.

---

## Stage 4. Pounds per hour to tons per year, and the 8760 rule

**In:** 33.73 lb/hr of NOx.
**Out:** 147.7 tons per year.
**File:** `agent/emissions.py`, `estimate()` and `effective_run_hours`.

```
PTE (tpy) = EF (lb/MMBtu) x heat input (MMBtu/hr) x hours (hr/yr) / 2000
```

The hours number is 8,760. Every hour in a year.

**This is the most counter-intuitive thing in the product and it's where a judge will
probe.**

**Potential to emit** isn't what the plant will emit. It's the maximum it *could* emit
at design capacity, every hour. If the developer says "we only plan to run 4,000
hours," the agency computes at 8,760 anyway. Intent isn't a limit.

The only thing that lowers it is a **federally enforceable limit**: a permit condition
with recordkeeping and monitoring attached, legally capping operation. Accept one and
the agency computes PTE at your capped hours. A source that would be major without the
cap and is minor with it is a **synthetic minor**.

The code enforces this at the type level. `run_hours` is honoured only when
`enforceable_limit=True`. Otherwise `effective_run_hours` returns 8,760 regardless of
what you passed. You can't accidentally under-report.

Full PTE for our plant:

| Pollutant | tpy |
|---|---|
| NOx | 147.7 |
| CO | 122.1 |
| PM10 | 98.3 |
| PM2.5 | 98.3 |
| SO2 | 50.6 |
| VOC | 15.6 |
| Formaldehyde | 3.2 |
| CO2e | 1,638,120 |

---

## Stage 5. The List of 28

**In:** the config and its 3,400 MMBtu/hr.
**Out:** a major-source threshold of 100 tons per year rather than 250.
**File:** `agent/pathway.py`, `classify_source_category()`.

40 CFR 52.21(b)(1)(i)(a) names 28 categories of industrial source. In one of them,
you're a PSD major source at 100 tons per year of any one regulated pollutant.
Otherwise the line is 250.

Item one is "fossil fuel-fired steam electric plants of more than 250 million Btu per
hour heat input."

A combined-cycle plant runs the turbine's hot exhaust through a heat recovery steam
generator and drives a second turbine with the steam. That steam cycle makes it a
steam electric plant. At 3,400 MMBtu/hr it clears the 250 MMBtu/hr cutoff by a factor
of thirteen. **On the list. Threshold 100.**

A simple-cycle turbine has no steam cycle and no boiler. **Not on the list. Threshold
250.**

The engine says it in its own words: the data center isn't a listed category, the power
plant on its site is.

That 150 ton gap decides everything downstream. At 147.7 tpy our plant is 47 tons over
the 100 line and 102 tons under the 250 line. Same pollution, two regulatory worlds,
decided by whether there's a steam turbine on the pad.

On the simple-cycle branch the code hedges in the output, not just in the comments: a
few state agencies read the "fossil fuel boilers" entry more broadly than EPA does.

---

## Stage 6. Attainment, nonattainment, and offsets

**In:** Loudoun County. EPA Green Book says ozone, moderate, Washington DC-MD-VA.
**Out:** major nonattainment NSR, 170 tons of offsets.
**File:** `agent/pathway.py`, `_NA_THRESHOLDS`, `_NA_POLLUTANT_MAP`, `_OFFSET_RATIOS`.

EPA sets National Ambient Air Quality Standards for six criteria pollutants and
measures whether each area meets them. Meeting is **attainment**. Failing is
**nonattainment**, with a severity class.

In attainment the programme is PSD and the threshold is the 100 or 250 number from
Stage 5. In nonattainment the programme is nonattainment NSR and the threshold drops
with severity:

| Ozone classification | Major threshold (tpy) |
|---|---|
| marginal / moderate | 100 |
| serious | 50 |
| severe / severe-15 / severe-17 | 25 |
| extreme | 10 |

Ozone isn't emitted directly. It forms from NOx and VOC in sunlight, so both count
against an ozone designation. Our NOx at 147.7 tpy clears the 100 tpy moderate
threshold. Nonattainment NSR applies.

Two consequences.

**LAER instead of BACT.** BACT lets you argue cost. LAER doesn't. If any comparable
source anywhere in the country achieves a rate, you match it.

**Offsets.** You buy verified reductions from existing sources in the same area, at a
ratio set by the classification. Moderate is 1.15 to 1. The engine computes 147.7 x
1.15 = **170 tons**.

At 1.3 and above the code raises a hard stop rather than a delay, because credits in
severe and extreme areas are frequently unavailable at any price. Ellis County, Texas
is the example worth knowing, because it used to be the fast alternate in these docs
and it isn't. Ellis is in the Dallas-Fort Worth severe-15 ozone area. Threshold 25 tpy,
ratio 1.3, requirement 192 tons, hard stop attached, likely 30.5 months. Will County,
Illinois lands in the same place through Chicago.

---

## Stage 7. The Ozone Transport Region

**In:** Virginia, Loudoun County.
**Out:** a 50 tpy NOx threshold applied statewide-by-statute, and +3 months.
**File:** `agent/pathway.py`, `OTR_STATES`, `OTR_VA_COUNTIES`, `in_otr()`.

CAA 184(a) draws a box around the Northeast. Every state inside it applies moderate
nonattainment requirements for NOx and VOC across its whole territory, whatever the
local monitors say.

Twelve states plus DC: CT, DE, ME, MD, MA, NH, NJ, NY, PA, RI, VT, DC. Virginia is in
the region only for the Washington metro portion, so it's handled at county level:
Arlington, Fairfax, Loudoun, Prince William, Stafford, Alexandria, Falls Church,
Manassas, Manassas Park. Nine names, ten Census county-equivalents, because Fairfax is
both a county and an independent city.

The sweep fires this trigger in 256 counties.

Two things this fixes. The threshold is now actually enforced rather than announced.
Before, the trigger text claimed 50 tpy and the engine kept using the Green Book
classification, so a New Jersey parcel with no Green Book listing scored as PSD. And
the region is now attached to all twelve states rather than only the eight modelled in
detail, which stops the alternate-site search from selling a move that doesn't exist.
New Jersey to Pennsylvania is not an escape. Neither is New Jersey to Delaware.

---

## Stage 8. PSD increment

**In:** 85% of the PM2.5 Class II increment consumed, 60% of NO2, one major source
inside the screening radius.
**Out:** +6 months and +2 months, with a hard stop above 95%.
**File:** `agent/pathway.py`, the `psd_increment_consumed` block.

Increment is a finite shared budget for how much a pollutant concentration may rise
above a historical baseline. Everyone permitted before you consumed part of it.

It behaves like a fishing quota. When it's gone it's gone, and your plant being clean
doesn't get you any. You fit into what's left, which usually means controls tighter
than BACT would demand, a taller stack, or a different spot on the parcel.

At 50% consumed the trigger adds 2 months. At 80% it adds 6. At 95% it's a hard stop
and the engine says a major source there may be un-permittable at any timeline.

Those months now apply in nonattainment areas as well as PSD areas. The old behaviour
gated the cost on `MAJOR_PSD` only, so at Loudoun an 85%-consumed increment fired,
printed, and cost nothing. Backwards, and fixed.

---

## Stage 9. Class I areas

**In:** Shenandoah National Park at 63 km, from Mireye's `EPA_CLASS_I_AREAS` layer.
**Out:** +6 months.
**File:** `agent/pathway.py`, the `class_i_aqrv` block.

Class I areas are national parks and wilderness areas with the strictest protection
under the Clean Air Act. Not only health. It covers **air quality related values**:
visibility, and deposition into soil and water.

Inside 100 km, PSD requires notifying the Federal Land Manager and an AQRV analysis is
expected. Between 100 and 300 km, FLMs have asked for long-range visibility modelling
on large sources, scored at +2 months. Beyond 300 km the trigger records that it didn't
fire and says why.

This matters more than six months suggests. The FLM can object on visibility grounds
when the NAAQS modelling passes. A second veto, held by a different agency.

---

## Stage 10. The state overlay

**In:** Virginia.
**Out:** a 1.25x timeline multiplier and a state toxics trigger.
**File:** `agent/pathway.py`, `STATE_OVERLAYS`.

Eight states are modelled with real agency behaviour. Each carries a multiplier, a
note and a source.

| State | Multiplier | Permit by rule |
|---|---:|---|
| TX | 0.75 | yes |
| OH | 0.95 | yes |
| GA | 1.00 | no |
| AZ | 1.15 | no |
| IL | 1.20 | no |
| VA | 1.25 | no |
| NM | 1.35 | no |
| NJ | 1.60 | no |

Virginia's note: "DEQ has approved exactly one air permit for a data center campus
with on-site gas generation. Assume the first-of-its-kind treatment, not a routine
review." That permit is Vantage VA2.

New Jersey is the highest at 1.6x. The whole state is in the Ozone Transport Region
and NJ DEP has statutory authority under N.J.S.A. 13:1D-157 to deny a permit outright
in an overburdened community. Modelled as a discretionary denial risk, not a timeline
risk.

Every other state gets `FEDERAL_DEFAULT_OVERLAY`, 1.0x, with a note that appears in the
output: "This state is not one of the eight modelled in detail. Treat the range as
wider than shown." The gap announces itself.

---

## Stage 11. Everything that fired

Run the Ashburn parcel with increment, terrain and litigation populated and eleven
trigger rows come back. Each carries a citation and a months-added number:

| Trigger | Months | Why |
|---|---|---|
| nonattainment_designation | 0 | Ozone moderate, DC-MD-VA |
| major_nonattainment_nsr | +6 | 148 tpy vs 100 tpy, 170 tons of offsets |
| class_i_aqrv | +6 | Shenandoah at 63 km |
| psd_increment_consumed (PM2.5) | +6 | 85% consumed |
| psd_increment_consumed (NO2) | +2 | 60% consumed |
| title_v | 0 | 148 tpy over the 100 tpy Title V line |
| nsps_turbine | 0 | Subpart KKKK, plus the January 2026 rule |
| state_toxics | +2 | Virginia runs its own toxics programme |
| ozone_transport_region | +3 | Loudoun is one of the nine Northern Virginia jurisdictions |
| complex_terrain | +2 | 180 m of relief forces complex-terrain AERMOD |
| litigation | +3 | One federal case touching the county |

Total added: 30 months. Pathway: major nonattainment NSR, 40 to 105 months, likely
67.5.

**Read the NSPS trigger out loud in the demo, and read it carefully, because the
obvious version of this sentence is wrong.** EPA published a new NSPS for stationary
combustion turbines on 15 January 2026, at 91 Fed. Reg. 1910, creating subpart KKKKa.
It did not close the "nonroad engine" reading that let xAI energise turbines without a
Clean Air Act construction permit. It finalised a **conditional exclusion** in the
other direction: turbines come out of the "stationary combustion turbine" definition
where the unit qualifies as a nonroad engine and is certified under Title II. That
exclusion is not operative. It takes effect only if EPA adopts Title II standards for
portable turbines, a separate rulemaking that hasn't happened.

So the trailer-mounted fast path is unsettled, not closed. Meanwhile the NAACP is
asking a federal court in Mississippi to shut down 27 unpermitted turbines at xAI's
Colossus 2, with a preliminary injunction hearing set for late August 2026. Anyone
underwriting a trailer-mounted fast path today is underwriting an open legal question.

The trigger's own text says all of this, and its citation string names the rule, the
new subpart and the case.

---

## Stage 12. The timeline, and what it isn't

**File:** `agent/pathway.py`, `_BASE_MONTHS` and the Step 5 block.

Base ranges by pathway, in months, as (optimistic, likely, pessimistic):

| Pathway | Base |
|---|---|
| Permit by rule | 1 / 2 / 4 |
| Minor NSR | 4 / 6 / 10 |
| Synthetic minor | 5 / 8 / 14 |
| Major PSD | 14 / 24 / 36 |
| Major nonattainment NSR | 20 / 30 / 48 |

The arithmetic:

```
months_low    = low    x multiplier + added x 0.5
months_likely = likely x multiplier + added x 1.0
months_high   = high   x multiplier + added x 1.5
```

For the eleven-trigger run above: added = 30, multiplier = 1.25.

```
low    = 20 x 1.25 + 15 = 40.0
likely = 30 x 1.25 + 30 = 67.5
high   = 48 x 1.25 + 45 = 105.0
```

**Be straight about what this is.** An additive model with hand-set coefficients.
Triggers don't interact. Nothing caps the total. The base ranges come from published
agency guidance and observed permit histories, not from a regression on a permit
outcome dataset, because no such dataset exists publicly at parcel resolution.

The defensible claim is that it **orders sites correctly**. Loudoun is worse than
Mecklenburg, which is worse than Brewster, and every reason is individually citable.
The indefensible claim is that Loudoun is 54.5 rather than 45 or 70. Don't make it.

---

## The two search loops

Both hold one thing fixed and vary the other.

**Alternate-site search.** Same config, different parcels. County-level scores from
`sweep/counties.py`, so no Class I or terrain:

| Site | Pathway | Likely months | Days |
|---|---|---|---|
| Loudoun County, VA | Major NA NSR | 48.5 | 1,476 |
| Mecklenburg County, VA | Major PSD | 32.0 | 974 |
| Brewster County, TX | Major PSD | 20.0 | 609 |
| Ellis County, TX | Major NA NSR (hard stop) | 30.5 | 928 |
| Cumberland County, NJ | Major NA NSR | 63.0 | 1,918 |
| Doña Ana County, NM | Major NA NSR | 46.5 | 1,415 |

Staying in Virginia saves 16.5 months. West Texas saves 28.5.

The live demo ran the loop for real at Vineland, New Jersey. 16 candidates on 30, 60
and 120 km rings, 13 resolved, 3 dropped for landing on open water, 80 credits. Best
answer: New Castle County, Delaware, 37 miles west, 66 months to 42. It clears NJ's EJ
denial statute and NJ state toxics. It does not clear the Ozone Transport Region,
because Delaware is in it. Say that part.

**Config search.** Same parcel, different plant. At Ashburn:

| Config | Pathway | Likely months |
|---|---|---|
| 500 MW CC, full controls | Major NA NSR | 54.5 |
| 500 MW CC + 5,337 hr/yr enforceable cap | Synthetic minor | 15.0 |
| 500 MW fuel cell | Minor NSR | 12.5 |
| 300 MW CC, full controls | Minor NSR | 12.5 |
| 500 MW simple-cycle, full controls | Major NA NSR | 54.5 |

`synthetic_minor_cap()` computes the cap and prices it. 5,337 hours is 61%
availability, and the function's own text says the plant can't serve baseload alone at
that cap. That sentence is why a developer would trust the tool.

Note the last row. Switching to simple-cycle gets you off the List of 28 and moves your
threshold from 100 to 250, but it raises heat input from 3,400 to 5,250 MMBtu/hr and
NOx from 148 to 228 tpy. In a nonattainment area the 100 tpy line applies either way,
so the trade does nothing. The engine finds that. A rule of thumb wouldn't.

---

## How provenance survives to the output

`providers/base.py` defines `Fact` with `key`, `value`, `unit`, `source`, `fetched` and
`confidence`. `Fact.cited()` renders one line with the trail in brackets.
`FactSet.provenance()` returns the whole map. `SiteContext` carries a `provenance` dict,
`NonattainmentStatus` carries `source` and `fetched`, `MajorSourceNearby` carries
`source`, and every `Trigger` carries a `citation`.

Nothing enters the engine without a source and nothing leaves without one. The `Fact`
docstring adds a rule worth quoting: don't invent a confidence. An absent score is
information.

The demo report ends with a 103-row provenance table. Every physical fact, its source,
its fetch timestamp and its confidence.

The same discipline runs through the sweep. `data/county_scores.json` carries a
`sources` block, a `trigger_citations` map, and a `resolution_note` stating in plain
text what a county-level score can't see.

---

## The national sweep

`sweep/counties.py` runs the same engine at every county interior point with a fixed
reference config: the identical 500 MW combined-cycle plant used throughout this
document. 3,222 counties in 0.5 seconds on 12 workers, zero Mireye credits.

| | |
|---|---|
| Counties scored | 3,222 |
| Major PSD | 2,843 |
| Major nonattainment NSR | 379 |
| Minor, any flavour | 0 |
| Carrying a hard stop | 77 |
| Only partly in a nonattainment area | 91 |
| In the Ozone Transport Region | 256 |
| Fastest | Brewster County, TX, 609 days |
| Slowest | New Jersey, 1,918 days |

Two things to notice. No county in the country makes a 500 MW combined-cycle plant a
minor source, which is what Stage 5 predicted. And the 91-county partial-designation
count is the honest limit of a county-level map. Those are the counties where the
screen and the parcel can disagree.

`.venv/bin/python -m sweep.map` renders it. 3,219 counties drawn, 61 distinct answers.
Three scored counties have no boundary geometry to draw against, and the page prints
"3,219 counties drawn of 3,222 scored" rather than quietly rounding.

---

## Where the code and the older docs disagree

Trust the code. These are the gaps a judge could find.

**1. "Move 22 miles, minor NSR instead of PSD, save 18 months" is dead.** The brief's
headline and its §1 county table show a 500 MW plant landing in minor NSR at the good
site. The code never produces that. NOx at 147.7 tpy is over the 100 tpy List-of-28
threshold in every county in the country, so the best relocation gets you major PSD.
The real story is bigger anyway: 48.5 months to 20. Minor NSR shows up below 340 MW,
with a fuel cell, or under an enforceable hour cap. **Say "major nonattainment NSR to
major PSD" in the demo, not "PSD to minor NSR."**

**2. Twenty-two miles was always optimistic.** Escaping the Washington DC ozone
nonattainment area from Loudoun takes more than 22 miles, and it doesn't escape the OTR
at all. Let the search produce the distance.

**3. Ellis County, Texas is not the fast alternate.** It's in the Dallas-Fort Worth
severe-15 ozone area. Major nonattainment NSR, likely 30.5 months, with an offset hard
stop at 192 tons. The fastest county in the country is Brewster, Texas at 609 days,
tied with 233 other Texas counties. `README.md` still has the old Ellis line.

**4. Eight states, not six.** `STATE_OVERLAYS` has VA, TX, GA, OH, AZ, NJ, NM, IL.

**5. Splitting the plant doesn't work in the code.** Setting `units=4` leaves the
emissions total unchanged and adds a source-aggregation warning plus 3 months. The
brief's bullet is wrong and the code is right.

**6. The January 2026 EPA turbine rule was stated backwards everywhere.** It did not
close the nonroad loophole. See Stage 11. Any sentence saying the loophole is "closed"
is wrong. `agent/pathway.py` has the correct text in the trigger, but the comment above
the block at line 831 still says "the January 2026 turbine rule is the reason the
trailer-mounted fast path closed." A code comment, not user-visible, but it should go.

**7. Three fixed engine bugs that changed published numbers.** The OTR threshold is now
enforced instead of announced, which moved 256 counties. Consumed increment now costs
months in nonattainment areas, not just PSD areas. The permit-by-rule gate now checks
heat input as well as tons, so a 75 MW combined-cycle plant at 510 MMBtu/hr comes back
minor NSR rather than permit-by-rule. Permit-by-rule needs 100 MMBtu/hr or less, which
is about 10 MW of combined cycle.

**8. CO is high without an oxidation catalyst.** The uncontrolled AP-42 CO factor of
0.082 lb/MMBtu makes CO the controlling pollutant at 1,221 tpy on a DLN-plus-SCR plant,
above what modern combined-cycle permits show. Add the oxidation catalyst and it drops
to 122 tpy. The demo config includes it. Run without it on camera and you'll have to
explain the CO number.

**9. `README.md` is stale.** It says 47 tests (52 pass), two backtest cases (three),
Ellis County as major PSD at 20 months, "37 months of difference" for the Ashburn-Ellis
comparison, and minor pathways opening below roughly 150 MW (the crossover is 340 MW
with full controls in a clean county). Fix it before you submit. It's the first file a
judge opens.

**10. The sweep confirms point 1.** All 3,222 counties come back either major PSD or
major nonattainment NSR for the reference plant. Zero minor. The engine agreeing with
itself, and the cleanest available proof that the "22 miles to minor NSR" line has to
go.
