# Evidence ledger

Every factual claim in `docs/build-brief.md` §1, §8, §10 and §11, checked against its
source. Checked 5 August 2026.

Read the four **RED** rows first. Those are the ones that will cost you if a judge
spot-checks them, and one of them is currently stated backwards in both the brief and
in `agent/pathway.py`.

## Scoreboard

| verdict | count |
|---|---|
| confirmed | 13 |
| needs rewording | 5 |
| unsupported | 1 |

---

## Ledger

| # | claim | number as stated in brief | what the source actually says | verdict | URL | checked |
|---|---|---|---|---|---|---|
| **E1** | EPA NSPS closes the nonroad loophole | "Jan 15, 2026 — EPA published a NSPS for stationary combustion turbines (91 Fed.Reg. 1910), **closing the 'nonroad engine' loophole**: turbines used for primary power at a fixed site need Clean Air Act permits regardless of being trailer-mounted." | **Citation right, substance backwards.** 91 FR 1910, 15 Jan 2026, "New Source Performance Standards Review for Stationary Combustion Turbines and Stationary Gas Turbines," pp. 1910–2005, new subpart KKKKa. The rule **creates a conditional exclusion**, it does not close one: it removes turbines from the "stationary combustion turbine" definition *if* they meet the nonroad engine definition and are certified under Title II. That exclusion is **not yet operative** — EPA has not adopted Title II standards for portable turbines, which requires a separate rulemaking. Clark Hill's headline is "EPA's New Turbine Rules **Ease** Air Permits for Data Centers." The rule also moves low-use turbines out of Title V major-source permitting. | **RED — needs rewording** | [FR](https://www.federalregister.gov/documents/2026/01/15/2026-00677/new-source-performance-standards-review-for-stationary-combustion-turbines-and-stationary-gas) · [Justia](https://regulations.justia.com/regulations/fedreg/2026/01/15/2026-00677.html) · [Clark Hill](https://www.clarkhill.com/news-events/news/epa-turbine-rules-air-permitting-data-centers/) · [Frantz Ward](https://www.frantzward.com/epa-moving-to-regulate-data-center-turbines-as-mobile-sources/) | 2026-08-05 |
| **E2** | Fund manager quote | "Announced capital is not deliverable capacity. Those are different things, and the market keeps pricing them the same." — attributed to "a fund manager… in print in July 2026" | **No such quote exists anywhere I can find.** Zero search hits on the exact string. It is not in the InvestmentNews piece (14 Jul 2026) the surrounding paragraph cites, and not in the HedgeCo piece (22 May 2026) cited immediately after. | **RED — unsupported** | searched: exact phrase, both cited articles | 2026-08-05 |
| **E3** | xAI speed | "~100,000 GPUs in ~19 days — a timeline Jensen Huang has said normally takes four years" | Faithfully copied from Energy.Media, but the underlying fact is looser. The **19 days is hardware-install to start-of-training**; the full Colossus 1 buildout was **122 days**. Huang's on-record words are that it was "superhuman" and "as far as I know, there's only one person in the world who could do that." The "four years" is reported as his comparison to a typical build, not as a verbatim quote I could source. | **RED — needs rewording** | [Energy.Media](https://energy.media/energy-deals/xai-gas-turbine-lawsuit-permitting-explained/) · [Entrepreneur](https://www.entrepreneur.com/business-news/nvidia-ceo-jensen-huang-praises-elon-musk-xai-superhuman/481325) | 2026-08-05 |
| **E4** | xAI litigation | "NAACP/SELC/Earthjustice sued in April 2026; DOJ moved to intervene in June; injunction hearing late August 2026" — presented as following from the Memphis 19-day build | **Dates all confirmed. Wrong site implied.** The April 2026 suit is over **Colossus 2 in Southaven, Mississippi** (27+ turbines, ~495 MW), filed in N.D. Miss.; DOJ moved to intervene and dismiss **16 June 2026**; PI hearing late August 2026. The 19-day build was **Colossus 1 in Memphis, Tennessee** — a different facility in a different state, whose permit fight is a separate Shelby County appeal. | **RED — needs rewording** | [Earthjustice](https://earthjustice.org/press/2026/xai-sued-for-illegal-power-plant) · [Mississippi Today](https://mississippitoday.org/2026/04/15/data-center-turbines-southaven/) · [CNBC](https://www.cnbc.com/2026/06/16/usdepartment-of-justice-calls-for-dismissal-of-naacp-xai-lawsuit-.html) | 2026-08-05 |
| E5 | Morgan Stanley gap | "68 GW between 2026 and 2028. Only 15 GW under construction; another 15 GW covered by available or contracted grid capacity. A 38 GW hole." | Exact match. Add one qualifier: Morgan Stanley's **base case still leaves a 1–11 GW deficit through 2028** after gas turbines, bitcoin-miner conversions and other mitigations. 38 GW is the gross gap before solutions, which is how the brief uses it — but say "before mitigations" or a judge will. | confirmed | [24/7 Wall St](https://247wallst.com/investing/2026/08/04/ge-vernova-set-to-be-biggest-winner-from-ai-data-centers-massive-power-shortfall/) | 2026-08-05 |
| E6 | 16 GW vs 5 GW | "16 GW announced for 2026. Closer to 5 GW actually available on the ground" | Confirmed verbatim, plus transformer lead times "up to 5 years" and turbine order books "full into 2030." Author Gregg Greenberg, 14 Jul 2026. | confirmed | [InvestmentNews](https://www.investmentnews.com/equities/data-centers/267347) | 2026-08-05 |
| E7 | Sightline pipeline | "~140 tracked projects slated to finish in 2026, only ~5 GW actively under construction; Sightline estimates 30–50% slips to 2027 or later" | Exact: "roughly 16GW slated to complete in 2026 across ~140 projects tracked by Sightline Climate, only ~5GW was actively under construction… Sightline estimates 30–50% of that pipeline will slip into 2027 or later." **Note:** this and E6 are the *same* underlying Sightline dataset. The brief presents them as two independent bullets. Merge them or attribute both to Sightline. | confirmed | [Archdesk](https://archdesk.com/blog/global-ai-data-center-construction-2026) | 2026-08-05 |
| E8 | Q1 2026 blocked | "at least 75 projects worth ~$130 billion blocked or delayed — matching the entire prior year in a single quarter. Opposition groups more than doubled to 833 across 49 states." | Exact match on all four numbers. The doubling is **396 groups at end-2025 → 833 by March 2026**. Bonus: 300+ state data center bills filed in the first six weeks of 2026, statewide moratorium proposals in 14 states. | confirmed | [Data Center Watch](https://www.datacenterwatch.org/q1-2026) · [NBC](https://www.nbcnews.com/tech/tech-news/data-center-opposition-sharply-rising-2026-study-finds-rcna349728) | 2026-08-05 |
| E9 | Capex and grid spend | "Hyperscaler AI capex above $690 billion in 2026; US utilities committed $1.4 trillion in grid spending through 2030" | Both exact. | confirmed | [InvestmentNews](https://www.investmentnews.com/equities/data-centers/267347) | 2026-08-05 |
| E10 | Behind-the-meter | "Of ~90 GW of announced behind-the-meter generation, 2.2% is operating. 36% is permitted. 60% exists only as announcements." | Exact: ~90 GW across **59 projects**; ~2 GW (2.2%) operating; ~1.2% under construction; ~36% permitted; ~60% announcement/early-stage. Updated through May 2026. Cite the project count too — 59 is a more striking number than 90 GW. | confirmed | [Cleanview](https://cleanview.co/reports/behind-the-meter-data-centers) | 2026-08-05 |
| E11 | New Mexico pipeline | "New Mexico blocked the gas pipeline feeding a 2.45 GW onsite plant for an OpenAI/Oracle Stargate project" | True, and much better than stated. The project is **Project Jupiter**, Santa Teresa, **Doña Ana County**, NM, ~1,400 acres, BorderPlex Digital Assets + STACK, 18-year Oracle lease, OpenAI end user. The pipeline is Energy Transfer's **18-mile, 24-inch "Green Chile" lateral**. Land Commissioner **Stephanie Garcia Richard denied the right-of-way on 20 March 2026 and again on 14 July 2026**. The 2.45 GW is **Bloom fuel cells**, not turbines — the original January application was for gas turbines and was withdrawn. | confirmed | [DCD](https://www.datacenterdynamics.com/en/news/new-mexico-regulators-reject-natural-gas-pipeline-for-oracles-25gw-project-jupiter-data-center/) · [Source NM](https://sourcenm.com/2026/07/16/new-mexico-land-commissioner-blocks-project-jupiter-related-pipeline-from-building-on-state-land/) · [Public Citizen](https://www.citizen.org/article/energy-transfer-green-chile-gas-pipeline-openai-oracle-jupiter-stargate-ai-data-center/) | 2026-08-05 |
| E12 | Nebius state | "Nebius cannot get an air permit for a 400 MW onsite gas plant — under a $17.4 billion Microsoft deal." Brief and §6 say **NJ**. | **NJ is correct.** Site is **Vineland, Cumberland County, New Jersey**, off S. Lincoln and Sheridan Avenues, developed with DataOne; 300 MW IT load; **36 Bergen Engine gas units, 403 MW combined**; NJDEP application **PCP250002**; Microsoft deal **$17.4B / 5 years, September 2025**. **Update needed:** the permit was never denied — it stalled, and on **20 May 2026 Nebius replaced the engines with 328 MW of Bloom fuel cells** under a 10-year, up-to-$2.6B deal. Present tense "cannot get an air permit" is now stale. | needs rewording | [Sierra Club NJ](https://www.sierraclub.org/new-jersey/blog/2026/02/sierra-club-sustain-south-jersey-and-local-farmers-oppose-massive-vineland) · [WHYY](https://whyy.org/articles/data-center-artificial-intelligence-vineland-new-jersey/) · [Nebius](https://nebius.com/newsroom/nebius-and-bloom-energy-partner-to-power-ai-infrastructure-build-out) | 2026-08-05 |
| E13 | Virginia DEQ | "Virginia DEQ has approved exactly one air permit for a data center campus with on-site gas generation." | Confirmed, and name it: the one permit is **Vantage VA2**. DEQ has **one other application pending, in Charles City**. Also worth knowing: revised presumptive BACT for data center generators applies to applications received on or after **1 July 2026**. | confirmed | [Virginia Mercury](https://virginiamercury.com/2026/07/20/data-centers-want-to-build-their-own-gas-turbines-would-that-skirt-state-renewable-energy-laws/) · [VA DEQ](https://www.deq.virginia.gov/news-info/shortcuts/permits/air/issued-air-permits-for-data-centers) | 2026-08-05 |
| E14 | Trinity / List of 28 | "Combined-cycle turbines at a data center fall under the 'fossil fuel-fired steam electric plants >250 MMBtu/hr' named source category — which drops the PSD major source trigger from 250 tpy to 100 tpy. Data centers themselves are not on the List of 28." | Confirmed almost verbatim: "Combined cycle turbines used for power generation at a data center are included under the 'fossil fuel-fired steam electric plants of more than 250 MMBtu/hr heat input' named source category" and "Data centers are not classified as one of the 28 named source categories." One nit: Trinity cites **40 CFR 51.166(b)(1)**; `agent/pathway.py` cites **40 CFR 52.21(b)(1)(i)(a)**. Both are correct — 51.166 governs SIP-approved state programs, 52.21 the federal PSD program. Article dated 23 Jun 2025. | confirmed | [Trinity](https://trinityconsultants.com/resources/powering-the-next-generation-of-data-centers-navigating-due-diligence-and-air-permitting-for-data-center-development/) | 2026-08-05 |
| E15 | Musk — interconnect | "They have to do a study for a year. A year later, they'll come back to you with their interconnect study." | Verbatim. Episode published **5 February 2026**. | confirmed | [Dwarkesh](https://www.dwarkesh.com/p/elon-musk) | 2026-08-05 |
| E16 | Musk — hardware lesson | "It's like those who have lived in software land don't realize that they're about to have a hard lesson in hardware — that it's actually very difficult to build power plants... the utility industry is a very slow industry. They impedance match to the government, to the public utility commission." | **Three separate quotes stitched with an ellipsis, and the wording is off.** Actual: "Those who have lived in software land don't realize they're about to have a hard lesson in hardware." / "It's actually very difficult to build power plants. You don't just need power plants, you need all of the electrical equipment." / "The utility industry is a very slow industry. They pretty much impedance match to the government, to the **Public Utility Commissions**. They impedance match literally and figuratively." Use the third sentence alone on screen — it is the best of the three and it is exact. | needs rewording | [Dwarkesh](https://www.dwarkesh.com/p/elon-musk) | 2026-08-05 |
| E17 | Musk — Nevada solar | "I think it's pretty hard to cover Nevada in solar panels. You have to get permits. Try getting the permits for that. See what happens." | Verbatim. | confirmed | [Dwarkesh](https://www.dwarkesh.com/p/elon-musk) | 2026-08-05 |
| E18 | Notes on Space GPUs | "you can't plug into utilities (queues too long), can't go behind-the-meter (turbine lead times past 2030), can't do solar (permits and tariffs)" | Accurate paraphrase. Actual lines: "You can't plug into the utilities—the interconnect queues are too long." / "You can't do behind the meter and generate power yourself—lead times for turbines stretch past 2030." / "You can't do solar on Earth, because of permits, and because of the tariffs." | confirmed | [Dwarkesh](https://www.dwarkesh.com/p/notes-on-space-gpus) | 2026-08-05 |
| E19 | India — Axis Capital | "announced targets of 6–8 GW by 2030 'look inflated'; realistic estimate 3.4–3.6 GW operational by mid-2030. Gensets from three global brands booked out two years; power connection delays ~18 months." | All confirmed. Add specifics: the three brands are **Caterpillar, Cummins, MTU**, and they are **diesel** gensets. Axis also gives a downside case of **~2.8 GW** under execution constraints. Article 3 Aug 2026. | confirmed | [newkerala](https://www.newkerala.com/news/a/supply-chain-constraints-may-cap-indias-data-centre-capacity-773.htm) | 2026-08-05 |
| E20 | India — land banking | "10.5 GW sits in the land-banking stage" (ICICI Securities) | Confirmed: "more than 10.5 gigawatts of data center capacity currently remains in the land-banking stage." | confirmed | [Compute Forecast](https://www.computeforecast.com/articles-post/india-data-center-hub-investment-outlook/) | 2026-08-05 |
| E21 | India — operational | "Operational capacity: ~1.8 GW as of H1 2026." | Confirmed, but **not from either source the brief cites**. It is Savills India: operational stock **1,819 MW IT in H1 2026**, up 36.6% from 1,332 MW. Note the same Axis Capital note used for E19 says ~1.4 GW — a different measure. Cite Savills for this one and the discrepancy disappears. | needs rewording | [Savills via Realty Today](https://therealtytoday.com/news/market-insights/indias-data-centre-infrastructure-reaches-18-gw-with-rising-global-investments-savills-india-report/) | 2026-08-05 |

---

## The four that matter

### E1 — the Federal Register cite is right, the sentence is wrong

This is the expensive one. The brief and `agent/pathway.py` both say the 15 January
2026 rule *closed* the nonroad-engine reading. It did the opposite in direction.

What the rule actually did, per the rule itself and three independent law-firm
readings: it finalised a **conditional exclusion** removing combustion turbines from
the "stationary combustion turbine" definition where the unit meets the nonroad engine
definition and is certified under Title II. EPA said in the preamble that turbines "may
qualify as 'a kind of internal combustion engine'" regulable as nonroad sources. The
exclusion only becomes effective if and when EPA adopts nonroad emission standards and
certification requirements for portable turbines — **a separate rulemaking that has not
happened.** Frantz Ward, May 2026: "such a reclassification would represent a
significant shift, effectively allowing certain temporary generation assets to bypass
NSR permitting."

So the trailer-mounted path is not closed. It is unsettled, and it is being fought in
court in Mississippi right now.

**Replacement wording that is supportable:**

> On 15 January 2026 EPA published a new NSPS for stationary combustion turbines
> (91 Fed. Reg. 1910, new subpart KKKKa). It did not settle the question that matters
> here. The rule finalised a *conditional* exclusion for turbines that qualify as
> nonroad engines — but that exclusion does not take effect until EPA adopts Title II
> standards for portable turbines, which it has not. Meanwhile the NAACP is asking a
> federal court in Mississippi to shut down 27 unpermitted turbines at xAI's Colossus 2,
> with a preliminary injunction hearing set for late August 2026. Anyone underwriting a
> trailer-mounted fast path today is underwriting an open legal question, not a
> loophole.

That version is more interesting than the original claim, and it is true.

Also fix `agent/pathway.py`: the `nsps_turbine` trigger repeats the wrong reading, and
its citation says "Subpart KKKK" where the new rule creates **KKKKa**. I do not own that
file. `backtest/cases.py` prints a correction whenever the trigger fires.

### E2 — the fund manager quote appears to be invented

"Announced capital is not deliverable capacity. Those are different things, and the
market keeps pricing them the same." Zero hits. Not in InvestmentNews. Not in HedgeCo.
Not anywhere.

It is the best-sounding sentence in the brief and it is the one that will get you
caught, because it is presented as a July 2026 quote from a named-category source
("a fund manager said it in print").

**Two supportable replacements, both real, both from the article the brief already
cites:**

> Michael Shawn, founder of Peregrine Private Client: "In a permit-constrained market,
> the winner isn't whoever spends the most. It's whoever already controls the land, the
> interconnect, and the power."

That is a better quote for this product than the fabricated one. It says the buyer's
problem in the buyer's words.

Or, if you want the framing without a quote, say it in your own voice and own it:

> Announced capital is not deliverable capacity. The market prices them the same. That
> is the trade.

Unattributed and in first person, that is a thesis. Attributed to an imaginary fund
manager, it is a fabricated quote.

### E3 — the 19 days is not the buildout

Energy.Media does say "roughly 100,000 GPUs in about 19 days," so the brief sourced it
honestly. But the primary reporting is that the **122-day** figure is the buildout and
19 days is install-to-training. Huang's sourced words are "superhuman" and "there's only
one person in the world who could do that." I could not source "normally four years" as
a verbatim Huang quote.

**Replacement:**

> xAI energised roughly 420 MW of trailer-mounted turbines in South Memphis and had
> ~100,000 GPUs training inside a 122-day buildout — 19 days from hardware install to
> first training run. Jensen Huang called it "superhuman." It was also done without a
> Clean Air Act construction permit, under a county reading that a turbine parked
> somewhere for under 364 days is a nonroad engine.

### E4 — two different xAI sites

Memphis, Tennessee (Colossus 1, ~35 turbines, >420 MW, Shelby County permit issued 2
July 2025 for 15 turbines, under appeal) and Southaven, Mississippi (Colossus 2, 27+
turbines, ~495 MW, the April 2026 NAACP/SELC/Earthjustice Clean Air Act suit in N.D.
Miss., DOJ intervention 16 June 2026, PI hearing late August 2026).

The brief's §6 and §7 say "xAI Memphis" for the litigated site. Say Southaven for the
lawsuit, Memphis for the 19-day build, and note they are 20 miles and one state line
apart. It is a small thing and it is exactly the kind of small thing that tells a judge
whether you read the filings.

---

## Regulatory facts added during this check

Not in the brief, verified here, and load-bearing for the backtest.

| fact | source | checked |
|---|---|---|
| Cumberland County NJ is in the Philadelphia-Atlantic City PA-NJ area, reclassified **Moderate → Serious** for the 2015 8-hr ozone NAAQS effective 30 July 2024. Serious drops the NOx major threshold to 50 tpy and the offset ratio to 1.2:1. Whole county, not partial. Design value 0.073 ppm. | EPA Green Book; [FR 30 Jul 2024](https://www.federalregister.gov/documents/2024/07/30/2024-16570/designations-of-areas-for-air-quality-planning-purposes-pennsylvania-new-jersey-maryland-delaware); cross-checked against `data/greenbook.json`, EPA export 2026-07-31 | 2026-08-05 |
| Doña Ana County NM (Santa Teresa / Sunland Park) is in the El Paso-Las Cruces TX-NM 2015 8-hr ozone area, **Marginal** — **partial county**, southern portion only. The violating monitors are at Sunland Park and Santa Teresa, the Project Jupiter site itself. The county also carries a **second** designation: Moderate for the 1987 PM10 NAAQS ("Dona Ana County; Anthony, NM"), also partial. The backtest excludes the PM10 designation because I could not confirm the site falls inside the Anthony boundary. | [NMED](https://www.env.nm.gov/air-quality/ozone/); EPA Green Book; cross-checked against `data/greenbook.json` | 2026-08-05 |
| Shelby County TN and DeSoto County MS are **Attainment/Unclassifiable** for the 2015 8-hr ozone NAAQS, effective 16 Jan 2018. Neither xAI site faces nonattainment NSR. | [MDEQ](https://www.mdeq.ms.gov/mdeq-announces-desoto-county-in-attainment-for-ozone-standard/); EPA Green Book | 2026-08-05 |
| Project Jupiter's original air permit applications covered **two microgrids ~1.25 miles apart**, 41 simple-cycle gas turbines, claiming NOx of **248.9 and 249.97 tpy** — each 1.1 tons under the 250 tpy major threshold. NMED called the applications incomplete on 19 Dec 2025 and wrote that a facility "that is 1.1 tons away from the 250" is **"not practically enforceable."** Applications prepared by **Trinity Consultants**. | [Albuquerque Journal, 9 Dec 2025](https://www.abqjournal.com/business/project-jupiter-permit-applications-forecast-massive-carbon-fuel-use/2932903); [Source NM, 19 Dec 2025](https://sourcenm.com/2025/12/19/nmed-says-data-center-project-jupiters-air-quality-applications-incomplete-for-now/) | 2026-08-05 |
| Nebius Vineland: **36 Bergen Engine units, 403 MW combined** (Sierra Club NJ, 27 Feb 2026); WHYY reported **32 gas engines plus 6 diesel emergency gensets** (25 Mar 2026). NJDEP application **PCP250002**, filed by DataOne. NJDEP was weighing whether to aggregate the site with the adjacent **Corning** plant as one stationary source. | [Sierra Club NJ](https://www.sierraclub.org/new-jersey/blog/2026/02/sierra-club-sustain-south-jersey-and-local-farmers-oppose-massive-vineland); [WHYY](https://whyy.org/articles/data-center-artificial-intelligence-vineland-new-jersey/) | 2026-08-05 |
| The DataOne lots **fall just outside** NJDEP's designated overburdened-community boundary, even though roughly half of Vineland's population lives in OBC tracts. The EJ statute is real; its application to this parcel was contested. Do not claim the EJ law blocked this permit. | reporting on NJDEP OBC mapping | 2026-08-05 |
| xAI Colossus 1: **up to 35 turbines, >420 MW** installed from mid-2024 with no CAA permit. Shelby County Health Department position: it "only regulates gas-burning generators if they're in the same location for more than 364 days." Permit for **15 turbines issued 2 July 2025**, appealed by NAACP and SELC. | [SELC](https://www.selc.org/press-release/memphis-health-leaders-grant-air-permit-for-xai-data-center/); [Inside Climate News](https://insideclimatenews.org/news/17072025/elon-musk-xai-data-center-gas-turbines-memphis/) | 2026-08-05 |

---

## What I could not verify

- **"Normally four years"** as a verbatim Jensen Huang quote. The sourced quotes are
  "superhuman" and "only one person in the world who could do that." Reporting attributes
  a four-year comparison to him; I found no transcript. Attribute loosely or drop it.
- **Whether 41 simple-cycle turbines was per microgrid or across both** at Project
  Jupiter. One reading gives ~1.4 GW, the other ~2.8 GW. The Albuquerque Journal reports
  "up to 2.8 gigawatts total," which the backtest uses. Flagged in `backtest/cases.py`.
- **Nebius Vineland MW.** Three published figures: 300 MW (Planning Board site plan),
  350 MW (WHYY), 403 MW of engine nameplate (Sierra Club), and 400 MW (Cleanview). These
  are probably IT load vs. generation nameplate and are not necessarily inconsistent, but
  do not state one as *the* number without saying which quantity it is.
- **DataOne's air permit application date.** One account gives 16 December 2025 and also
  says the permit had "been on hold since February 2025," which cannot both be right. The
  backtest uses only "under review, not granted, as of 27 Feb 2026," which is solid.
- **Any published count of residents within 1 km** of the Vineland site. None exists. The
  backtest leaves the field `None` rather than guess, which costs it the EJ hard stop.
