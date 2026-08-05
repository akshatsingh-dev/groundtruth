# Deliverable, in plain English

Read this before you record. No code. Every term is defined the first time it
appears.

Every engine number here came out of the code in this repo, run on 5 August 2026. Where
a command produces it, the command is written next to it.

---

## 1. The story

Someone announces a 500 megawatt data center. That's a mid-size power station's
worth of electricity going into one building full of chips.

The chips are ordered. The money is raised. There's a press release with a date on
it. Then the date passes and the building isn't running.

It wasn't the chips. Hyperscaler capital spending is projected above $690 billion
in 2026. It was the power.

Not "there is no electricity." The problem is narrower than that. The grid can't
connect you fast enough, so you build your own plant on the site. Before you burn a
cubic foot of gas, a state agency has to hand you a piece of paper called an air
permit. Score a 500 MW gas plant against every county in the country and that paper
takes 11.5 months in the best case and 99.3 in the worst. What decides which end you
land on is a set of facts about the dirt you already bought.

Morgan Stanley puts US data center demand at another 68 gigawatts between 2026 and
2028, with a 38 gigawatt hole in it before mitigations. Of about 90 gigawatts of announced on-site generation across 59
projects, 2.2% is operating and roughly 60% is still just an announcement. In Q1
2026, at least 75 projects worth about $130 billion were blocked or delayed.

Nebius is the case that makes it concrete. A 400 MW on-site gas plant in Vineland,
New Jersey, sitting under a $17.4 billion Microsoft contract. NJDEP never issued the
permit. On 20 May 2026 Nebius gave up on the engines and signed a 10-year deal with
Bloom Energy for 328 MW of solid oxide fuel cells instead. The site slipped to 2027.

Announced capital isn't deliverable capacity. The market prices them the same. That's
the trade.

If you want someone else's words for it, Michael Shawn of Peregrine Private Client,
July 2026: "In a permit-constrained market, the winner isn't whoever spends the most.
It's whoever already controls the land, the interconnect, and the power."

---

## 2. The one fact the whole product turns on

**Which permit you need is decided by where the land is, not by what you're
building.**

Take one plant. 500 MW, combined-cycle gas turbines, dry low-NOx combustors,
selective catalytic reduction, an oxidation catalyst. Best controls available. Don't
change a bolt. Put it in two counties.

**Loudoun County, Virginia.** Major nonattainment New Source Review. 30.5 to 76.5
months, most likely 48.5. That's 1,476 days.

**Brewster County, Texas.** Same plant, same emissions to the pound. Major Prevention
of Significant Deterioration. 11.5 to 30 months, most likely 20. That's 609 days.

Both come out of `.venv/bin/python -m sweep.counties --fresh`. Brewster is the
fastest county in the country. 233 other Texas counties tie it.

Twenty-eight and a half months of difference. Same plant. Different dirt. Five
reasons, and only one of them is a choice you get to make.

**Is the county's air already dirty?** EPA labels every county "attainment" (clean
enough for a given pollutant) or "nonattainment" (not). Loudoun sits inside the
Washington DC ozone nonattainment area, classified moderate. Brewster isn't in a
nonattainment area for anything.

In a nonattainment area you're not asking to add pollution to clean air. You're
asking to add it to air that already fails a federal standard. Different request,
different law. You have to find an existing factory nearby, pay it to cut its
emissions, and hand those cuts to the regulator. That's an **offset**. At Loudoun the
engine computes 170 tons of them. In some airsheds those credits don't exist for sale
at any price.

**Is the county inside the Ozone Transport Region?** Congress drew a box around the
Northeast in 1990 and said every state inside it applies nonattainment-style NOx
rules across its whole territory, clean monitors or not. Twelve states plus DC, and
nine jurisdictions in Northern Virginia. Loudoun is one of the nine. The sweep fires
that trigger in 256 counties.

This one matters more than it sounds, because it kills the obvious escape. Move a New
Jersey project to Pennsylvania or Delaware and you haven't left the region. You can't
drive out of it inside a day.

