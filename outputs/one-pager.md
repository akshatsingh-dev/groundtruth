# Groundtruth

**Announced ≠ deliverable.** An agent that works out which air permit a data center
power project needs at that exact parcel, and then goes and finds ground where the
answer is better.

Mireye's deck screens whether a site is good. Slope, flood, 345 kV, queue position.
This screens whether they will let you switch it on. It is the layer immediately
after their API already said yes.

Built for the Mireye Build Challenge, August 2026. Every number below traces to the
code, a live run, or `docs/evidence.md`, the claim-by-claim fact check in the repo.

---

## The gap

- **16 GW** of US data center capacity announced for 2026. About **5 GW** is on the
  ground. Transformer lead times run to five years and turbine order books are full
  into 2030. (Sightline Climate, via InvestmentNews, 14 Jul 2026)
- **Q1 2026: 75 projects worth about $130 billion blocked or delayed.** That matches
  the whole prior year in a single quarter. Active opposition groups went from 396 at
  the end of 2025 to **833 across 49 states** by March. (Data Center Watch)
- Behind-the-meter does not rescue it. Of roughly **90 GW** of announced onsite
  generation across **59 projects, 2.2% is operating.** 36% is permitted. 60% is still
  an announcement. (Cleanview, through May 2026)

**Which permit you need is decided by where the land is, not by what you are
building.** Developers buy for power, fiber and price. They find out afterwards.

---

## The proof, on one real parcel

21571 Beaumeade Cir, Ashburn VA. Loudoun County, resolved at rooftop grade,
confidence 0.95.

**Mireye says yes.** 120 m to the nearest transmission line. 504 m to the Beaumeade
substation, 230 kV, in service. Gas at 3.75 km. 715 MW of active interconnection
queue in the county. Any siting deck signs this off.

**The same 106-field `data_center_siting` call also says wait.**
`in_air_quality_nonattainment: true`. `air_quality_worst_classification: Moderate`,
2015 8-hour ozone, which sets the NOx major-source threshold at 100 tpy and brings
1.15:1 offsets. `nearest_class_i_area_name: Shenandoah NP` at 63,478 m, inside the
100 km Federal Land Manager radius under 40 CFR 52.21(p). Virginia DEQ has approved
exactly one air permit for a data center campus with onsite gas generation, Vantage
VA2.

One call. 106 credits. Both answers, each cited to EPA_GREEN_BOOK, EPA_CLASS_I_AREAS
or EIA_POWER with a fetch timestamp. Raw captures in `docs/api-captures/`.

---

## What the agent does

1. **Resolve.** `/v1/lookup`. Refuses a low-confidence match instead of guessing.
2. **Physical read.** `/v1/fetch` presets and `/v1/proximity`. Terrain, land cover,
   transmission, gas, receptors within a kilometre.
3. **Potential to emit.** MW × heat rate × AP-42 factors × 8,760 hours. Local
   arithmetic, no network, so it runs before anything is bought.
4. **Pathway.** Source category, threshold, attainment classification, offset ratio,
   Class I distance, state overlay. Out comes one of five pathways, from
   permit-by-rule to major nonattainment NSR, with a month range for that agency.
5. **Non-air blockers.** County moratoria and zoning posture, federal dockets, gas
   reachability.
6. **Act.** When the pathway fails, the agent mutates the input and re-runs itself.
   Outward across a ring of candidate parcels at 30, 60 and 120 km. Sideways across
   the design space at the current parcel.

Step 6 is the difference between a report and an agent. The live run screened 13
candidate parcels and 8 generation configurations before it wrote a sentence.

The pathway engine runs three ways on one project: once on the announced parcel, once
per candidate config, once per candidate parcel. Only the parcel loop spends Mireye
credits. 80 of the live run's 94.

---

## The live run

Cumberland County, New Jersey. 400 MW simple-cycle gas, uncontrolled, no enforceable
hour cap. Announced energization December 2027.

