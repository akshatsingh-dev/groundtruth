# How it works

One example, all the way through. Every number below came out of the code in this
repo. You can point at any of them under questioning.

**The project:** a 500 MW combined-cycle natural gas plant to power a data center
campus in Loudoun County, Virginia. Dry low-NOx combustors, selective catalytic
reduction, and an oxidation catalyst. Best available controls, nothing exotic.

**The answer the engine gives:** major nonattainment New Source Review. 34 to 88
months, most likely 57. Roughly 1,718 days until legal power.

---

## Stage 1. Address to parcel, and the refusal

**In:** a string. "42000 Beaumeade Circle, Ashburn, VA."
**Out:** latitude, longitude, county, state, FIPS code, parcel ID, and a
confidence score.
**File:** `providers/base.py`, the `geocode` method on `PhysicalFactsProvider`.

The signature is `geocode(query, min_confidence=0.8)`. Below that threshold it
raises `ResolutionError` rather than returning the best guess.

Defend that refusal out loud. The code's own comment: a centroid that is actually
the county seat, silently substituted for a parcel, produces a permit answer for
the wrong county. A refusal costs a retry. A wrong parcel costs a land option.
This is the one stage where the product could fail silently, because every
downstream answer is keyed on county. So it fails loudly instead.

`NullProvider` in the same file lets the engine and tests run with no API key and
no network. Every method raises or returns empty. The reasoning: any code path
that produces a plausible answer against a provider with no data would fabricate
against a real one.

---

## Stage 2. Megawatts to heat input

**In:** 500 MW, combined-cycle turbine.
**Out:** 3,400 MMBtu/hr of heat input.
**File:** `agent/emissions.py`, `GenerationConfig.heat_input_mmbtu_hr`.

Emissions do not scale with megawatts. They scale with **fuel burned**. The bridge
is **heat rate**, in Btu of fuel per kWh of electricity. Lower heat rate means a
more efficient plant, less fuel for the same output, fewer tons of pollution.

The module's defaults:

| Prime mover | Heat rate (Btu/kWh) |
|---|---|
| Simple-cycle turbine | 10,500 |
| Combined-cycle turbine | 6,800 |
| Lean-burn gas engine | 8,500 |
| Rich-burn gas engine | 9,200 |
| Diesel reciprocating | 7,500 |
| Fuel cell | 7,400 |

The arithmetic, which the code prints in its own output:

```
500 MW x 1000 kW/MW x 6,800 Btu/kWh / 1e6 = 3,400 MMBtu/hr
```

Swap the combined-cycle turbines for simple-cycle at the same 500 MW and heat
input goes to 5,250 MMBtu/hr. Same electricity, 54% more fuel, 54% more of every
pollutant. That is the whole reason a design change can move a project across a
permit line without changing its nameplate rating.

---

## Stage 3. Heat input to pounds per hour

**In:** 3,400 MMBtu/hr plus a controls list.
**Out:** pounds per hour of each pollutant.
**File:** `agent/emissions.py`, the `_EF` table and `_apply_controls`.

Emission factors come from AP-42, EPA's published compilation of air pollutant
emission factors. Every factor carries its AP-42 table reference in the `citation`
field, so the output shows its work the same way Mireye's does.

Uncontrolled natural gas turbine, from AP-42 Table 3.1-1:

| Pollutant | lb/MMBtu |
|---|---|
| NOx | 0.32 |
| CO | 0.082 |
| PM10 / PM2.5 | 0.0066 |
| SO2 | 0.0034 |
| VOC | 0.0021 |
| Formaldehyde | 0.00071 |
| CO2e | 110 |

Controls are applied as fractional reductions, in sequence:

```
DLN:  NOx 0.3200 -> 0.0992 lb/MMBtu (69% reduction)
SCR:  NOx 0.0992 -> 0.0099 lb/MMBtu (90% reduction)
```

NOx at 0.0099 lb/MMBtu times 3,400 MMBtu/hr is **33.73 lb/hr**.

