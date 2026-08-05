# Glossary

Every term a judge might say, in the words to say back. Each one ends with why it
matters here.

The running example is a 500 MW combined-cycle gas plant with dry low-NOx combustors,
SCR and an oxidation catalyst, at 21571 Beaumeade Circle in Ashburn, Loudoun County,
Virginia. NOx potential to emit 147.7 tpy. Every number below comes out of that run or
out of `sweep/counties.py`.

---

### PSD — Prevention of Significant Deterioration
The federal permit programme for a large new source built where the air already meets
federal standards. It exists to stop clean air from being degraded up to the legal
limit.
*Why it matters for us:* one of the five pathways the engine returns, and the two-year
answer. `Pathway.MAJOR_PSD`, base range 14 / 24 / 36 months. 2,843 of 3,222 US counties
land here for the reference plant.

### NSR — New Source Review
The umbrella name for the whole preconstruction air permitting programme. PSD in clean
areas, nonattainment NSR in dirty areas, minor NSR below the major thresholds.
*Why it matters for us:* NSR is the thing the engine computes. "Which NSR applies" is
our exact question.

### BACT — Best Available Control Technology
The control standard in a PSD permit. Case-by-case, set by the agency, and you can
argue that a tighter control isn't economically achievable.
*Why it matters for us:* the engine lists which pollutants need BACT by comparing PTE
against the significant emission rates in 40 CFR 52.21(b)(23)(i).

### LAER — Lowest Achievable Emission Rate
The control standard in a nonattainment NSR permit. Stricter than BACT because cost
isn't a defence. If any comparable source anywhere achieves a rate, you match it.
*Why it matters for us:* moving from an attainment county to a nonattainment county
swaps BACT for LAER. Real capex on top of the delay.

### PTE — Potential to Emit
The maximum tons per year a source could emit at design capacity, running 8,760 hours,
unless a federally enforceable permit condition caps it lower.
*Why it matters for us:* PTE is the number every threshold is compared against. Also
the most misunderstood concept in the product. Intent to run less doesn't reduce it.

### Synthetic minor
A source that would be major at full operation but stays under the threshold because
it accepted a legally binding limit in its permit. Usually a cap on annual run hours or
fuel throughput.
*Why it matters for us:* the main lever the config search pulls. At Ashburn a 5,337
hr/yr cap turns a 54.5-month permit into a 15-month one, at the price of 39% of the
year offline.

### Title V
The federal operating permit, as opposed to the construction permit. The engine fires
it at 100 tons per year of any criteria pollutant or 10 tons of a single hazardous air
pollutant.
*Why it matters for us:* it runs after construction permitting and rarely blocks the
build, but it adds a second public comment window and permanent annual compliance cost.
Fires as a trigger with zero months added. It fires in all 3,222 counties for the
reference plant.

### NSPS — New Source Performance Standards
Technology standards under Clean Air Act section 111 that apply to new equipment by
category, wherever it's built and whatever the site's size.
*Why it matters for us:* Subpart KKKK covers stationary combustion turbines. EPA
published a new turbine NSPS on 15 January 2026 at 91 Fed. Reg. 1910, creating subpart
KKKKa.

**Say this one carefully. It's the fact most likely to be quoted back at you
backwards.** The rule did *not* close the trailer-mounted "nonroad engine" reading xAI
used. It finalised a **conditional exclusion** in the opposite direction: turbines come
out of the "stationary combustion turbine" definition where the unit qualifies as a
nonroad engine and is certified under Title II. That exclusion isn't operative. It
takes effect only if EPA adopts Title II standards for portable turbines, which is a
separate rulemaking that hasn't happened. The rule also moved low-use turbines out of
Title V major-source permitting. So the fast path is unsettled, not closed, and the
NAACP is asking a federal court in Mississippi to shut down 27 unpermitted turbines at
xAI's Colossus 2 with a preliminary injunction hearing set for late August 2026.

### NESHAP — National Emission Standards for Hazardous Air Pollutants
Standards under Clean Air Act section 112 for the federally listed hazardous air
pollutants. Subpart ZZZZ covers reciprocating engines.
*Why it matters for us:* it sets a control floor for engine configurations, and it's
why formaldehyde is tracked separately in the emissions module.

### Attainment / nonattainment
EPA's designation for whether an area meets a National Ambient Air Quality Standard for
a given pollutant. Nonattainment comes with a severity class: marginal, moderate,
serious, severe, extreme.
*Why it matters for us:* this single field flips the pathway. It's why two identical
plants 40 miles apart get different answers, and it's the one fact the EPA Green Book
supplies.

### Criteria pollutant
The six pollutants EPA sets national ambient standards for: ozone, particulate matter,
carbon monoxide, sulfur dioxide, nitrogen dioxide, lead.
*Why it matters for us:* the major-source test runs against these. The engine tracks
NOx, CO, PM10, PM2.5, SO2 and VOC, and excludes CO2e and formaldehyde from the criteria
comparison.