| | |
|---|---|
| Pathway | **Major nonattainment NSR.** 41–104 months, 66 likely |
| Controlling pollutant | NOx at **5,887 tpy** against a **50 tpy** threshold |
| Why 50 | Serious ozone, Philadelphia-Atlantic City PA-NJ, plus the Ozone Transport Region |
| Offsets | **7,064 tons** of verified NOx reductions, bought inside the area at 1.2:1, LAER with no cost defense |
| Schedule | 16 months to the announced date. 69 required. **Probability 2%** |
| Also fired | NJ's environmental justice denial authority (N.J.S.A. 13:1D-157), state toxics, and two live federal dockets touching the developer and the county |

**The act, part one.** Alternate parcel: New Castle County, DE. 37 miles west,
24 months saved. Read it honestly. That is still major nonattainment NSR. The whole
Northeast sits in the Ozone Transport Region, so you cannot drive out of the 50 tpy
threshold inside 120 km. What moving buys is New Jersey's EJ statute and state toxics
programme, and that is worth two years, not a pathway flip.

**The act, part two.** Config search: solid oxide fuel cells are the only change that
flips the pathway. Minor NSR, 44 months saved. SCR plus dry low-NOx takes NOx from
5,887 to 182 tpy and offsets from 7,064 tons to 219, a thirty-fold cut in the hardest
procurement problem on the project, and still does not clear 50.

The backtest froze this project's public facts at 1 March 2026. On 20 May 2026, 80
days later, Nebius replaced the gas engines at Vineland with 328 MW of Bloom solid
oxide fuel cells under a deal worth up to $2.6B. The config search names the swap the
developer actually made.

13 tool calls. 94 Mireye credits. Every physical fact carrying its source, its fetch
timestamp and its confidence.

---

## The national artifact

3,222 counties scored against one fixed plant: 500 MW combined cycle, dry low-NOx
plus SCR plus oxidation catalyst, 148 tpy NOx. Best-available controls, not a
strawman. The equipment never changes, so the only variable is the ground.

**2,843 major PSD. 379 major nonattainment NSR. Zero minor.**

There is no county in the United States where a 500 MW onsite gas plant is a minor
source. The question is never whether you clear major review. It is which major
review and whose desk. Fastest is Brewster County, Texas at 609 days. Slowest is all
21 New Jersey counties at 1,918. **1,309 days of spread. Three and a half years, for
identical equipment.**

---

## What we combined Mireye with

Their first two examples.

**Court filings. CourtListener / RECAP.** Federal dockets by developer and by county,
pulled live. `National Association for the Advancement of Colored People v. X.AI
Corp.`, 3:26-cv-00074, N.D. Miss., filed 14 April 2026, cause 42:7413(b) Clean Air
Act. That is 27 unpermitted turbines at Colossus 2 in Southaven, Mississippi, with a
preliminary injunction hearing late this month. Fetched 5 Aug 2026 and cached with
the timestamp.

Most coverage of the regulatory backdrop has it backwards, so the engine states it
carefully. EPA's 15 January 2026 NSPS (91 Fed. Reg. 1910, new subpart KKKKa) did
**not** close the nonroad-engine reading. It finalised a *conditional* exclusion, and
that exclusion is not operative. It takes effect only if EPA adopts Title II
standards for portable turbines, which has not happened. The trailer-mounted fast
path is an open legal question in active litigation. Not a loophole and not closed.

**Permit databases. EPA Green Book.** 463 nonattainment designations across 245
counties, parsed straight from EPA's `nayro.dbf` and `areadata.dbf`. EPA publishes
dBASE and BIFF only, and dBASE III is 60 lines of `struct.unpack`, so there is no
GIS stack in this repo. Mireye's own preset returns nonattainment status and
classification at a coordinate, which beats a county join, so the Green Book runs as
an independent cross-check. It agreed. It also exposed a real gap:
`air_quality_worst_classification` is blank for PM2.5, PM10, SO2, NO2 and lead, which
we filed as a field request and Mireye's screener confirmed.

---

## Who writes the cheque