Tier 4 diesel engines are handled differently. EPA certifies them on engine
**output** in grams per kWh, not on fuel input, so the code replaces the AP-42
factors outright instead of discounting them. The values come from 40 CFR 1039.101
Table 7.

---

## Stage 4. Pounds per hour to tons per year, and the 8760 rule

**In:** 33.73 lb/hr of NOx.
**Out:** 147.7 tons per year of NOx.
**File:** `agent/emissions.py`, `estimate()` and `effective_run_hours`.

```
PTE (tpy) = EF (lb/MMBtu) x heat input (MMBtu/hr) x hours (hr/yr) / 2000
```

The hours number is 8,760. That is every hour in a year.

**This is the single most counter-intuitive thing in the product, and it is where
a judge will probe.**

**Potential to emit** is not what the plant will emit. It is the maximum it
*could* emit at design capacity, every hour of the year. If the developer says "we
only plan to run 4,000 hours," the agency ignores that and computes at 8,760.
Intent is not a limit. Running the plant less does not lower your number.

The only thing that lowers it is a **federally enforceable limit**: a condition
written into the permit, with recordkeeping and monitoring attached, that legally
caps operation. Accept one and the agency computes PTE at your capped hours. A
source that would be major without the cap and is minor with it is a **synthetic
minor**.

The code enforces this at the type level. `run_hours` is only honoured when
`enforceable_limit=True`. Otherwise `effective_run_hours` returns 8,760 regardless
of what you passed. You cannot accidentally under-report, which is exactly the
mistake this rule exists to prevent.

The full PTE for our plant:

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

**In:** the config and its 3,400 MMBtu/hr of heat input.
**Out:** a major-source threshold of 100 tons per year rather than 250.
**File:** `agent/pathway.py`, `classify_source_category()`.

40 CFR 52.21(b)(1)(i)(a) names 28 categories of industrial source. If your plant
is in one, you are a PSD major source at 100 tons per year of any one regulated
pollutant. If not, the line is 250.

Item one on that list is "fossil fuel-fired steam electric plants of more than 250
million Btu per hour heat input."

A combined-cycle plant runs the gas turbine's hot exhaust through a heat recovery
steam generator and drives a second turbine with the steam. That steam cycle makes
it a steam electric plant. At 3,400 MMBtu/hr it clears the 250 MMBtu/hr cutoff by
a factor of thirteen. **On the list. Threshold 100.**

A simple-cycle turbine has no steam cycle and no boiler. **Not on the list.
Threshold 250.**

The engine says it in its own words: the data center itself is not a listed
category, the power plant on its site is.

That 150 ton gap decides everything downstream. At 147.7 tpy of NOx our plant is
47 tons over the 100 line and 102 tons under the 250 line. Same pollution, two
regulatory worlds, decided by whether there is a steam turbine on site.

The code hedges honestly on the simple-cycle branch, noting that a few state
agencies read the "fossil fuel boilers" entry more broadly than EPA does. That
hedge is in the output, not just the comments.

---

## Stage 6. Attainment, nonattainment, and offsets

**In:** Loudoun County, Virginia. EPA Green Book says ozone, moderate, Washington
DC-MD-VA area.
**Out:** major nonattainment NSR, 170 tons of offsets required.
**File:** `agent/pathway.py`, `_NA_THRESHOLDS`, `_NA_POLLUTANT_MAP`,
`_OFFSET_RATIOS`.

EPA sets National Ambient Air Quality Standards for six criteria pollutants and
measures whether each area meets them. Meeting is **attainment**. Failing is
**nonattainment**, with a severity classification: marginal, moderate, serious,
severe, extreme.

In attainment the programme is PSD, and the threshold is the 100 or 250 number
from Stage 5. In nonattainment the programme is nonattainment NSR, and the
threshold drops with severity:

| Ozone classification | Major threshold (tpy) |
|---|---|
| marginal / moderate | 100 |
| serious | 50 |
| severe | 25 |
| extreme | 10 |

Ozone is not emitted directly. It forms in the atmosphere from NOx and VOC in
sunlight, so both count against an ozone designation. Our NOx at 147.7 tpy clears
the 100 tpy moderate threshold. Nonattainment NSR applies.

