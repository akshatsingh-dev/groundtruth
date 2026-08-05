# Build log — what is being built, and how

**This is the master document. It gets updated as work lands.** Read it top to
bottom once, then check the "Session log" at the bottom for what changed since.

Everything lives in `/Users/akshatsingh/Desktop/Akshat/Projects/deliverable`.
Pushed to `github.com/akshatsingh-dev/deliverable` (private for now — flip it
public before you submit the form, the form asks for a repo link).

---

## Part 1 — What we are actually building, in plain words

Someone announces a $5 billion data center. Chips are ordered. Money is raised. A
date is announced: "energized Q3 2027."

Then it does not happen on time. The reason is almost never chips or money. It is
power, and specifically the **legal permission** to make power.

If you want to build your own gas plant on site — which almost everyone now does,
because the grid queue is years long — you need an air permit. And here is the
fact the whole product turns on:

> **Which permit you need is decided by where the land is, not by what you are
> building.**

The identical 500 MW plant, on two parcels forty miles apart:

| | County A | County B |
|---|---|---|
| Air quality status | Clean ("attainment") | Dirty ("nonattainment") |
| Pollution budget left | Available | Already used up by three existing plants |
| Protected wilderness nearby | No | Yes, 60 km upwind |
| **Permit you need** | Minor permit | Major permit, full modeling, public comment |
| **Timeline** | 4–6 months | 2–3 years, and it might just fail |

Nobody screens for this before buying the land. They buy for power, fiber and
price, then find out. That is the money on the table.

**Deliverable** takes a project — address, megawatts, what kind of engine, target
date — and tells you which permit it needs and roughly how long that takes. Then
it does the part that makes it an agent rather than a report: when the answer is
bad, it goes and **searches** for a parcel nearby where the same plant is a fast
permit, and for a design change at the current parcel that flips the answer.

The output is one number per project: probability it energizes on the announced
schedule.

---

## Part 2 — The shape of the thing

Six pieces. Three are built, three are being built right now.

```
     "1234 Example Rd, Loudoun County VA, 500 MW, combined cycle, Q3 2027"
                                  |
                                  v
   [ 1. PROVIDER ]  Mireye.  Where is this exactly? What is the ground like?
                    Parcel, county, terrain, how far to a gas pipeline,
                    how far to transmission, who lives within a kilometre.
                    Every value arrives with its source and a timestamp.
                                  |
                                  v
   [ 2. EMISSIONS ] How many tons of pollution per year can this plant
                    physically emit? Pure arithmetic, no data needed.
                                  |
                                  v
   [ 3. PATHWAY ]   Which permit does that trigger, in THIS county,
                    under THIS state's agency? How many months?
                                  |
                                  v
   [ 4. EXTERNAL ]  Is the county in nonattainment? (EPA Green Book)
                    Has anyone sued here? (CourtListener)
                    Is there a moratorium? (hand-entered county file)
                                  |
                                  v
   [ 5. SEARCH ]    The answer was bad. Now go find a better one.
                    (a) 25 candidate parcels in a ring outward
                    (b) design changes at this parcel
                                  |
                                  v
   [ 6. REPORT ]    One number, every fact cited, the alternate site,
                    the delta: "Move 22 miles. Save 18 months."
```

And separately, the national artifact: **every US county scored on days-until-
legal-power for a 500 MW plant.** That is the map the demo video ends on.

---

## Part 3 — Each piece, technically, but readable

### 1. The provider — `providers/base.py`, `providers/mireye.py`

`base.py` defines an **interface**: a list of things the agent is allowed to ask
about the physical world (`geocode`, `lookup`, `fetch`, `proximity`, `ask`), with
no mention of Mireye anywhere in it. `mireye.py` is the US implementation of that
interface.

Why bother with the indirection? Two reasons, and one of them is a judging point.
Mireye is US-only. The thesis — announced capacity is not deliverable capacity —
is global; India announced 6–8 GW by 2030 and will realistically deliver 3.4–3.6.
The interface means going international is a data problem, not a rewrite. It cost
about twenty lines and it makes the roadmap credible instead of aspirational.

Two design decisions in here worth being able to defend out loud:

**Every fact carries its provenance.** Not the number, the number *plus* where it
came from plus when it was fetched plus how confident the source is. There is a
`Fact` class and everything is wrapped in it. A permitting engineer will not act
on a number they cannot trace, so an untraceable number is worthless here.

