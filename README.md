# Deliverable

Tells you whether a data center power project can legally get built where it's
announced, and if not, where nearby it could.

Example, from a real run: a 500 MW combined-cycle gas plant in a county with
85% of its NOx increment consumed and a Class I wilderness 60 km away needs a
major PSD permit. Roughly 24 to 66 months at Virginia DEQ. The same plant 22 miles
away is minor NSR, about 5 months.

Built on [Mireye](https://www.mireye.com) for the physical layer.

## Why

16 GW of US data centers were announced for 2026. About 5 GW is actually on the
ground. Permits are a large part of the gap: 75 projects worth roughly $130 billion
were blocked or delayed in Q1 2026 alone, and of ~90 GW of announced behind-the-meter
generation, 2.2% is operating. Sources for every number are in `docs/evidence.md`,
checked claim by claim.

The specific thing nobody screens for:

> Which permit you need is decided by where the land is, not by what you're building.

Same 500 MW plant, two counties 40 miles apart. One is a 4 to 6 month minor permit.
The other is major PSD with full dispersion modeling and public comment — 2 to 3
years, and it may fail. Developers buy land for power, fiber and price, then find out.

## What it does

1. Resolve the parcel (Mireye). Refuse low-confidence matches rather than guessing.
2. Pull physical facts and infrastructure proximity (Mireye) — terrain, land cover,
   distance to gas pipeline and transmission, who lives within a kilometre.
3. Estimate potential to emit from MW, prime mover, fuel, controls and run hours.
4. Work out the air permit pathway: source category, threshold, attainment status,
   increment, Class I, state overlay.
5. Check the non-air blockers: county moratoria, zoning posture, federal litigation.
6. If it fails, **search** — outward across candidate parcels for one where the
   pathway flips, and across design configs at the current parcel.

Step 6 is the part that makes it an agent. It does not stop at a report.

## Setup

```bash
git clone https://github.com/akshatsingh-dev/deliverable
cd deliverable
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest -q          # 47 tests, no API keys needed
```

To run against live data:

```bash
cp .env.example .env
# MIREYE_API_KEY      sign up at mireye.com/account with code BUILD
# ANTHROPIC_API_KEY   the planner's reasoning loop
# COURTLISTENER_TOKEN free, courtlistener.com/help/api/rest/
```

The whole repo runs with no keys at all. `NullProvider` refuses every physical
lookup rather than returning plausible-looking defaults, so a keyless run produces
an obviously incomplete answer rather than a quietly wrong one.

## The agent never acts on the world

There is no email client in this codebase. No HTTP POST to a third party. No form
automation. The agent reasons, decides, searches, and drafts. Drafts land in
`outputs/drafts/` as plain files for a human to send.

That is deliberate. "Acts" in the challenge criterion means acts on the analysis —
searching parcels, testing generation configs, re-planning which Mireye calls to
make. It does not mean acts on the world without supervision. An agent that emails
a county planning office on its own is a liability, not a feature.

## What's real and what isn't

- **County moratorium data: 20-odd counties, entered by hand.** I did not write a
  scraper. Hand-entering from public trackers was faster and more accurate, and the
  records carry their source URLs so you can check them.
- **Backtest: 3 cases, and one of them is a miss.** Nebius/DataOne at Vineland NJ
  and Project Jupiter in Doña Ana County NM both hit, on the mechanism that
  actually bound. xAI Colossus 1 is a miss: the engine says major PSD and about
  two years, and xAI energised in weeks by taking the position that the turbines
  were nonroad engines. The engine prices the compliant path and has no variable
  for a developer who runs it anyway and litigates. Three cases is a demonstration,
  not a rigorous out-of-sample test. A real backtest needs a point-in-time panel
  across hundreds of projects. See `docs/backtest-notes.md`, which is blunt about it.
- **8 states modelled properly** (VA, TX, GA, OH, AZ, NJ, NM, IL). The other 42 fall
  back to federal defaults, and the output says so instead of hiding it.
- **The county map is a screening layer.** It uses county-level facts only. It cannot
  see parcel increment, terrain or pipeline distance. The parcel run is the answer.
- **Timelines are calibrated on public permit records and agency guidance**, not on a
  validated statistical model. They are ranges and are presented as ranges.
- **This is a screen, not an applicability determination.** A licensed professional
  signs those and carries the liability. This tells you which conversation you are
  about to have.

## Notes on the Mireye API

See `docs/mireye-api-notes.md` for the full engineering note. Short version lives
in the challenge feedback draft at `outputs/drafts/mireye_feedback.md`.

## Layout

```
agent/
  emissions.py    potential-to-emit estimator, AP-42, pure math
  pathway.py      the permit decision engine
  planner.py      the tool-calling loop
  search.py       alternate site + config search — this is the "act"
  report.py       terminal, markdown and JSON output
providers/
  base.py         PhysicalFactsProvider interface — makes going global a data problem
  mireye.py       the US implementation
  cache.py        SQLite response cache so re-runs are free
ingest/
  greenbook.py    EPA nonattainment designations, one CSV
  dockets.py      CourtListener, one endpoint
  counties.json   hand-entered moratoria
sweep/            national county scoring and the map
backtest/         Nebius NJ, NM Stargate
docs/             explainers, evidence ledger, API notes
```

Start with `BUILD-LOG.md` if you want the whole thing explained end to end.