### HAP — Hazardous Air Pollutant
A specifically listed toxic compound. Different programme from the criteria pollutants,
different thresholds. The one the engine uses is 10 tons per year of a single HAP,
which triggers Title V.
*Why it matters for us:* formaldehyde from gas combustion is the one that bites. Our
500 MW turbine plant is at 3.2 tpy with an oxidation catalyst. Swap to 500 MW of
lean-burn gas engines and formaldehyde alone hits 983 tpy. Completely different
regulatory conversation.

### Offsets
Verified emission reductions bought from existing sources in the same nonattainment
area, at a ratio above 1:1, to compensate for what you'll add.
*Why it matters for us:* in a moderate ozone area the ratio is 1.15, so our plant needs
170 tons. At 1.3 and above the engine calls a hard stop rather than a delay, because in
severe and extreme areas the credits often don't exist at any price. That's what
happens in Ellis County, Texas: severe-15, 25 tpy threshold, 192 tons required, hard
stop.

### Increment (PSD increment)
A fixed cap on how much a pollutant concentration may rise in an area above a
historical baseline. A shared budget, consumed in order by whoever permits first.
*Why it matters for us:* a clean county can still be closed to you. The engine adds 2
months at 50% consumed, 6 months at 80%, and calls a hard stop at 95%. Those months now
apply in nonattainment areas too. They used to be gated on PSD only, which meant a
Loudoun site could show 85% consumed increment and pay nothing for it.

### Class I area
A national park or wilderness area with the strictest air protection under the Clean
Air Act, covering visibility and deposition as well as health.
*Why it matters for us:* Shenandoah at 63 km triggers Federal Land Manager notification
and an AQRV analysis, worth +6 months. The FLM can object on visibility grounds when
every health number passes.

### AQRV — Air Quality Related Values
What a Class I area is protected for beyond human health. Visibility, and deposition of
nitrogen and sulfur into soil and water.
*Why it matters for us:* a second veto, held by a different federal agency, running on
a different clock from the state permit.

### AERMOD
EPA's regulatory air dispersion model. It takes stack parameters, terrain and
meteorology and predicts ground-level concentrations, compared against the ambient
standards and the increment.
*Why it matters for us:* the engine doesn't run AERMOD. It predicts whether you'll have
to, and whether it'll be the cheap flat-terrain version or the expensive
complex-terrain one. 180 m of relief triggers the expensive one, +2 months.

### AP-42
EPA's published *Compilation of Air Pollutant Emission Factors*. Pounds of each
pollutant per unit of fuel burned, by equipment type.
*Why it matters for us:* every emission factor in `agent/emissions.py` comes from AP-42
and carries its table number in the code. Table 3.1 for turbines, 3.2 for gas engines,
3.4 for diesel.

### Heat rate
Btu of fuel consumed per kWh of electricity produced. Lower is more efficient.
Combined-cycle turbine 6,800 Btu/kWh, simple-cycle 10,500.
*Why it matters for us:* the bridge between megawatts and pollution. Emissions scale
with fuel burned, not with nameplate rating.

### Simple cycle vs combined cycle
A simple-cycle turbine burns gas, spins, and exhausts the hot gas. A combined-cycle
plant captures that exhaust in a heat recovery steam generator and drives a second
turbine with the steam.
*Why it matters for us:* two consequences pull opposite ways. Combined cycle burns 35%
less fuel per MWh. But the steam cycle puts it on the List of 28, which drops the
major-source threshold from 250 tpy to 100. At 500 MW in a nonattainment county the
trade is a wash, and the engine says so.

### SCR — Selective Catalytic Reduction
Ammonia injected into the exhaust over a catalyst, converting NOx to nitrogen and
water. Around 90% reduction.
*Why it matters for us:* it takes our plant from 0.0992 to 0.0099 lb/MMBtu of NOx.
Usually the single most expensive item in a BACT determination. At Vineland it cuts NOx
from 5,887 tpy to 589 and doesn't change the pathway, because the serious-ozone
threshold is 50.

### Oxidation catalyst
A catalyst in the exhaust that oxidises carbon monoxide and unburned hydrocarbons.
About 90% on CO, 50% on VOC, 70% on formaldehyde.
*Why it matters for us:* without it, CO is the controlling pollutant at 1,221 tpy and
the answer looks worse than reality. With it, CO drops to 122 tpy and NOx takes over.
The demo config includes it.

### DLN — Dry Low-NOx combustors
A combustor design that mixes fuel and air more evenly so the flame burns cooler and
makes less NOx. No water, no ammonia, no add-on equipment. Around 69% reduction.
*Why it matters for us:* the cheapest NOx control on a turbine, and it applies before
SCR. The code refuses to let you specify it on a reciprocating engine.