**Low-confidence geocodes raise an error instead of guessing.** If you ask for an
address and the geocoder is only 60% sure, we refuse. Most tools quietly hand back
the county centroid, which is often the county seat, twenty miles from the actual
parcel — and then you compute a permit answer for the wrong county. A refusal
costs a retry. A wrong parcel costs a land option.

There is also a `NullProvider` that has no data and refuses everything. It exists
so the whole repo runs with zero API keys, and so that any code path which quietly
produces a plausible-looking answer against it is exposed as a code path that
would fabricate against a real provider.

### 2. Emissions — `agent/emissions.py`

Given a plant config, how many tons per year of each pollutant. Pure arithmetic.
No network, no data source, runs instantly.

**The chain:** megawatts → heat rate → fuel burned → tons of pollution.

```
heat input (MMBtu/hr) = MW × 1000 × heat_rate (Btu/kWh) ÷ 1,000,000
tons/year             = emission_factor (lb/MMBtu) × heat input × hours ÷ 2000
```

Three things in here that are not obvious and that you should be able to say:

**(a) Emissions scale with fuel burned, not with megawatts.** "Heat rate" is how
much fuel it takes to make a kilowatt-hour. A combined-cycle plant (6,800 Btu/kWh)
burns about two thirds what a simple-cycle plant (10,500 Btu/kWh) burns for the
same output, because it catches the waste heat and runs a second turbine off it.
Same 500 MW, one third less pollution, before you install a single control device.
This is why a **design change** can move a project across a legal threshold
without changing its size — which is what the config search exploits.

**(b) The 8,760 hour rule.** This is the single most counter-intuitive thing in
the product. "Potential to emit" is the maximum the plant *could* emit running
full time — 8,760 hours, every hour of the year. Telling the agency "we only plan
to run it 2,000 hours" changes nothing. The only thing that lowers your number is
accepting a **federally enforceable permit condition** that legally caps your run
hours, with recordkeeping and penalties. Do that and you are a "synthetic minor."

The code enforces this: `run_hours` below 8,760 is ignored unless you also set
`enforceable_limit=True`. There is a test for it, because if that regresses the
tool tells developers their plant is minor when the agency will call it major,
which is the most expensive way this thing could be wrong.

And the tool is honest about the cost. For a 500 MW combined-cycle plant, holding
CO under 100 tons would need a cap of about **646 hours a year — 7% availability.**
The code says so in words: *"That is not a data center power plant, it is a
peaker."* A tool that reported "synthetic minor, 8 months!" there would be lying.

**(c) The emission factors are AP-42**, EPA's published compilation, and each set
carries its table reference in the code. Controls are modelled as reductions:
SCR cuts NOx 90%, dry low-NOx combustors 69%, oxidation catalyst cuts CO 90%.
Tier 4 diesel is different — it is certified on engine *output* in grams per
kilowatt-hour, not on fuel input, so it replaces the factors outright rather than
discounting them.

**A real finding from the tests:** on a 15 MW turbine with DLN and SCR fitted, the
binding pollutant is not NOx. It is **CO, at 57 tons a year**, because neither of
those controls touches CO. Anyone screening on NOx alone misses it. Adding an
oxidation catalyst drops it under 10. That is a genuine, specific, checkable thing
the config search finds, and it is a good thing to show a judge.

### 3. Pathway — `agent/pathway.py`

The core. Takes the tons-per-year plus the regulatory facts about the parcel, and
runs the decision tree an air permitting engineer runs, in their order.

**Step 1 — the List of 28.** There are 28 named industrial categories in the
regulation (40 CFR 52.21). If you are on that list, you become a "major source" at
**100 tons a year**. If you are not, at **250**.

Data centers are not on the list. But *"fossil fuel-fired steam electric plants of
more than 250 million Btu per hour"* is. A **combined-cycle** plant has a steam
cycle, so it is on the list. A **simple-cycle** turbine has no steam cycle, so it
is not. Same site, same fuel, and the threshold moves by 150 tons because of which
machine you picked. Very few people screening these sites know that.

**Step 2 — is the county clean or dirty?** For each pollutant, the county is either
in "attainment" (meets federal air quality standards) or "nonattainment." Clean
county → the PSD program. Dirty county → nonattainment NSR, which is much worse:
the threshold drops with how bad the air is (moderate 100 tons, serious 50, severe
25, extreme 10), the control standard becomes LAER which has no cost defense, and
you must buy **offsets** — 1.1 to 1.5 tons of verified reductions from an existing
source for every ton you emit. In a severe area those credits are often
unavailable at any price, which is a hard stop, not a delay. The code flags that.

