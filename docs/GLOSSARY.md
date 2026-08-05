# Glossary

Every term a judge might say, in the words to say back. Each one ends with why it
matters here.

---

### PSD — Prevention of Significant Deterioration
The federal permit programme that applies when you build a large new source of air
pollution in an area whose air already meets federal standards. It exists to stop
clean air from being degraded up to the legal limit.
*Why it matters for us:* it is one of the five pathways the engine can return, and
it is the two-year answer. `Pathway.MAJOR_PSD`, base range 14 / 24 / 36 months.

### NSR — New Source Review
The umbrella name for the whole preconstruction air permitting programme. It splits
into PSD in clean areas, nonattainment NSR in dirty areas, and minor NSR for
everything below the major thresholds.
*Why it matters for us:* NSR *is* the thing the engine computes. When someone says
"which NSR applies," they are asking our exact question.

### BACT — Best Available Control Technology
The control standard in a PSD permit. Case-by-case, set by the agency, and you are
allowed to argue that a tighter control is not economically achievable.
*Why it matters for us:* the engine lists which pollutants need BACT by comparing
PTE against the significant emission rates in 40 CFR 52.21(b)(23)(i).

### LAER — Lowest Achievable Emission Rate
The control standard in a nonattainment NSR permit. Stricter than BACT because
cost is not a defence. If any comparable source anywhere achieves a rate, you match
it.
*Why it matters for us:* moving from an attainment county to a nonattainment county
swaps BACT for LAER. That is a real capex increase on top of the delay.

### PTE — Potential to Emit
The maximum tons per year a source could emit at its physical design capacity,
running 8,760 hours, unless a federally enforceable permit condition legally caps
it lower.
*Why it matters for us:* PTE is the number every threshold is compared against. It
is also the most misunderstood concept in the product. Intent to run less does not
reduce it.

### Synthetic minor
A source that would be a major source at full operation, but stays under the
threshold because it accepted a legally binding limit in its permit. Usually a cap
on annual run hours or fuel throughput.
*Why it matters for us:* it is the main lever the config search pulls. At Loudoun a
5,337 hr/yr cap turns a 57-month permit into a 17-month one, at the price of 39% of
the year offline.

### Title V
The federal operating permit, as opposed to the construction permit. The engine
fires it at 100 tons per year of any criteria pollutant or 10 tons of a single
hazardous air pollutant.
*Why it matters for us:* it runs after construction permitting and rarely blocks
the build, but it adds a second public comment window and permanent annual
compliance cost. The engine fires it as a trigger with zero months added.

### NSPS — New Source Performance Standards
Technology standards under Clean Air Act section 111 that apply to new equipment by
category, no matter where it is built or how big the site is.
*Why it matters for us:* Subpart KKKK covers stationary combustion turbines. The
EPA rule at 91 Fed. Reg. 1910, published 15 January 2026, is the one that closed
the trailer-mounted "nonroad engine" loophole xAI used.

### NESHAP — National Emission Standards for Hazardous Air Pollutants
Standards under Clean Air Act section 112 for the federally listed hazardous air
pollutants. Subpart ZZZZ is the one for reciprocating engines.
*Why it matters for us:* it sets a control floor for engine configurations and it
is why formaldehyde is tracked separately in the emissions module.

### Attainment / nonattainment
EPA's designation for whether an area meets a National Ambient Air Quality Standard
for a given pollutant. Attainment means it meets it. Nonattainment means it does
not, and comes with a severity class: marginal, moderate, serious, severe, extreme.
*Why it matters for us:* this single field flips the pathway. It is the reason two
identical plants 40 miles apart get different answers, and it is the one fact the
EPA Green Book supplies.

### Criteria pollutant
The six pollutants EPA sets national ambient standards for: ozone, particulate
matter, carbon monoxide, sulfur dioxide, nitrogen dioxide, and lead.
*Why it matters for us:* the major-source test is run against these. The engine
tracks NOx, CO, PM10, PM2.5, SO2 and VOC, and excludes CO2e and formaldehyde from
the criteria comparison.

### HAP — Hazardous Air Pollutant
A specifically listed toxic compound. Different programme from the criteria
pollutants and different thresholds. The one the engine uses is 10 tons per year of
a single HAP, which triggers Title V.
*Why it matters for us:* formaldehyde from gas combustion is the one that bites.
Our 500 MW plant is at 3.2 tpy with an oxidation catalyst, but a lean-burn engine
plant hits 295 tpy, which is a completely different regulatory conversation.

### Offsets
Verified emission reductions you buy from existing sources in the same
nonattainment area, at a ratio above 1:1, to compensate for what you will add.
*Why it matters for us:* in a moderate ozone area the ratio is 1.15, so our plant
needs 170 tons. In severe and extreme areas the credits often do not exist at any
price, which is why the engine calls a ratio of 1.3 or higher a hard stop rather
than a delay.

### Increment (PSD increment)
A fixed cap on how much a pollutant concentration is allowed to rise in an area
above a historical baseline. It is a shared budget, consumed in order by whoever
permits first.
*Why it matters for us:* it means a clean county can still be closed to you. The
engine flags 80% consumed and calls 95% a hard stop, because at that point no
major source may be permittable there at any timeline.

### Class I area
A national park or wilderness area given the strictest air protection under the
Clean Air Act, including protection of visibility and deposition, not just health.
*Why it matters for us:* Shenandoah at 60 km triggers Federal Land Manager
notification and an AQRV analysis, worth +6 months. The FLM can object on
visibility grounds even when every health number passes.

### AQRV — Air Quality Related Values
The things a Class I area is protected for beyond human health. Visibility, and
deposition of nitrogen and sulfur into soil and water.
*Why it matters for us:* it is a second veto held by a different federal agency,
running on a different clock from the state permit.