**Is the pollution budget already spent?** Even in a clean county there's a cap on how
much the air is allowed to get worse. It's called the **PSD increment**, and it's a
fixed budget shared with everyone who permitted before you. If the sources around you
have eaten 85% of it, your plant has to fit in the 15% left. The engine adds six
months at 80% consumed and calls a hard stop at 95%, because past that point no plant
of any size may be permittable there.

**Is there protected wilderness nearby?** Certain parks and wilderness areas are
**Class I areas**, with extra legal protection for how the view looks. Shenandoah
National Park is 63 km from the Ashburn parcel. That's inside the 100 km line where
the National Park Service gets formal notice and can object on visibility grounds
even if every other number passes. Six months.

**What kind of plant did you pick?** The only one of the five that's yours. There's a
federal list of 28 named categories of industrial plant. On the list you become a
"major source" at 100 tons per year of one pollutant. Off it, the line is 250. A
combined-cycle plant has a steam cycle, which makes it a "fossil fuel-fired steam
electric plant," item one on the list. A simple-cycle plant has no steam cycle and
isn't on it. One design decision moves your threshold by 150 tons a year.

Nobody screens for any of this before optioning the land. They screen for power,
fibre and price.

---

## 3. What it does, in six sentences

You give it an address, a size in megawatts, and a generation design. It resolves the
address to a real parcel and refuses to guess when it isn't confident. It computes how
many tons of each pollutant that plant could legally emit in a year. It runs the same
decision tree an air permitting engineer runs, in the same order, and names the permit
you need. It attaches a timeline for that state agency and every rule that fired, with
the citation next to it. Then it goes looking for a version of the project that isn't
stuck.

---

## 4. What "the agent acts" means

The Mireye challenge wants agents that reason, decide and act on physical-world data.
Not a website with a map on it.

Most entries will reason and then stop at a report. Ours does two more things, and
both of them ran in the demo. Read `outputs/demo/report.md` for the output.

**It searches outward across parcels.** `search_alternate_sites` holds the design
fixed and re-runs the whole analysis at candidate points in expanding rings. In the
demo it laid 16 candidates out to 120 km, resolved 13, dropped 3 that landed on open
water, and spent 80 credits doing it. The answer: move 37 miles west from Vineland,
New Jersey to New Castle County, Delaware. 66 months becomes 42.

Be careful how you say what that saves. It clears New Jersey's environmental justice
denial statute and New Jersey's state toxics programme. It does **not** escape the
Ozone Transport Region, because Delaware is in the region too. The 50 tpy NOx
threshold follows you across the river. The honest sentence is that you've escaped
New Jersey's state-specific stack, not the transport region.

**It searches across designs at the parcel you already own.** Sometimes moving isn't
an option. The fibre is there, or the land is bought. So it holds the location fixed
and varies the plant. At Vineland it finds one config that flips the pathway: solid
oxide fuel cells. Minor NSR, 21.6 months likely, 44 months saved. Nothing else works.
SCR cuts NOx from 5,887 tpy to 589 and doesn't move the pathway at all, because the
serious-ozone threshold is 50.

That's the strongest beat in the demo, and it's the one to say slowly. Our backtest
freezes Nebius at 1 March 2026. Nebius signed the Bloom fuel cell deal on 20 May
2026. Eighty days after the freeze date, the developer did the thing the config
search names.

The engine prices what it finds. At the Ashburn parcel, a 500 MW combined-cycle plant
can accept a federally enforceable cap of 5,337 operating hours a year and drop out of
major nonattainment review into **synthetic minor**. 54.5 months becomes 15. Then the
function says what that costs: 5,337 hours is 61% availability, and a data center
plant can't serve baseload at that cap. It finds the door and reads you the price on
the door.

---

## 5. Who pays for this