Two consequences.

**LAER instead of BACT.** BACT, best available control technology, lets you argue
cost. LAER, lowest achievable emission rate, does not. If any similar source
anywhere in the country achieves a rate, you match it.

**Offsets.** You buy verified emission reductions from existing sources in the
same area, at a ratio set by the classification. Moderate is 1.15 to 1. The engine
computes 147.7 x 1.15 = **170 tons**.

At ratios of 1.3 and above the code raises a hard stop rather than a delay,
because offset credits in severe and extreme areas are frequently unavailable at
any price. Move the plant to Will County, Illinois, severe-15 ozone in the Chicago
area, and the threshold falls to 25 tpy, the ratio rises to 1.3, and the
requirement becomes 192 tons with a hard stop attached.

---

## Stage 7. PSD increment

**In:** 85% of the PM2.5 Class II increment already consumed, one major source
within the screening radius.
**Out:** a fired trigger, with a hard stop above 95%.
**File:** `agent/pathway.py`, the `psd_increment_consumed` block.

Increment is a finite, shared budget for how much a pollutant concentration may
rise in an area above a historical baseline. Every source permitted before you
consumed part of it.

It behaves like a fishing quota. When it is gone it is gone, and your plant being
clean does not get you any. You fit into what is left, which usually means
controls tighter than BACT would demand, a taller stack, or a different spot on
the parcel. Or you wait for someone else to shut down.

At 80% consumed the engine fires the trigger. At 95% it declares a hard stop and
says a major source there may be un-permittable at any timeline.

---

## Stage 8. Class I areas

**In:** Shenandoah National Park at 60 km.
**Out:** +6 months.
**File:** `agent/pathway.py`, the `class_i_aqrv` block.

Class I areas are national parks and wilderness areas given the strictest
protection under the Clean Air Act. The protection is not only about health. It
covers **air quality related values**: visibility, and deposition into soil and
water.

Inside 100 km, PSD requires notifying the Federal Land Manager and an AQRV
analysis is expected. Between 100 and 300 km, FLMs have asked for long-range
visibility modelling on large sources, scored at +2 months. Beyond 300 km the
trigger records that it did not fire and says why.

This matters more than the months suggest: the FLM can object on visibility
grounds even when the NAAQS modelling passes. A second veto, held by a different
agency.

---

## Stage 9. The state overlay

**In:** Virginia.
**Out:** a 1.25x timeline multiplier, plus a state toxics trigger.
**File:** `agent/pathway.py`, `STATE_OVERLAYS`.

Eight states are modelled with real agency behaviour: VA, TX, GA, OH, AZ, NJ, NM,
IL. Each carries a multiplier, a note, and a source.

Virginia is 1.25x. The note: "DEQ has approved exactly one air permit for a data
center campus with on-site gas generation. Assume the first-of-its-kind treatment,
not a routine review."

Texas is 0.75x, because TCEQ standard permits and permits-by-rule are genuinely
fast. New Jersey is 1.6x, the highest, because the state sits in the Ozone
Transport Region and NJ DEP has statutory authority under N.J.S.A. 13:1D-157 to
deny a permit outright in an overburdened community. That is the Nebius failure
mode, modelled as a discretionary denial risk rather than a timeline risk.

Every other state gets `FEDERAL_DEFAULT_OVERLAY`, a 1.0x multiplier with a note
that appears in the output: "This state is not one of the eight modelled in
detail. Treat the range as wider than shown." The gap announces itself.

---

## Stage 10. Everything else that fired

For this run, ten triggers fired. Each one carries a citation and a months-added
number:

| Trigger | Months | Why |
|---|---|---|
| nonattainment_designation | 0 | Ozone moderate, DC-MD-VA |
| major_nonattainment_nsr | +6 | 148 tpy vs 100 tpy, 170 tons of offsets |
| class_i_aqrv | +6 | Shenandoah at 60 km |
| psd_increment_consumed (PM2.5) | 0 | 85% consumed |
| psd_increment_consumed (NO2) | 0 | 60% consumed |
| title_v | 0 | 148 tpy over the 100 tpy Title V line |
| nsps_turbine | 0 | Subpart KKKK, and the Jan 2026 rule |
| state_toxics | +2 | Virginia runs its own toxics programme |
| complex_terrain | +2 | 180 m of relief forces complex-terrain AERMOD |
| litigation | +3 | One federal case touching the county |