| Buyer | Why now | Deal shape |
|---|---|---|
| **Hedge funds and asset managers** long GEV, Vertiv, Bloom, Constellation, Talen, Vistra, Equinix | The market prices announced capacity as deliverable capacity. That is the trade. | Alt-data subscription, **$50k–500k/yr**. 2–6 week cycle, no procurement gauntlet. |
| **Site selection.** Hyperscaler and colo teams, QTS, Vantage, CyrusOne, Aligned, behind-the-meter developers, turbine lessors | One wrong site is tens of millions in options, engineering and legal, plus 18 to 36 months. Nebius is the live example, under a $17.4B Microsoft deal. | **$250k–1M/yr** enterprise, or **$10–25k per site report**. The report is the path to revenue in months rather than years. |
| **Air permitting consultancies.** Trinity, ERM, Onterris | They run this screen by hand today. They keep the billable interpretation and the stamp. | Per-seat or per-screen licence. Channel, not competitor. |
| **Infrastructure lenders and funds** | Underwriting against announced energization dates. | Same feed, diligence use case. |
| **The other side of the table**<br>county planning offices, state air agencies | The same engine runs backwards. Virginia DEQ has approved exactly one air permit for a data center campus with onsite gas. That is a capacity problem, not an obstruction one, and an agency that pre-screens an application in a day instead of a quarter is the version municipalities buy. | Public procurement. Slower to close, and the only buyer here with a standing budget line for it. |

Sightline Climate, Data Center Watch, BNEF and JLL already sell pipeline tracking.
None of them computes the permit pathway. None of them goes looking for a parcel
where it changes.

---

## COGS, which is Mireye revenue

The Cumberland run cost **94 Mireye credits**. 14 for the parcel screen, 80 for the
13-parcel alternate-site search. At the published $1.00 per 1,000 credits that is
9.4 cents a project. 3,000 tracked projects re-swept weekly is about **282,000
credits a week, 1.2M a month, roughly $1,200/month of Mireye spend** against an
alt-data subscription priced at $50k–500k a year. A full-depth screen
(`data_center_siting` + `terrain` + `utilities` + one `/v1/ask`) measures at ~155
credits and takes the same cadence to ~2M credits a month.

---

## What this is not

- **The backtest is 3 cases and one is a self-declared miss.** Vineland NJ and
  Project Jupiter NM both hit on the mechanism that actually bound. xAI Colossus 1 in
  Memphis is the miss: the engine said major PSD, roughly 26 months, and xAI energised
  in weeks by taking the position that trailer-mounted turbines are nonroad engines.
  The engine prices the compliant path. It has no variable for a developer who runs
  anyway and litigates. A real backtest needs a point-in-time panel across hundreds of
  projects, and that panel does not exist.
- **8 states modelled** from public permit records: VA, TX, GA, OH, AZ, NJ, NM, IL.
  The other 42 fall back to federal defaults and every record says which.
- **27 county posture records entered by hand.** Absence of a moratorium record is
  absence of evidence, not evidence of absence.
- **The county map is a screening layer.** It cannot see parcel increment, terrain or
  pipeline distance. The parcel run is the answer.
- **We cannot sign the opinion.** A licensed professional stamps a permitting
  determination and carries the liability. This tells you which conversation you are
  about to have, and those professionals are buyer three.

---

Built on Mireye. Repo, evidence ledger and the 2-minute demo in the submission.

---

## Where this goes: India

US first, because Mireye is US-only. India is the market this is built for. Axis Capital
calls the announced **6 to 8 GW by 2030** inflated and puts the real figure at **3.4 to
3.6 GW**. Operational stock is about **1.8 GW** of IT load today. **Over 10.5 GW sits in
land banking**, which is the local phrasing for announced and not broken ground. Power
connections run about 18 months and gensets from Caterpillar, Cummins and MTU are booked
out two years.

Same gap, different regulator, different fuel. The buyer is different too. In the US this
sells to developers and funds. In India the first customer is more likely a district
planning office or a state pollution control board, because the agencies are the
bottleneck and they procure.

`providers/base.py` is an interface and `providers/mireye.py` is the US implementation of
it. The agent, the emissions estimator and the pathway engine never import Mireye. That
cost about twenty lines and it makes going international a data problem rather than a
rewrite. The permit logic is jurisdiction-specific and would need rebuilding for CPCB and
the state boards, but the shape holds.

The substrate is what's missing. There is no Mireye for India and no equivalent. Filed as
a feature request: parcel resolution, administrative hierarchy at a coordinate, and
DISCOM territory would be enough to port this.