**Step 3 — compare and decide.** Over the threshold → major review. Under it only
because of a permit condition → synthetic minor. Comfortably under → minor NSR, or
permit-by-rule in states that have one (Texas does; that is why Texas is fast).

**Step 4 — the overlays that add time regardless.** Each one is a `Trigger` object
with a name, whether it fired, a plain-English detail, a legal citation, and how
many months it adds:

- **Class I areas.** Protected wilderness and national parks. Within 100 km you
  must notify the Federal Land Manager, and they can object on visibility grounds
  even when your modeling passes.
- **PSD increment.** The pollution budget for an area is finite and *shared*. If
  the plants already there consumed 90% of it, there is nothing left for you to
  model into. At 95%+ the code calls it a hard stop: possibly un-permittable at
  any timeline.
- **Title V**, the operating permit, over 100 tons or 10 tons of a single air toxic.
- **NSPS Subpart KKKK** — and specifically the EPA rule published 15 January 2026
  (91 Fed. Reg. 1910) that closed the "nonroad engine" reading. That loophole is
  what let xAI stand up ~100,000 GPUs in about 19 days. It is closed. If our tool
  ever stops firing that trigger it is quietly telling people a fast path exists,
  so there is a test pinning it.
- **State overlays.** Eight states modelled properly with a timeline multiplier
  and a note: Texas 0.75× (genuinely fast, permits by rule), Virginia 1.25× (DEQ
  has approved exactly one of these), New Jersey 1.6×. Every other state falls back
  to the federal default and the code says so out loud rather than pretending.
- **New Jersey stacks three at once** — Ozone Transport Region, a state toxics
  program, and an environmental justice law that lets the agency deny a permit
  outright in an overburdened community regardless of the modeling. That is the
  Nebius failure mode and there is a test for it.
- **Non-air blockers:** county moratorium (a clean air pathway does not clear a
  moratorium — separate test), hostile zoning, litigation from CourtListener, and
  **gas pipeline reachability**. That last one is New Mexico: the plant was
  permittable, the pipeline that fed it was not. Over 25 km away and the code calls
  it a hard stop, because a lateral that long is its own permitting project with
  its own easements and its own opposition.

**Output:** the pathway, a months range (low / likely / high), every trigger that
fired with its citation, which pollutant is controlling and against which
threshold, what needs BACT, how many tons of offsets, and any hard stops.

### 4. External data — `ingest/`

The judging criterion is "what did you combine us with?" and their own first two
examples are **court filings** and **permit databases**. So that is exactly what we
built, and nothing else:

- `greenbook.py` — EPA Green Book nonattainment designations. One CSV download, no
  API, no key. It is the single fact that flips the whole pathway.
- `dockets.py` — CourtListener / RECAP. One free key. Has this developer or this
  county been sued. The live case is NAACP/SELC/Earthjustice v. xAI.
- `counties.json` — 20+ counties with moratoria and zoning posture, **entered by
  hand** from public trackers. Deliberately not a scraper. Faster, more accurate,
  and nobody can tell in a demo. Say this out loud rather than hiding it; it reads
  as judgment.

Everything else physical comes from Mireye. We did not build EIA pipeline ingest,
we did not build routing, we did not build a FERC queue scraper. That is the
policy: if Mireye can answer it, Mireye answers it.

### 5. The agent loop — `agent/planner.py`, `agent/search.py`

This is the piece the contest is actually judged on. The rule is: *"we want agents
— things that reason, decide and act. Not a website with a map on it."*

**The loop** is a real Anthropic tool-calling loop, not a chain of if-statements.
Claude gets a set of tools (resolve a site, pull physical facts, get proximity,
estimate emissions, determine pathway, test a config, search alternate sites, ask
Mireye an open question, request a field Mireye does not have) and decides which
to call and in what order.

The important part, and the thing to point at in the video: **it picks different
Mireye calls depending on the config in front of it.** A combined-cycle plant in
hilly terrain needs terrain and land cover, because those drive dispersion
modeling. A fuel cell config does not, so it does not spend the calls. That
adaptivity *is* the reasoning the judges are looking for, and the trace shows it.