Read the NSPS trigger out loud in the demo. It records that as of the EPA rule
published 15 January 2026 at 91 Fed. Reg. 1910, a turbine providing primary power
at a fixed site needs Clean Air Act permits whether or not it is trailer-mounted.
That closes the "nonroad engine" reading that let xAI energise around 100,000 GPUs
in about 19 days. The engine's own words: "Assume no fast path."

---

## Stage 11. The timeline, and what it is not

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

For our run: added = 19, multiplier = 1.25.

```
low    = 20 x 1.25 + 9.5  = 34.5
likely = 30 x 1.25 + 19   = 56.5
high   = 48 x 1.25 + 28.5 = 88.5
```

**Be straight about what this is.** An additive model with hand-set coefficients.
Triggers do not interact. Nothing caps the total. The base ranges come from
published agency guidance and observed permit histories, not from a regression on
a permit outcome dataset, because no such dataset exists publicly at parcel
resolution.

The defensible claim is that it **orders sites correctly**. Loudoun is worse than
Mecklenburg, which is worse than Ellis, and every reason is individually citable.
The indefensible claim is that Loudoun is 56.5 rather than 48 or 70. Do not make
it.

---

## The two search loops

Both hold one thing fixed and vary the other.

**Alternate-site search.** Same config, different parcels.

| Site | Pathway | Likely months | Days |
|---|---|---|---|
| Loudoun County, VA | Major NA NSR | 56.5 | 1,718 |
| Mecklenburg County, VA | Major PSD | 34.0 | 1,034 |
| Ellis County, TX | Major PSD | 20.0 | 608 |
| Salem County, NJ | Major NA NSR (hard stop) | 63.0 | 1,915 |
| Doña Ana County, NM | Major PSD (hard stop) | 48.4 | 1,471 |

Staying in Virginia saves 22.5 months. Texas saves 36.5.

**Config search.** Same parcel, different plant. At Loudoun:

| Config | Pathway | Likely months |
|---|---|---|
| 500 MW CC, full controls | Major NA NSR | 56.5 |
| 500 MW CC + 5,337 hr/yr enforceable cap | Synthetic minor | 17.0 |
| 300 MW CC, full controls | Minor NSR | 14.5 |
| 500 MW fuel cell | Minor NSR | 14.5 |
| 500 MW simple-cycle, full controls | Major NA NSR | 56.5 |

`synthetic_minor_cap()` computes the cap and prices it: 5,337 hours is 61%
availability, and the function's own text says the plant cannot serve baseload
alone at that cap. That sentence is why a developer would trust the tool.

Note the last row. Switching to simple-cycle gets you off the List of 28 and moves
your threshold from 100 to 250, but it raises heat input from 3,400 to 5,250
MMBtu/hr and NOx from 148 to 228 tpy. In a nonattainment area the 100 tpy line
applies either way, so the trade does nothing. The engine finds that. A rule of
thumb would not.

---

## How provenance survives to the output

`providers/base.py` defines `Fact` with `key`, `value`, `unit`, `source`,
`fetched` and `confidence`. `Fact.cited()` renders one line with the trail in
brackets. `FactSet.provenance()` returns the whole map. `SiteContext` carries a
`provenance` dict, `NonattainmentStatus` carries `source` and `fetched`,
`MajorSourceNearby` carries `source`, and every `Trigger` carries a `citation`.

Nothing enters the engine without a source and nothing leaves without one. The
`Fact` docstring adds a rule worth quoting: do not invent a confidence. An absent
score is information.

The same discipline runs through the sweep output. `data/county_scores.json`
carries a `sources` block, a `trigger_citations` map, and a `resolution_note` that
states in plain text what a county-level score cannot see.

---

## The national sweep