### AERMOD
EPA's regulatory air dispersion model. It takes stack parameters, terrain and
meteorology and predicts ground-level concentrations, which are then compared
against the ambient standards and the increment.
*Why it matters for us:* the engine does not run AERMOD. It predicts *whether you
will have to*, and whether it will be the cheap flat-terrain version or the
expensive complex-terrain version. 180 m of relief at the Loudoun site triggers the
expensive one.

### AP-42
EPA's published *Compilation of Air Pollutant Emission Factors*. Pounds of each
pollutant per unit of fuel burned or product made, by equipment type.
*Why it matters for us:* every emission factor in `agent/emissions.py` comes from
AP-42 and carries its table number in the code. Table 3.1 for turbines, 3.2 for gas
engines, 3.4 for diesel engines.

### Heat rate
Btu of fuel consumed per kWh of electricity produced. Lower is more efficient. A
combined-cycle turbine is 6,800 Btu/kWh, a simple-cycle turbine 10,500.
*Why it matters for us:* it is the bridge between megawatts and pollution.
Emissions scale with fuel burned, not with nameplate rating, and heat rate is how
you get from one to the other.

### Simple cycle vs combined cycle
A simple-cycle turbine burns gas, spins, and exhausts the hot gas. A combined-cycle
plant captures that exhaust in a heat recovery steam generator and drives a second
turbine with the steam.
*Why it matters for us:* two consequences pull in opposite directions. Combined
cycle burns 35% less fuel per MW, so less pollution. But the steam cycle puts it on
the List of 28, which drops the major-source threshold from 250 tpy to 100.

### SCR — Selective Catalytic Reduction
Ammonia injected into the exhaust over a catalyst, converting NOx to nitrogen and
water. Around 90% reduction.
*Why it matters for us:* it is what takes our plant from 0.0992 to 0.0099 lb/MMBtu
of NOx. Usually the single most expensive item in a BACT determination.

### Oxidation catalyst
A catalyst in the exhaust that oxidises carbon monoxide and unburned hydrocarbons.
About 90% on CO, 50% on VOC, 70% on formaldehyde.
*Why it matters for us:* without it, CO is the controlling pollutant at 1,221 tpy
and the answer looks worse than reality. With it, CO drops to 122 tpy and NOx takes
over as the binding constraint. The demo config includes it.

### DLN — Dry Low-NOx combustors
A combustor design that mixes fuel and air more evenly so the flame burns cooler
and produces less NOx. No water, no ammonia, no add-on equipment. Around 69%
reduction.
*Why it matters for us:* it is the cheapest NOx control on a turbine and it applies
before SCR. The code refuses to let you specify it on a reciprocating engine.

### Tier 4 (Tier 4 final)
EPA's strictest emission certification for new non-road and stationary compression
ignition engines. Certified on engine output in grams per kWh, not on fuel input.
*Why it matters for us:* the code handles Tier 4 as an override rather than a
percentage reduction, because the certification is output-based. Values come from
40 CFR 1039.101 Table 7.

### Behind-the-meter
Generation built on the customer's side of the utility meter, serving the load
directly instead of going through the grid.
*Why it matters for us:* this is the whole product. Developers go behind-the-meter
to escape the interconnection queue, and discover the air permit is the new queue.
Of about 90 GW announced, 2.2% is operating.

### Interconnection queue
The line you join to get a grid connection. The utility studies your impact on the
system, in order, and the study alone can take a year.
*Why it matters for us:* it is the reason on-site generation exists as a strategy.
Musk to Dwarkesh: "They have to do a study for a year. A year later, they'll come
back to you with their interconnect study."

### The List of 28
The 28 named source categories in 40 CFR 52.21(b)(1)(i)(a) that become PSD major
sources at 100 tons per year instead of 250.
*Why it matters for us:* item one is "fossil fuel-fired steam electric plants of
more than 250 million Btu/hr heat input." A combined-cycle plant is on it. A
simple-cycle plant is not. A data center is not. One design decision moves the
threshold by 150 tons.

---

## Terms that come up in follow-up questions

### NAAQS
National Ambient Air Quality Standards. The concentration limits in the air itself
that the attainment and nonattainment designations are measured against.

### EPA Green Book
EPA's published dataset of nonattainment area designations and classifications.
One download, no API. It is the source for every attainment field in the engine.

### NEI
EPA's National Emissions Inventory. Where the permitted emissions of existing major
sources come from, which is how increment consumption gets estimated.

### ERC — Emission Reduction Credit
A tradable, verified ton of reduction, registered with a state. What you actually
buy when you buy an offset.

### FLM — Federal Land Manager
The agency running a Class I area, usually the National Park Service or the Forest
Service. It gets notified and can object on AQRV grounds.

### Permit by rule / general permit
A pre-written permit for a common, small source. You register against it instead of
applying. Fastest pathway in the engine, 1 / 2 / 4 months, available in Texas and
Ohio in our state table.

### Source aggregation
EPA's rule that units which are contiguous or adjacent, under common control, and
in the same major industrial grouping count as one source. It is what stops you
splitting a plant to duck a threshold.
*Why it matters for us:* the code models it. Setting `units=4` does not reduce
emissions and adds a warning plus three months.

### OTR — Ozone Transport Region
A multi-state region in the Northeast where nonattainment-style NOx rules apply
statewide regardless of local monitor readings. New Jersey is in it.

### MMBtu/hr, tpy, lb/MMBtu
Million Btu per hour, the unit of heat input. Tons per year, the unit every
threshold is written in. Pounds per million Btu, the unit of an emission factor.
The whole calculation is: lb/MMBtu x MMBtu/hr x hr/yr / 2000 = tpy.