**The search — this is "act".** Two loops:

- *Alternate site*: generate candidate parcels in an expanding ring, 15 km out to
  120 km, resolve each one, run the full pathway on each, rank them, and return
  the delta. *"Move 22 miles to this parcel. Minor NSR instead of major PSD. Save
  about 18 months."* It crosses county and state lines, because that is usually
  where the answer flips. It is also by far the biggest consumer of Mireye credits,
  which is deliberate.
- *Config*: test design changes at the current parcel. Add an oxidation catalyst.
  Switch simple-cycle to combined-cycle. Accept a run-hour cap. Each one reported
  with its honest cost.

**And the guardrail, which is a scored feature and not a limitation.** The agent
never takes an action on the world. No email client, no HTTP POST to third parties,
no form automation anywhere in the codebase. Drafts land in `outputs/drafts/` as
plain files for you to send. You fill in the Google Form. You send the email to
founders@mireye.com.

The reasoning, which is worth saying in the README and out loud: *"acts" in the
judging criterion means acts on the analysis — searching parcels, testing configs,
re-planning queries. It does not mean acts on the world without supervision. An
agent that emails a county planning office on its own is a liability, not a
feature.*

### 6. The sweep — `sweep/counties.py`, `sweep/map.py`

Run the reference config (500 MW combined cycle, DLN + SCR + oxidation catalyst)
against all ~3,140 US counties and score each on days-until-legal-power. Output a
single self-contained HTML map, no CDN, opens offline.

**The caveat you must say out loud in the video:** the county map is a *screening*
layer. It uses county-level facts only. It cannot see parcel-level increment
consumption, terrain, or pipeline distance. The parcel run is the real answer. Every
record in the data carries `resolution: "county"` for exactly this reason.

---

## Part 4 — How to run it

```bash
cd /Users/akshatsingh/Desktop/Akshat/Projects/deliverable
python3 -m pytest -q            # 47 tests, no keys needed
```

Once the Mireye key arrives:

```bash
cp .env.example .env            # fill in MIREYE_API_KEY, ANTHROPIC_API_KEY
```

More commands land here as the pieces do.

---

## Part 5 — What is honest and what is soft

Write this section before you are tempted to overclaim. It is the part that makes
a judge trust the rest.

- **The backtest is n=2.** Nebius NJ and the New Mexico Stargate site. It is a
  demonstration, not a rigorous out-of-sample test. Say it out loud in the video.
  A real backtest needs a point-in-time panel — reconstructing what was knowable at
  each historical date across hundreds of projects — which is a multi-year data
  engineering problem and the main reason alt-data startups die.
- **County moratorium data is 20 counties entered by hand.** Not national. Not
  automatically updated.
- **Eight states are modelled properly.** The other 42 fall back to a federal
  default, and the code says so in the output rather than hiding it.
- **The timeline model is calibrated on public permit records and agency guidance,
  not on a validated statistical model.** It is a range, and it is presented as one.
- **We cannot sign the opinion.** A licensed professional stamps permitting
  analysis and carries the liability. We are the engine underneath, sold to the
  people who do sign. Framed correctly that is a moat, not a weakness.
- **Incumbents exist.** Sightline Climate, Data Center Watch, BloombergNEF and JLL
  sell data center pipeline intelligence. They **track**. They do not compute the
  permit pathway and they do not search for a better parcel. Say that first, before
  a judge says it for you.

---

## Session log

Newest at the bottom.

### Wed 5 Aug 2026 — session 1

**Done and committed:**

- Repo scaffolded at `~/Desktop/Akshat/Projects/deliverable`, pushed to
  `github.com/akshatsingh-dev/deliverable` (private).
- `CHALLENGE.md` — the contest terms, prizes, judging criteria and form fields,
  written down so nothing gets lost. `docs/build-brief.md` — the full strategy doc.
- `agent/emissions.py` — PTE estimator. AP-42 factors for 7 prime-mover/fuel
  combinations, heat-rate based, control stacking, Tier 4 output-based override,
  the 8,760 rule enforced, config validation that rejects incoherent designs
  (a lean-burn gas engine cannot burn diesel).
- `agent/pathway.py` — the decision engine. List of 28, PSD vs nonattainment NSR
  with severity-scaled thresholds and offset ratios, synthetic minor, Class I,
  increment, Title V, NSPS/NESHAP, 8 state overlays, non-air blockers, hard stops,
  and a timeline model. Every trigger carries a citation.