`sweep/counties.py` runs the same engine at every county interior point with a
fixed reference config: the identical 500 MW combined-cycle plant used throughout
this document.

| | |
|---|---|
| Counties scored | 3,222 |
| Major PSD | 3,028 |
| Major nonattainment NSR | 194 |
| Carrying a hard stop | 67 |
| Only partly in a nonattainment area | 90 |
| Fastest | Texas, 609 days |
| Slowest | New Jersey, 1,918 days |

Two things to notice. First, no county in the country makes a 500 MW
combined-cycle plant a minor source, which is the same result Stage 5 predicted.
Second, that 90-county partial-designation count is the honest limit of a
county-level map. Those are the counties where the screen and the parcel can
disagree.

---

## Where the code and the brief disagree

Trust the code. These are the gaps a judge could find.

**1. "Move 22 miles, minor NSR instead of PSD, save 18 months" is not reachable at
500 MW.** The brief's headline and its §1 county table show a 500 MW plant landing
in minor NSR at the good site. The code never produces that. NOx at 147.7 tpy is
over the 100 tpy List-of-28 threshold everywhere in the country, so the best
relocation gets you is major PSD. The real story is bigger anyway: 57 months to
20, a 36.5 month saving, not 18. Minor NSR appears at 300 MW and below, with a
fuel cell, or under an enforceable hour cap. **Say "major nonattainment NSR to
major PSD" in the demo, not "PSD to minor NSR."**

**2. Twenty-two miles is optimistic.** Escaping the Washington DC ozone
nonattainment area from Loudoun takes more than 22 miles. That number only works
for a parcel on a designation boundary. Say "the alternate site the search finds"
and let the distance be whatever the run produces.

**3. Eight states, not six.** The brief's README template says six. `STATE_OVERLAYS`
has eight: VA, TX, GA, OH, AZ, NJ, NM, IL.

**4. Splitting the plant does not work in the code.** The brief lists it as a
config option. Setting `units=4` leaves the emissions total unchanged and adds a
source-aggregation warning plus 3 months. The brief's bullet is wrong and the code
is right.

**5. The New Jersey Ozone Transport Region trigger says 50 tpy but does not apply
it.** The trigger text claims the OTR major threshold for NOx and VOC is 50 tpy.
The engine still uses the Green Book classification, which is 100 tpy for a
moderate area. A New Jersey site with no Green Book listing scores as PSD, not
nonattainment NSR. Known bug. Call it what it is.

**6. PSD increment adds zero months in nonattainment areas.**
`psd_increment_consumed` only adds months when the pathway is `MAJOR_PSD`. At
Loudoun the pathway is `MAJOR_NA_NSR`, so 85% consumed PM2.5 increment fires,
prints, and costs nothing. Arguably backwards. Flag it first.

**7. Permit-by-rule is gated on tons only.** The gate is `largest_tpy < 25`. A
75 MW combined-cycle plant with full controls comes out at 22.2 tpy NOx and
510 MMBtu/hr and scores permit-by-rule in Texas. Real TCEQ permits by rule have
heat-input and equipment limits the code does not check. Most likely place for the
engine to be too optimistic.

**8. CO is high without an oxidation catalyst.** The uncontrolled AP-42 CO factor
of 0.082 lb/MMBtu makes CO the controlling pollutant at 1,221 tpy on a
DLN-plus-SCR plant, well above what modern combined-cycle permits show. Add the
oxidation catalyst and it drops to 122 tpy, which is defensible. The demo config
includes it for that reason. Run without it on camera and you will have to explain
the CO number.

**9. The README repeats both errors.** As of the last check, `README.md` still
says the backtest is 2 cases (it is 3) and that "the same plant 22 miles away is
minor NSR, about 5 months" (it is not, at 500 MW). Fix the README before you
submit. It is the first file a judge opens and it currently contradicts the code
it sits on top of.

**10. The national sweep confirms point 1.** All 3,222 counties come back either
major PSD or major nonattainment NSR for the reference 500 MW plant. Zero minor.
That is the engine agreeing with itself, and it is the cleanest available proof
that the "22 miles to minor NSR" line has to go.