**Hedge funds and asset managers.** Anyone holding GE Vernova, Vertiv, Bloom Energy,
Constellation, Talen, Vistra, Equinix, or the utilities carrying data center load.
They price announced capacity as deliverable capacity and lose money every time a
2026 project slips to 2028. $50k to $500k a year, no procurement department.

**Data center and power developers.** Hyperscaler site-selection teams, colo
developers, behind-the-meter power developers. They lose money the other way. One
wrong site is tens of millions in land options and engineering, plus 18 to 36 months
of dead time. Nebius is the live example. $250k to $1M a year enterprise, or $10k to
$25k per site report, which is the realistic first revenue.

**Air permitting consultancies.** Trinity, ERM, Onterris. They do this by hand today
and lose money on the hours. They'd rather buy the screen and keep the billable
interpretation. A licensed professional still signs the opinion. That makes them a
channel, not a competitor.

**Infrastructure lenders.** They underwrite against the announced energization date.
When the date is wrong, the model is wrong.

---

## 6. What's built, and what's a demonstration

Read this twice. A judge who finds soft ground you didn't admit to discounts
everything else.

**Built and running.** About 14,250 lines across 17 modules. 52 tests pass with no API
key: `.venv/bin/python -m pytest -q`.

- `agent/emissions.py` and `agent/pathway.py`. The potential-to-emit calculator and
  the permit decision engine. AP-42 emission factors with table citations, the List of
  28, PSD and nonattainment thresholds, offset ratios, the Ozone Transport Region,
  eight state overlays, and about twenty rules that each fire with a citation and a
  months-added number.
- `providers/base.py`, `providers/mireye.py`, `providers/cache.py`. The interface every
  physical fact enters through, carrying `source`, `fetched` and `confidence` from the
  first moment. The live Mireye implementation. A SQLite cache so re-runs cost nothing.
  An unresolvable address raises rather than returning a guess.
- `agent/planner.py`, `agent/tools.py`, `agent/report.py`. The tool-calling loop, the
  10 tools it can call, and the report renderer. The demo run made 13 tool calls across
  those 10 tools and spent 94 Mireye credits.
- `agent/search.py`. Both search loops.
- `ingest/greenbook.py`, `ingest/dockets.py`, `ingest/counties.py`. The EPA Green Book
  parsed to `data/greenbook.json`, CourtListener returning real federal dockets, and 27
  hand-entered county records.
- `sweep/counties.py`. The national sweep, and it has run. **3,222 counties scored.
  2,843 major PSD. 379 major nonattainment NSR. 77 carrying a hard stop. Zero minor.**
  Fastest is Brewster County, Texas at 609 days. Slowest is New Jersey at 1,918.
- `backtest/cases.py`. Three cases, each with dated input provenance and an explicit
  list of facts kept out.

**Known soft spots.**

- The timeline model is additive. Each rule adds a fixed number of months and they
  sum. No interaction, no cap. It's a defensible ordering of sites, not a calibrated
  forecast of one site.
- Eight states are modelled with real agency behaviour. The other 42 get a flat
  federal default, and the engine says so in its own output.
- The backtest is three cases. Two hits, one honest miss. Say the number out loud in
  the video.
- The county map is a screening layer. Permits are issued against parcels, and 91 of
  the 3,222 counties are only partly inside a nonattainment area. Say that out loud
  too.
- `README.md` is stale in four places: it says 47 tests (52), two backtest cases
  (three), Ellis County Texas at 20 months as major PSD (Ellis is major nonattainment
  NSR at 30.5 months with an offset hard stop, because it's in the Dallas-Fort Worth
  severe-15 ozone area), and that minor pathways open below roughly 150 MW. The real
  crossover with full controls in a clean county is 340 MW.

**One thing the code does better than the pitch.** The brief lists "split the plant
below thresholds" as a design option. The code refuses to give you credit for it.
Split a 500 MW plant into four units and the emissions total doesn't move. The engine
adds three months and a warning that EPA aggregates units that are contiguous, under
common control, and in the same industrial grouping. That's the correct legal answer
and it costs the pitch a bullet point. Keep it.