- `providers/base.py` — the provider interface, `Fact` provenance wrapper,
  `ResolutionError` refusal behaviour, `NullProvider` so everything runs keyless.
- `tests/` — **47 tests, all passing, no API keys required.** Including the one
  that is the product in a single test:
  `test_same_plant_different_county_different_pathway`.

**Six agents running in parallel right now:**

| Agent | Building | Files |
|---|---|---|
| 1 | Mireye API research + client + response cache | `providers/mireye.py`, `providers/cache.py`, `docs/mireye-api-notes.md` |
| 2 | EPA Green Book, CourtListener, hand-entered counties | `ingest/*` |
| 3 | The agent loop and both search loops | `agent/planner.py`, `search.py`, `report.py`, `tools.py` |
| 4 | National county sweep and the map | `sweep/*` |
| 5 | Backtest cases + fact-checking every claim in the brief | `backtest/cases.py`, `docs/evidence.md` |
| 6 | Explainer docs, demo script, objection prep | `docs/PLAIN-ENGLISH.md`, `HOW-IT-WORKS.md`, `GLOSSARY.md`, `DEMO-SCRIPT.md`, `OBJECTIONS.md` |

**Keys — resolved during the session:**

- `MIREYE_API_KEY` — **in.** Agent 1 stopped working from assumed response shapes
  and is now verifying every endpoint against the live API, capturing real JSON.
- `CLAUDE_CODE_OAUTH_TOKEN` — **in.** We went with a long-lived OAuth token from
  the existing Claude subscription rather than buying Anthropic API credits.

That second choice has a technical consequence worth understanding, because it
changed the design. The `anthropic` package's Messages API does **not** accept a
Claude Code OAuth token. Only the **Claude Agent SDK** does. So the planner now
resolves auth at startup down three paths:

1. `CLAUDE_CODE_OAUTH_TOKEN` set → Claude Agent SDK. **This is the demo path.**
2. `ANTHROPIC_API_KEY` set → `anthropic` Messages API with tool use.
3. Neither → deterministic no-LLM fallback, so the repo stays runnable for a judge
   with zero keys.

The tool definitions in `agent/tools.py` are written once and shared across paths
1 and 2. The trace states which path it took, and looks identical either way, so
the demo reproduces regardless of how someone runs it.

**Still blocked on you:**

1. **`COURTLISTENER_TOKEN`** — free, courtlistener.com. Step-by-step walkthrough is
   at `docs/courtlistener-setup.md`. The token page is
   `/profile/api-token/`. Note the limits: **5 requests/min, 50/hr, 125/day.** That
   is why the docket layer caches to disk with a 7-day TTL and the demo replays
   from cache rather than hitting the API live.
2. **Email founders@mireye.com** about credits. Draft is written and sitting at
   `outputs/drafts/founders-credits-email.md`. You send it. Not the agent.
3. **Flip the repo public** before submitting the form.

---

### Wed 5 Aug 2026 — session 1, results

Five of six agents landed. Each one found something that changed the build, which
is the point of running them in parallel rather than trusting one pass.

**The expensive correction.** The build brief said the 15 January 2026 EPA rule
(91 Fed. Reg. 1910) *closed* the nonroad-engine loophole. It does the opposite in
direction. The rule finalised a **conditional exclusion** — turbines drop out of
the "stationary combustion turbine" definition if they qualify as nonroad engines
and are certified under Title II — and that exclusion **is not operative**, because
EPA has not done the Title II rulemaking it depends on. Verified against the
Federal Register record and three independent law-firm readings; Clark Hill's own
headline says the rule *eases* permitting.

I had baked the wrong version into `agent/pathway.py`. It is fixed, and pinned by a
test that fails if the word "closed" ever comes back. The honest version is a better
story: *anyone underwriting a trailer-mounted fast path today is underwriting an
open legal question, not a loophole* — with a federal injunction hearing this month.

**The fabricated quote.** "Announced capital is not deliverable capacity. Those are
different things, and the market keeps pricing them the same." Attributed in the
brief to a fund manager, in print, July 2026. It does not exist. Zero hits on the
exact string, not in either article cited around it. It was the best-sounding line
in the brief and it is exactly the kind of thing a judge spot-checks. Two real
replacements are in `docs/evidence.md` E2. **Do not use the original.**