### Tier 4 (Tier 4 final)
EPA's strictest emission certification for new non-road and stationary
compression-ignition engines. Certified on engine output in grams per kWh, not on fuel
input.
*Why it matters for us:* the code handles Tier 4 as an override rather than a
percentage reduction, because the certification is output-based. Values from 40 CFR
1039.101 Table 7.

### Behind-the-meter
Generation built on the customer's side of the utility meter, serving the load directly
instead of going through the grid.
*Why it matters for us:* this is the whole product. Developers go behind-the-meter to
escape the interconnection queue and discover the air permit is the new queue. Of about
90 GW announced across 59 projects, 2.2% is operating.

### Interconnection queue
The line you join to get a grid connection. The utility studies your impact on the
system, in order, and the study alone can take a year.
*Why it matters for us:* it's the reason on-site generation exists as a strategy. Musk
to Dwarkesh, 5 February 2026, verbatim: "They have to do a study for a year. A year
later, they'll come back to you with their interconnect study."

### The List of 28
The 28 named source categories in 40 CFR 52.21(b)(1)(i)(a) that become PSD major
sources at 100 tons per year instead of 250.
*Why it matters for us:* item one is "fossil fuel-fired steam electric plants of more
than 250 million Btu/hr heat input." A combined-cycle plant is on it. A simple-cycle
plant isn't. A data center isn't. One design decision moves the threshold by 150 tons.

---

## Terms that come up in follow-up questions

### NAAQS
National Ambient Air Quality Standards. The concentration limits in the air itself that
attainment and nonattainment are measured against.

### EPA Green Book
EPA's published dataset of nonattainment designations and classifications. One
download, no API. The source for every attainment field in the engine, exported
2026-07-31 and parsed to `data/greenbook.json`.

### NEI
EPA's National Emissions Inventory. Where the permitted emissions of existing major
sources come from, which is how increment consumption gets estimated.

### ERC — Emission Reduction Credit
A tradable, verified ton of reduction, registered with a state. What you actually buy
when you buy an offset.

### FLM — Federal Land Manager
The agency running a Class I area, usually the National Park Service or the Forest
Service. It gets notified and can object on AQRV grounds. For Shenandoah it's NPS.

### Permit by rule / general permit
A pre-written permit for a common, small source. You register against it instead of
applying. Fastest pathway in the engine, 1 / 2 / 4 months, available in Texas and Ohio
in our state table.
*Why it matters for us:* the gate is 25 tpy **and** 100 MMBtu/hr of heat input. The
heat-input half is the one that keeps it honest. Real state PBRs carry equipment and
heat-input limits, and a tons-only gate handed a 75 MW combined-cycle plant at 510
MMBtu/hr a permit-by-rule answer it can't have. That plant now comes back minor NSR.
100 MMBtu/hr is roughly 10 MW of combined cycle.

### Source aggregation
EPA's rule that units which are contiguous or adjacent, under common control, and in
the same major industrial grouping count as one source. It stops you splitting a plant
to duck a threshold.
*Why it matters for us:* the code models it. Setting `units=4` doesn't reduce emissions
and adds a warning plus three months.

### OTR — Ozone Transport Region
A statutory region under CAA 184(a) where nonattainment-style NOx and VOC rules apply
across each state's whole territory, whatever the local monitors read. Major source
threshold 50 tpy.
*Why it matters for us:* twelve states plus DC (CT, DE, ME, MD, MA, NH, NJ, NY, PA, RI,
VT, DC) and nine Northern Virginia jurisdictions (Arlington, Fairfax, Loudoun, Prince
William, Stafford, Alexandria, Falls Church, Manassas, Manassas Park). 256 counties in
the sweep. The engine now applies the 50 tpy threshold instead of just printing it,
which is what moved New Jersey and Northern Virginia in the national numbers.

It also kills the obvious escape. New Jersey to Pennsylvania is inside the region. New
Jersey to Delaware is inside the region. The demo's alternate site clears New Jersey's
EJ statute and state toxics, not the OTR.

### EJ denial authority
New Jersey's environmental justice statute, N.J.S.A. 13:1D-157, effective April 2023.
It lets NJDEP deny a permit outright in an overburdened community, independent of
whether the modelling passes.
*Why it matters for us:* modelled as a discretionary denial risk, +4 months, and it's
the single fact that makes New Jersey the slowest state in the sweep. It fires in 21
counties.

### MMBtu/hr, tpy, lb/MMBtu
Million Btu per hour, the unit of heat input. Tons per year, the unit every threshold is
written in. Pounds per million Btu, the unit of an emission factor. The whole
calculation is lb/MMBtu x MMBtu/hr x hr/yr / 2000 = tpy.
