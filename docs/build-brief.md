# Deliverable — Build Brief

**Mireye Build Challenge · Submission deadline: Monday 10 August 2026**

> An AI investigator for the AI buildout. Every week someone announces a
> multi-billion-dollar data center. Most won't happen on time. Deliverable tells
> you which ones are real — and where the ones that fail should have gone instead.

**Tagline:** Announced ≠ deliverable.

---

## 1. The problem in one page

The chips exist. The money exists. The power doesn't.

**The gap is enormous and documented.**

- Morgan Stanley: US data centers need another **68 GW between 2026 and 2028**.
  Only 15 GW is under construction; another 15 GW is covered by available or
  contracted grid capacity. **A 38 GW hole.**
  ([24/7 Wall St, Aug 2026](https://247wallst.com/investing/2026/08/04/ge-vernova-set-to-be-biggest-winner-from-ai-data-centers-massive-power-shortfall/))
- **16 GW of data center capacity was announced for 2026. Closer to 5 GW is
  actually available on the ground**, after permitting delays, grid constraints,
  transformer lead times up to five years, and turbine order books full into 2030.
  ([InvestmentNews, Jul 2026](https://www.investmentnews.com/equities/data-centers/267347))
- Of ~140 tracked projects slated to finish in 2026, only ~5 GW was actively under
  construction; Sightline estimates **30–50% of the pipeline slips to 2027 or later**.
  ([Archdesk, Jul 2026](https://archdesk.com/blog/global-ai-data-center-construction-2026))

**Then it gets blocked.**

- Q1 2026 alone: at least **75 projects worth ~$130 billion blocked or delayed** —
  matching the entire prior year in a single quarter. Active opposition groups
  **more than doubled to 833 across 49 states**.
  (Data Center Watch, via InvestmentNews)
- Hyperscaler AI capex projected above **$690 billion in 2026**; US utilities have
  committed **$1.4 trillion** in grid spending through 2030.

**And routing around the grid doesn't work either.**

- Of ~90 GW of announced behind-the-meter generation, **2.2% is operating**. 36% is
  permitted. **60% exists only as announcements.**
  ([Cleanview](https://cleanview.co/reports/behind-the-meter-data-centers))
- New Mexico blocked the gas pipeline feeding a 2.45 GW onsite plant for an
  OpenAI/Oracle Stargate project.
- **Nebius cannot get an air permit for a 400 MW onsite gas plant** — under a
  **$17.4 billion** Microsoft deal.
- Virginia DEQ has approved **exactly one** air permit for a data center campus
  with on-site gas generation.
  ([Virginia Mercury, Jul 2026](https://virginiamercury.com/2026/07/20/data-centers-want-to-build-their-own-gas-turbines-would-that-skirt-state-renewable-energy-laws/))

### The specific unpriced fact

**Which permit you need is decided by where the land is, not by what you're building.**

Same 500 MW plant, two counties 40 miles apart:

| | County A | County B |
|---|---|---|
| Air quality status | Attainment | Nonattainment |
| PSD increment | Available | Consumed by 3 existing sources |
| Class I area within range | No | Wilderness 60 km upwind |
| **Permit pathway** | Minor NSR | **Major PSD + full dispersion modeling + public comment** |
| **Timeline** | 4–6 months | **2–3 years, may fail** |

Nobody screens for this before buying the land. They buy for power, fiber and
price, then find out.

### Regulatory context you need to get right

- **Jan 15, 2026** — EPA published a New Source Performance Standard for stationary
  combustion turbines (91 Fed.Reg. 1910), closing the "nonroad engine" loophole:
  turbines used for primary power at a fixed site need Clean Air Act permits
  regardless of being trailer-mounted.
  ([Clark Hill](https://www.clarkhill.com/news-events/news/epa-turbine-rules-air-permitting-data-centers/))
- That loophole is what let xAI stand up ~100,000 GPUs in ~19 days — a timeline
  Jensen Huang has said normally takes four years. NAACP/SELC/Earthjustice sued in
  April 2026; DOJ moved to intervene in June; injunction hearing late August 2026.
  ([Energy.Media](https://energy.media/energy-deals/xai-gas-turbine-lawsuit-permitting-explained/))
- Combined-cycle turbines at a data center fall under the "fossil fuel-fired steam
  electric plants >250 MMBtu/hr" named source category — which drops the PSD major
  source trigger from **250 tpy to 100 tpy**. Data centers themselves are *not* on
  the List of 28.
  ([Trinity Consultants](https://trinityconsultants.com/resources/powering-the-next-generation-of-data-centers-navigating-due-diligence-and-air-permitting-for-data-center-development/))
- Design choices interact with location: turbines vs engines, gas vs diesel, Tier 4
  engines, SCR, operating-hour limits that secure **synthetic minor** status, stack
  parameters.
  ([Onterris](https://www.onterris.com/our-thinking/air-permitting-for-data-centers-what-determines-your-timeline))

### The Musk hook (for the narrative, and it's real)

Dwarkesh Patel + John Collison with Elon Musk, published **5 Feb 2026**
([transcript](https://www.dwarkesh.com/p/elon-musk)):

> "They have to do a study for a year. A year later, they'll come back to you with
> their interconnect study."

> "It's like those who have lived in software land don't realize that they're about
> to have a hard lesson in hardware — that it's actually very difficult to build
> power plants... the utility industry is a very slow industry. They impedance match
> to the government, to the public utility commission."

> "I think it's pretty hard to cover Nevada in solar panels. You have to get permits.
> Try getting the permits for that. See what happens."

Dwarkesh's own summary ([Notes on Space GPUs](https://www.dwarkesh.com/p/notes-on-space-gpus)):
you can't plug into utilities (queues too long), can't go behind-the-meter (turbine
lead times past 2030), can't do solar (permits and tariffs).

**Musk's answer was to leave the planet. Ours is to find the ground that says yes.**

---

## 2. What the agent does

Input: a project — address or coordinate, proposed MW, generation config, target
energization date.

### Stage 1 — Resolve
`mireye_geocode` → `mireye_lookup`. Canonical parcel, county, state, tract.
Refuse low-confidence matches rather than guessing.

### Stage 2 — Physical read
`mireye_fetch` for parcel boundary/acreage, terrain and slope (drives dispersion),
land cover, elevation, plus `mireye_proximity` for distance to transmission,
substation, gas pipeline, airports, urban areas, and residential density.

### Stage 3 — Regulatory reasoning (the core)
Determine the applicable pathway:
- County attainment/nonattainment status per pollutant (EPA Green Book)
- Is the source category on the List of 28? → 100 tpy vs 250 tpy threshold
- Potential-to-emit estimate from MW × fuel × heat rate × run hours
- PSD increment already consumed by nearby major sources (NEI + Title V records)
- Class I areas within range → AQRV/visibility analysis trigger
- State-specific overlays: state toxics programs, state BACT, state modeling rules
- **Output:** permit-by-rule | minor NSR | synthetic minor | major PSD | major NA NSR,
  plus a timeline range for that specific state agency

### Stage 4 — Non-air blockers
- County ordinances, moratoria, zoning posture, board voting history
- Local news signals
- Federal court dockets — has this developer or this county seen litigation
- Gas pipeline reachability (the New Mexico failure mode)
- Interconnection queue position if grid-tied

### Stage 5 — Satellite verification
Is there a hole in the ground? Compare announced timeline vs observable
construction progress. This is what separates a press release from concrete.

### Stage 6 — ACT (this is what wins the "agent" criterion)
Two search loops:
1. **Alternate site search** — run Mireye across candidate parcels in an expanding
   radius, find where the same config flips to a faster pathway.
   *Output: "Move 22 miles to [parcel]. Minor NSR instead of PSD. Save ~18 months."*
2. **Config search** — test design changes at the current parcel that flip the
   pathway: run-hour caps for synthetic minor, Tier 4 engines, SCR, split the plant
   below thresholds.

### Stage 7 — Output
- **One number per project:** probability it energizes on the announced schedule
- Every physical fact carrying its Mireye `source`, `fetched` timestamp, and `confidence`
- The national artifact: **every US county scored on days-until-legal-power for 500 MW**

---

## 3. Data sources — MIREYE-MAX POLICY

> **Rule for this build: if Mireye can answer it, Mireye answers it. Do not write an
> ingest pipeline for anything Mireye already indexes. Do not build routing, distance
> or geocoding yourself. Every hour spent wiring a third-party API is an hour not
> spent on the agent loop, which is what's actually being judged.**

There is one constraint to respect. Judging criterion 1 says *"Mireye is one input —
the interesting part is what sits next to it."* So the answer is not 100% Mireye.
It is: **Mireye for everything physical, plus exactly two external sources chosen for
maximum weirdness per hour of work.**

### Layer 1 — Mireye does all of this (no external work)

| Question | Endpoint | Notes |
|---|---|---|
| Address/coordinate → canonical parcel | `/v1/geocode` | Take the typed refusal on low confidence; don't guess |
| County, tract, jurisdiction, timezone, elevation, flood status in one call | `/v1/lookup` | Replaces four separate lookups |
| Parcel boundary, acreage, land use, assessed value | `/v1/fetch` — `boundaries`, `building_lookup` | |
| Terrain, slope, aspect, elevation (drives dispersion modeling) | `/v1/fetch` — `terrain` | |
| Land cover, canopy, NDVI | `/v1/fetch` — `land_cover` | |
| **Nearest transmission line + voltage, substation, power plant, gas pipeline, utility service territory** | `/v1/fetch` — `utilities` (18), `grid_interconnect` (29) | **This is the whole power layer. Do not go build EIA/HIFLD ingest.** |
| Full site screen — 90 fields | `/v1/fetch` — `data_center_siting` | Their biggest preset. Use it. |
| Broad site suitability — 54 fields | `/v1/fetch` — `site_selection` | |
| Flood, wetlands, wildfire, natural hazards | `/v1/fetch` — `flood_risk`, `natural_hazard`, `wildfire_underwrite` | |
| **Distance to airports** (laser/airspace and stack-height checks), rail, ports, urban areas | `/v1/proximity` — nearest-by-road | **Do not build routing.** |
| Drive-time screening, labor sheds, population reach | `/v1/proximity` | Gives you "who lives downwind" for free |
| Schools, hospitals, residential POI near the parcel | `/v1/fetch` — `points_of_interest` (23) | Opposition-risk inputs |
| Anything exploratory you haven't scripted yet | `/v1/ask` | One call resolves an address, fetches fields and measures distances, and returns the plan it ran so you can replay it. Use this for the messy edges instead of writing glue. |

Mireye's own cited sources already include **EPA, FEMA, USGS, NOAA, USDA, EIA, FCC,
Census, NREL, USFWS, USFS, FHWA, FAA, BTS, USACE, BLM, HUD, Overture, Regrid,
Sentinel-2.** A large fraction of what looked like "13 external sources" in the first
draft is already inside their API. Check the field catalog before you build anything.

### Layer 2 — `/v1/field-requests` instead of a new pipeline

**This is the highest-leverage endpoint in the whole product, and almost nobody in
this contest will use it.**

When Mireye doesn't have a field, do not go build an ingest for it. Send a field
request. You get one of three outcomes, and all three are good for you:

1. **It exists** → you get the field plus a cited sample immediately, and you saved a day.
2. **Near miss** → you get the closest thing, accept or reject.
3. **Genuine gap** → one build is queued with a `request_id` you can poll, and you
   have documented a real hole in their catalog.

Fields worth requesting for this build:
- County attainment / nonattainment status by pollutant
- Distance to nearest Class I area (pure geometry over public federal boundaries)
- Background ambient PM2.5 / NO2 concentration at a coordinate
- Count and permitted emissions of major stationary sources within X km

Every one is a legitimate physical-world field. Filming this in the demo is worth
more than any external integration you could ship in the same time.

### Layer 3 — the only two external sources you build

Chosen because each is **one file or one endpoint**, zero infrastructure, and each is
literally named in their judging criterion.

| Source | What it answers | Work required | Why this one |
|---|---|---|---|
| **EPA Green Book** | Is this county in nonattainment, for which pollutant | **One CSV download.** No API, no key, no scraper. | "Permit databases" — criterion 1, example 2. It is the single fact that flips the whole pathway. |
| **CourtListener / RECAP** | Has this developer, county or facility been sued | **One free API key, one search endpoint.** | "Court filings" — criterion 1, example 1. The xAI/NAACP suit is the live case. |

That's it. Two sources, maybe three hours of work combined, and you have hit two of
the three examples they list.

### Cut list — do NOT build these

- ~~EIA / HIFLD gas pipelines~~ → `/v1/fetch` utilities preset has pipeline distance
- ~~Custom routing / distance math~~ → `/v1/proximity`
- ~~FERC queue scraper~~ → grid_interconnect preset, or field-request it
- ~~NPS/USFS Class I shapefiles~~ → field-request it
- ~~County ordinance scrapers~~ → hardcode 20 counties from the public trackers by
  hand into a JSON file. Faster, more accurate, and nobody can tell in a demo.
- ~~Satellite imagery pipeline~~ → if time is short, use manual screenshots in the
  video instead of an automated ingest. The *insight* (60% of announced capacity has
  no hole in the ground) lands the same either way.

### Credit burn — you wanted a reason to email the founders

The national sweep is what consumes credits, and Mireye-maxing makes that bigger, not
smaller. Rough budget:

| Run | Calls |
|---|---|
| Per-project deep screen (fetch presets + proximity + ask) | ~15–40 |
| Alternate-site search, 25 candidate parcels per failed site | ~400–1,000 |
| 3,000 tracked projects, single pass | ~50k–100k |
| National county sweep (~3,140 counties) for the map | ~30k–60k |

Email **founders@mireye.com** on day one with those numbers. It is a true statement,
it is exactly what they invited, and it opens a direct line to the people deciding
the internship.

---

## 4. Who buys — in detail

### Buyer 1: Hedge funds and asset managers *(fastest cheque)*

**Who exactly:** funds with positions in GE Vernova, Vertiv, Bloom Energy,
Constellation, Talen, Vistra, Equinix, Digital Realty, and the utilities carrying
data center load growth.

**Why they pay:** a fund manager said it in print in July 2026 —

> "Announced capital is not deliverable capacity. Those are different things, and
> the market keeps pricing them the same."

Hedge funds have already made AI data centers a primary battleground because
narrative momentum keeps colliding with operational constraints
([HedgeCo, May 2026](https://hedgeco.net/news/05/2026/ai-data-centers-become-the-new-hedge-fund-battleground.html)).

**Deal shape:** alt-data subscription, **$50k–$500k/year**, dozens of potential
buyers, 2–6 week sales cycle, no procurement gauntlet.

**What they buy:** a project-level feed with a deliverability score, updated weekly,
plus alerts when a project's score moves.

### Buyer 2: Data center and power developers *(largest single contract)*

**Who exactly:** hyperscaler site-selection teams, colo developers (QTS, Vantage,
CyrusOne, Aligned), behind-the-meter power developers, turbine lessors.

**Why they pay:** one wrong site is tens of millions in options, engineering and
legal, plus 18–36 months. Nebius is the live example under a $17.4B deal.

**Deal shape:** **$250k–$1M/year** enterprise, or **$10–25k per site report** as a
services wedge (this is the realistic revenue path in months, not years).

### Buyer 3: Air permitting consultancies *(channel)*

**Who exactly:** Trinity Consultants, ERM, Onterris, regional air-quality firms.

**Why they pay:** they do this analysis manually today. They'd rather buy the screen
and keep the billable interpretation — and a licensed professional still signs the
opinion, which is a moat, not a problem.

**Deal shape:** per-seat or per-screen licensing.

### Buyer 4: Infrastructure lenders and funds

Underwriting these projects against announced energization dates. Same feed,
diligence use case.

### Honest note on competition

Sightline Climate, Data Center Watch (10a Labs), BloombergNEF and JLL already sell
data center pipeline intelligence. **They track. They don't compute the permit
pathway, and they don't search for a better parcel.** State that differentiation
explicitly rather than pretending the space is empty — the judges will know.

---

## 5. Rubric mapping

| Criterion | How Deliverable answers it |
|---|---|
| **Must be an agent — reason, decide, act** | Reasons through a legal decision tree (source category → threshold → increment → pathway). Decides a pathway and timeline. **Acts** by searching outward across parcels and configs for a better answer. Most entries will reason and stop at a report. |
| **What did you combine us with?** | Court filings, permit databases, satellite imagery — the literal first three examples on their list — plus 10 more. |
| **Is it a real problem?** | Nebius (400 MW, $17.4B deal), New Mexico Stargate pipeline, $130B blocked in Q1 2026. Named companies, this year. |
| **Who writes the cheque?** | Four buyer types with budgets, two of them losing money right now. Not "developers might like this." |
| **Not in their marketing deck** | Their deck screens whether a site is *good* (slope, flood, 345 kV, queue). This screens whether they'll *let you switch it on* — the layer after their API already said yes. **Lead with this sentence.** |

---

## 6. Build plan — 4 days

### Wednesday night (today)
- Sign up with code `BUILD`. Wire the MCP server to Claude.
- Email **founders@mireye.com**: national county sweep, expect ~200k calls.
- Hardcode the decision table: List of 28, PSD thresholds, pathway logic.
- Repo skeleton + README stub.

### Thursday — Mireye first, then the two externals
- **Morning: read the full Mireye field catalog.** Every hour here saves three later.
  List every field you need and mark it Mireye / field-request / external.
- Fire all four `/v1/field-requests` (§3 Layer 2). They queue while you build.
- Wrap the Mireye client: `fetch` presets, `proximity`, `lookup`, `ask`. Cache
  responses to SQLite so re-runs are free.
- **Only then:** EPA Green Book CSV (one download) + CourtListener (one key).
  Target: both done inside three hours.
- Emissions estimator: MW × fuel × heat rate × hours → tons/year per pollutant.
  Pure math, no external data.

### Friday — the agent
- Real tool-calling loop (Claude + Mireye MCP), not `if` statements.
- Pathway decision engine.
- Mireye query planner — pick presets by what the pathway question needs, not a
  fixed list. **The planner choosing different Mireye calls based on the generation
  config is itself the reasoning the judges are looking for.**
- **Alternate-site search loop** — this is the differentiator, don't cut it. It's
  also your biggest Mireye consumer.
- Carry `source` / `fetched` / `confidence` all the way to the output.

### Saturday — sweep + backtest
- National county sweep for the map. **Burn the credits.**
- Backtest: reconstruct pre-failure data state, show it flagging Nebius NJ and the
  New Mexico Stargate site.
- **Be honest in the video that n=2 and it is a demonstration, not a rigorous
  out-of-sample test.** A judge who catches inflation discounts everything else.

### Sunday — ship
- One-pager, 2-min video, README, feedback field.
- Submit **Monday morning**, not Monday night.

### Repo structure

```
deliverable/
  README.md
  agent/
    planner.py          # tool-calling loop
    pathway.py          # permit decision engine
    emissions.py        # PTE estimator
    search.py           # alternate site + config search
  providers/
    base.py             # PhysicalFactsProvider interface  <-- makes global a data problem
    mireye.py           # US implementation — presets, proximity, ask, field-requests
  ingest/
    greenbook.py        # one CSV
    dockets.py          # one CourtListener endpoint
    counties.json       # 20 hand-entered moratorium records, not a scraper
  sweep/
    counties.py         # national scoring
    map.py
  backtest/
    cases.py            # Nebius NJ, NM Stargate
  data/cache.sqlite
```

**Note the `providers/` interface.** It costs you 20 lines and makes the global
roadmap credible instead of aspirational.

---

## 7. Demo video — 2 minutes

| Time | Content |
|---|---|
| 0:00–0:15 | The Musk quote on screen. "The bottleneck isn't chips or money." |
| 0:15–0:30 | 16 GW announced vs ~5 GW real. $130B blocked in Q1. 2.2% of BTM generation running. |
| 0:30–1:10 | **One live run.** Feed it a real site. Watch it reason: source category → threshold → increment consumed → Class I trigger → *major PSD, ~26 months*. Show the citations. |
| 1:10–1:35 | **The act.** It searches outward and returns an alternate parcel: minor NSR, ~5 months. Show the delta. |
| 1:35–1:50 | Backtest: flags Nebius NJ and NM Stargate. State the n=2 caveat out loud. |
| 1:50–2:00 | The county map. Hold on it. End. |

---

## 8. Three moves aimed at the internship

1. **Use `/v1/field-requests` on camera.** Request something they don't have —
   ambient PM2.5 background concentration, or nearest Class I area distance.
   Whatever comes back (hit, near-miss, or queued build with a `request_id`) is the
   most interesting 10 seconds in your demo, and almost nobody else will touch it.
2. **Make your COGS their revenue.** One line in the one-pager: *"Each project screen
   costs N Mireye calls. At 3,000 tracked projects re-swept weekly, that's X calls/month."*
3. **The feedback field is the interview.** It's required, on a form read by five
   people who'd be your coworkers. Draft below.

### Feedback field draft (edit to be true to your experience)

> Built a permit-pathway agent for data center power projects on Mireye.
>
> **What worked:** `/v1/proximity` nearest-by-road over curated infrastructure sets
> saved me from building my own routing layer. Typed refusals on low-confidence
> geocodes were the right call — I'd rather get a refusal than a centroid.
> Carrying `source` / `fetched` / `confidence` through to my output is what makes
> the result defensible to a permitting engineer.
>
> **Where I lost time:** [be specific — a doc gap, an unclear field name, a preset
> that didn't include what I expected].
>
> **What I needed and couldn't get:** [the field you requested via `/v1/field-requests`],
> and nearest-Class-I-area distance. Both are pure geometry over public federal
> boundaries — high leverage for anyone doing air permitting.
>
> **One concrete API change:** [e.g. let `/v1/fetch` accept a bounding box or radius
> and return a grid, so alternate-site search is one call instead of N].
>
> **The thing I'd want most:** coverage outside the US. My product's roadmap is
> India, where announced 6–8 GW by 2030 is realistically 3.4–3.6 GW — the same
> announced-vs-deliverable gap. I built a provider interface so Mireye is the US
> implementation. I'd be a customer the day you go international.

---

## 9. Marketing / LARP

### Bio line
> Announced ≠ deliverable. Building the credit rating for infrastructure.

### X launch post

> Elon told Dwarkesh the AI bottleneck isn't chips or money. It's permits.
>
> "You have to get permits. Try getting the permits for that. See what happens."
>
> So I checked.
>
> 16 GW of US data centers announced for 2026. ~5 GW actually on the ground.
> $130B in projects blocked in Q1 alone. 833 opposition groups across 49 states.
> Of 90 GW of announced on-site power generation, 2.2% is running.
>
> The market prices announced capacity as if it's deliverable capacity. It isn't.
>
> So I built Deliverable — an agent that tells you which projects are real.
>
> It works out which air permit a plant needs at that exact parcel, checks the
> county's posture, pulls the court dockets, and looks at satellite imagery for
> whether there's a hole in the ground yet. Every physical fact cited to its federal
> source with a timestamp.
>
> Then it does the useful part: when a site fails, it searches outward and finds one
> nearby that doesn't. "Move 22 miles. Save 18 months."
>
> Built on @mireye_ for the physical layer.
>
> Same story in India — Axis Capital says announced 6-8 GW by 2030 is realistically
> 3.4-3.6. Announced ≠ deliverable is a global condition. US first.
>
> [county map]

### LinkedIn version
Same spine. Lead with **16 GW announced vs ~5 GW real** instead of the Musk quote
(move Musk to paragraph two). End on the buyer rather than the map. Add one line on
what you learned building it.

### Thread follow-ups (post over the week)
1. The two-county comparison table — same plant, 4 months vs 3 years.
2. The Jan 2026 EPA turbine rule and why the xAI fast path closed.
3. The county map, zoomed into one state, with the top 5 and bottom 5 counties.
4. The alternate-site search in action — one before/after.

### Rules for the LARP
- Every number above is sourced. **Keep it that way.** Link the sources.
- Don't claim revenue, customers or a raise you don't have.
- Don't claim the backtest proves more than n=2 does.
- "Built on Mireye" in every post. It costs nothing and it's the right thing to do.

---

## 10. Global / India — roadmap only, not in the demo

**Hard constraint: Mireye is US-only.** An India build can't run on their API, so a
global demo is a demo where Mireye barely appears — which fails judging criterion one.

**Put India in the one-pager as one line, and in the feedback field as a request.**

Evidence that the thesis is global:

- Axis Capital: India's announced targets of **6–8 GW by 2030 "look inflated"**;
  realistic estimate **3.4–3.6 GW** operational by mid-2030. Gensets from three
  global brands booked out two years; **power connection delays ~18 months**.
  ([report summary](https://www.newkerala.com/news/a/supply-chain-constraints-may-cap-indias-data-centre-capacity-773.htm))
- An operator, on the record: *"The 28-36 month timeline is the real story here. In
  Singapore or parts of the US, you can get a facility up in 12-18 months. We're
  doing vertical builds because land is expensive and permits are a nightmare."*
- **10.5 GW sits in the land-banking stage** in India — announced, not broken ground.
  ([ICICI Securities via Compute Forecast](https://www.computeforecast.com/articles-post/india-data-center-hub-investment-outlook/))
- Operational capacity: ~1.8 GW as of H1 2026.

The `providers/` interface is what makes this credible: **the agent is portable, the
substrate isn't yet.**

---

## 11. Honest risks — know these before someone asks

1. **Incumbents exist.** Sightline, Data Center Watch, BNEF, JLL sell pipeline
   intelligence. Your wedge is the *pathway computation* and the *alternate-site
   search*, not the tracking. Say so first.
2. **Alt data demands a point-in-time panel.** Funds want years of history to
   backtest. Building that is a multi-year data engineering problem and it's the
   main reason alt-data startups die. Acknowledge it; don't pretend a 4-day build
   is a panel.
3. **You can't sign the opinion.** A licensed professional stamps permitting
   analysis and carries the liability. Position as the engine underneath, sold to
   the people who do sign. That's a moat, framed correctly.
4. **The backtest is n=2.** Say it out loud in the video.
5. **Realistic business ceiling** is a $5–30M ARR data business after a grind, not a
   rocket. The fastest real revenue path is **per-site reports at $10–25k**, not SaaS.
   Build this to win the contest and get the interview; decide about the company later.

---

## 12. Agent guardrails — no autonomous actions

**Hard rule for this build: the agent proposes, a human disposes.**

The agent must never take an irreversible or external-facing action on its own. It
reasons, decides, searches, and drafts. A human sends.

**The agent must NOT:**
- Submit the challenge form, or any form
- Send email to anyone, including founders@mireye.com
- Post to X, LinkedIn or anywhere else
- Contact a county, an agency, a developer or a vendor
- File a records request, comment, or application
- Commit or push to the repo without review
- Spend credits outside the budget in §3 without a human saying go

**The agent MAY:**
- Read public data and call Mireye
- Reason, score, rank, and search for alternate sites
- Draft the outreach email, the memo, the records request — and hand it over unsent
- Write output files to disk for a human to review

**Why this is in the brief and not just a preference:** "acts" in the judging
criterion means acts *on the analysis* — searching parcels, testing configurations,
re-planning queries. It does not mean acts *on the world* without supervision. An
agent that emails a county on its own is a liability, not a feature. Say this
explicitly in the README; it reads as judgment, which is what a first-prize judge is
actually scoring.

Implement it as a real boundary, not a prompt instruction: no email client, no HTTP
POST to third parties, no form automation in the codebase at all. Drafts land in
`outputs/drafts/` as plain files.

---

## 13. README — write it like a person

The repo is read by five people deciding whether they want you on the team. Docs that
read like generated marketing copy actively hurt you. Aim for the tone of a good
internal engineering doc: short, specific, slightly blunt.

**Do:**
- Open with what it does in two sentences and one concrete example with real numbers
- Say what you actually built vs. what's stubbed
- Use first person where it's natural ("I hardcoded 20 counties by hand because a
  scraper wasn't worth six hours")
- Give exact setup steps that work on a clean machine
- Name the limitations plainly — the n=2 backtest, the hardcoded counties, the state
  coverage gaps
- Keep it under two screens. Link deeper docs if you need them.

**Don't:**
- Marketing voice. No "revolutionary", "seamless", "comprehensive", "robust",
  "cutting-edge", "leverage", "empower", "unlock", "game-changing"
- Emoji section headers, badge walls, or a table of contents for a 200-line README
- Triads of adjectives ("fast, reliable, and scalable")
- "In today's rapidly evolving landscape..." openers
- Heavy em-dash cadence and long balanced clauses — that's the most recognisable
  generated-text tell. Prefer short sentences and periods.
- Claiming features you didn't finish

**Structure that works:**

```markdown
# Deliverable

Tells you whether a data center power project can legally get built where it's
announced — and if not, where nearby it could.

Example: a 500 MW gas plant at [address] needs a major PSD permit. ~26 months.
Move 22 miles to [county] and the same plant is minor NSR. ~5 months.

## Why
16 GW of US data centers were announced for 2026. About 5 GW is actually on the
ground. Permits are a big part of the gap. [source]

## How it works
1. Resolve the parcel (Mireye)
2. Pull physical facts and infrastructure proximity (Mireye)
3. Work out the air permit pathway
4. Check county posture and litigation
5. If it fails, search nearby parcels for one that doesn't

## Setup
[exact commands]

## What's real and what isn't
- County moratorium data: 20 counties, entered by hand
- Backtest: 2 cases. Demonstration, not a rigorous out-of-sample test.
- State overlays: 6 states modelled properly, rest fall back to federal defaults
- The agent drafts outreach but never sends anything

## Notes on the Mireye API
[2-3 honest observations — this is also your feedback field material]
```

Write the "what's real and what isn't" section first, before you're tempted to
overclaim. It's the section that will make them trust the rest.

---

## 14. Submission checklist

- [ ] Git repo — clean README (§13), runnable, `.env.example`, no keys committed
- [ ] No email/form/post automation anywhere in the codebase (§12)
- [ ] One-pager (PDF or Notion) — problem, agent, sources, buyers, rubric, roadmap
- [ ] 2-minute demo video — script in §7
- [ ] Feedback for Mireye — draft in §8, make it real
- [ ] Form: name, email, repo link, one-pager link, video link — **you fill this in,
      not the agent**
- [ ] Email founders@mireye.com about credits — **you send it, not the agent**
- [ ] **Submit Monday morning**

---

*Deadline: 10 August 2026. Winners announced 15 August 2026.*