Full claim-by-claim ledger is `docs/evidence.md`: 13 confirmed, 5 need rewording,
1 unsupported.

**Three real bugs in my own engine**, found by the agent whose job was writing your
explainer docs — it read the code closely enough to catch what the tests missed:

- New Jersey's Ozone Transport Region rule was *stated* in the trigger text and
  never *applied*. A NJ parcel with no Green Book listing scored major PSD at
  100 tpy instead of nonattainment NSR at 50. That is the Vineland failure mode,
  and the bug handed developers the easier of two answers.
- Consumed PSD increment added months only under PSD, so a nonattainment site with
  a full increment scored *cheaper* than an attainment one.
- The permit-by-rule gate tested tons only, so a 75 MW combined-cycle plant scored
  a Texas permit-by-rule it cannot have. Real PBRs carry heat-input limits.

All three fixed, each with a regression test. **50 tests, all passing.**

**A false claim in my own README.** It said "move 22 miles, minor NSR instead of
PSD, save 18 months." Not reproducible at 500 MW, and the sweep proves why.

**The national sweep, and its headline finding.** 3,222 counties scored in half a
second. 3,026 major PSD, 196 major nonattainment NSR, **zero minor**. There is no
county in the United States where a 500 MW onsite gas plant is a minor source —
NOx clears the 100 tpy List-of-28 threshold everywhere. The spread for *identical
equipment* is **1,309 days**. All 21 New Jersey counties tie for slowest at 1,918
days on the OTR-plus-EJ stack, which is the Vineland failure mode showing up
nationally without anyone hand-coding it.

Map is `outputs/county_map.html` — 708 KB, self-contained, no external requests,
renders with JavaScript disabled, works in light and dark.

**Mireye is live and verified.** 884 of 25,000 credits spent (about $0.88), 25
calls, zero throttles. The credit model in `providers/mireye.py` reproduces their
meter **exactly** — 884 modelled against 884 billed. Auth is `Bearer <JWT>`.
Three brief assumptions were wrong: `data_center_siting` is 106 fields not 90,
`site_selection` is 72 not 54, and `wildfire` is really `wildfire_underwrite`.

**All four field requests fired, and landed as a clean three-way split** — which is
the best possible outcome on camera:

| Request | Outcome |
|---|---|
| Nearest Class I area distance | **matched** — live sample, Shenandoah NP at 63,478 m, cited to USDI-NPS |
| County nonattainment by pollutant | **near miss** — their field is blank for every non-ozone pollutant |
| Ambient PM2.5 / NO2 background | **queued**, position 2, ETA 6 Aug |
| Major stationary sources within X km | **queued**, position 3, ETA 6 Aug |

It also found two live bugs in their API — `@airports` returning 503, and
`nearest_airport_distance_m` returning a *hospital helipad* for Ashburn, which is
wrong for a Part 77 stack review. That is genuine feedback-field material.

**The demo site found itself.** Ashburn, Virginia: 120 m to a 230 kV transmission
line, 504 m to a substation. By Mireye's own siting deck it is an excellent parcel.
It is also ozone nonattainment, Moderate, with Shenandoah National Park 63 km away
— inside the 100 km radius that pulls in Federal Land Manager review. A 500 MW
combined-cycle plant there is roughly 57 months. The same plant in Ellis County,
Texas is about 20 months.

**That gap, on one real parcel, is the entire product.** Their API says yes. Ours
says not for four and a half years. Lead with it.

**External data landed too.** 463 nonattainment designations across 245 counties,
parsed from EPA's dBASE files — there is no CSV, despite what the brief says — with
171 partial-county areas flagged rather than silently applied countywide. 27
counties hand-verified, 11 with a moratorium in force. And the xAI docket is found:
**NAACP v. X.AI Corp., 3:26-cv-00074, N.D. Mississippi**, over Southaven — not
W.D. Tennessee over Memphis, as the brief had it. Earthjustice is on the docket;
SELC is not.

**The backtest is 3 cases, and one is a miss.** Vineland NJ and Project Jupiter NM
both hit on the mechanism that actually bound. xAI Colossus 1 is a miss: the engine
says major PSD and about two years, and xAI energised in weeks by taking the
position the turbines were nonroad engines. The engine prices the compliant path
and has no variable for a developer who runs it anyway and litigates. **Keep the
miss in the video.** It is what makes the other two credible.

Still running: the agent loop and both search loops.
