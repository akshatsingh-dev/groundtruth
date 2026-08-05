# Deliverable

Tells you whether a data center power project can legally get built where it's
announced, and if not, where nearby it could.

Example, from a real run on a real parcel in Ashburn, Virginia. Mireye says this
site is excellent: 120 m to a 230 kV transmission line, 504 m to a substation. By
any siting deck it is a yes.

Then you ask the next question. The county is ozone nonattainment, Moderate.
Shenandoah National Park is 63 km away, inside the 100 km radius that triggers
Federal Land Manager review. A 500 MW combined-cycle plant here is major
nonattainment NSR — roughly 57 months, plus offsets. The same plant in Ellis
County, Texas is major PSD at about 20 months.

Same machine. Same fuel. **37 months of difference, decided entirely by the dirt.**

Built on [Mireye](https://www.mireye.com) for the physical layer.

## Why

16 GW of US data centers were announced for 2026. About 5 GW is actually on the
ground. Permits are a large part of the gap: 75 projects worth roughly $130 billion
were blocked or delayed in Q1 2026 alone, and of ~90 GW of announced behind-the-meter
generation, 2.2% is operating. Sources for every number are in `docs/evidence.md`,
checked claim by claim.

The specific thing nobody screens for:

> Which permit you need is decided by where the land is, not by what you're building.

Developers buy land for power, fiber and price, then find out.

One finding worth stating plainly, because it surprised us and it is checkable:
**we scored all 3,140-odd US counties and not one of them makes a 500 MW onsite gas
plant a minor permit.** At that size, NOx clears the 100 tpy List-of-28 threshold
everywhere in the country. The question is never "can I avoid major review at 500
MW." It is "which flavour of major review, and how many months" — and that answer
ranges from about 20 months to over 90 depending on the county and the state agency.
Below roughly 150 MW the picture changes completely and minor pathways open up,
which is itself a design finding.

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
