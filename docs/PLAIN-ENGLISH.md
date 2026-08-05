# Deliverable, in plain English

Read this before you record anything. No code. Every term is defined the first
time it appears.

---

## 1. The story

Someone announces a 500 megawatt data center. That is a mid-size power station's
worth of electricity, dedicated to one building full of chips.

The chips are ordered. The money is raised. There is a press release with a date
on it. Analysts model the revenue. A hedge fund buys the stock of the company
building the turbines. Then the date passes and the building is not running.

It was not the chips. It was not the money. Hyperscaler capital spending is
projected above $690 billion in 2026. It was the power.

Not "there is no electricity." The problem is narrower. The grid cannot connect you
fast enough, so you build your own power plant on the site. And then you discover
that before you can burn a single cubic foot of gas, a state agency has to give you
a piece of paper called an air permit. That paper takes between four months and
five years, depending on facts about the dirt you bought that nobody checked before
they bought it.

The numbers are not small. Morgan Stanley says US data centers need another
68 gigawatts between 2026 and 2028, with a 38 gigawatt hole in that. Of 90
gigawatts of announced on-site power generation, 2.2% is operating and 60% exists
only as an announcement. In Q1 2026 alone, at least 75 projects worth about
$130 billion were blocked or delayed. Nebius cannot get an air permit for a
400 MW on-site gas plant sitting under a $17.4 billion Microsoft contract.

The market prices announced capacity as if it were deliverable capacity. It is
not.

---

## 2. The one fact the whole product turns on

**Which permit you need is decided by where the land is, not by what you are
building.**

Take one specific plant. 500 MW, combined-cycle gas turbines, best available
pollution controls. Do not change a single bolt. Put it in two different counties.

**Loudoun County, Virginia.** Major nonattainment New Source Review. 34 to 88
months, most likely 57. Close to five years, and a real chance it never issues.

**Ellis County, Texas.** Same plant, same emissions to the pound. Major Prevention
of Significant Deterioration. 12 to 30 months, most likely 20.

Thirty-six and a half months of difference. Same plant. Different dirt. Here is
why, in four steps.

**Step one: is the county's air already dirty?** The EPA labels every county
"attainment" (clean enough for a given pollutant) or "nonattainment" (not clean
enough). Loudoun sits inside the Washington DC ozone nonattainment area. Ellis
County is not in a nonattainment area for anything.

In a nonattainment area you are not asking permission to add pollution to clean
air. You are asking to add pollution to air that is already failing a federal
standard. The law treats those as different requests. In nonattainment you have to
find an existing factory nearby, pay it to cut its emissions, and hand those cuts
to the regulator. That is called an **offset**. The engine computes 170 tons of
offsets needed here. In some parts of the country those credits do not exist for
sale at any price.

**Step two: is the pollution budget already spent?** Even in a clean county there
is a cap on how much the air is allowed to get worse. It is called the **PSD
increment**, and it is a fixed, shared budget. Every factory permitted before you
took a slice. If the sources around you have eaten 85% of it, your whole plant has
to fit in the 15% left. Above 95% consumed the engine calls it a hard stop,
because at that point no plant of any size may be permittable there.

**Step three: is there protected wilderness nearby?** Certain national parks and
wilderness areas are legally designated **Class I areas**, with extra protection
for how the view looks. Shenandoah National Park is 60 kilometres from a Loudoun
site. That is inside the 100 km line where the federal agency running the park
gets formal notification and can object on visibility grounds, even if every other
number in your application passes. The engine adds six months for that.

**Step four: what kind of plant did you pick?** The only one of the four that is
your choice. There is a federal list of 28 named categories of industrial plant. On
the list, you become a "major source" at 100 tons per year of any single pollutant.
Off it, the line is 250 tons. A combined-cycle plant has a steam cycle, which makes
it a "fossil fuel-fired steam electric plant," item one on that list. A
simple-cycle plant has no steam cycle and is not on the list. One design decision
moves your threshold by 150 tons per year.

Nobody screens for any of this before optioning the land. They screen for power,
fibre and price, then find out.

---

## 3. What our thing does, in six sentences

You give it an address, a size in megawatts, and a generation design. It resolves
the address to a real parcel and refuses to guess if it is not confident. It
computes how many tons of each pollutant that plant could legally emit in a year.
It runs the same decision tree an air permitting engineer runs, in the same order,
and names the permit you need. It attaches a timeline for that state agency, plus
every rule that fired, with the citation next to it. Then it goes looking for a
version of your project that is not stuck.

---

## 4. What "the agent acts" means

The Mireye challenge has one hard rule: they want agents that reason, decide, and
**act** on physical-world data. Not a website with a map on it.

Most entries will reason and then stop at a report. "Your permit is bad. Good
luck." Ours does two more things.

**It searches outward across parcels.** `search_alternate_sites` holds the design
fixed and re-runs the whole analysis at candidate points in expanding rings. It
comes back with an instruction: move from Loudoun County to Mecklenburg County,
still in Virginia, and the same plant goes from 57 months to 34. Go to Ellis
County, Texas, and it goes to 20.

**It searches across designs at the parcel you already own.** Sometimes moving is
not an option, because the fibre is there or the land is already bought. So it
holds the location fixed and varies the plant. At the Loudoun site it finds this:
accept a legally binding cap of 5,337 operating hours a year, and the plant drops
out of major nonattainment review into **synthetic minor**. Fifty-seven months
becomes seventeen.

Then it prices that, which is the part that makes it useful rather than clever.
5,337 hours is 61% availability. You would be turning the plant off for 39% of the
year. That is not a data center power plant any more, and the engine says so in
the output in those words. It does not just find the door. It tells you what the
door costs.

---

## 5. Who pays for this, and why

**Hedge funds and asset managers.** Anyone holding GE Vernova, Vertiv, Bloom
Energy, Constellation, Talen, Vistra, Equinix, or the utilities carrying data
center load. They price announced capacity as deliverable capacity. A fund manager
said exactly that in print in July 2026. They lose money every time a project they
modelled as 2026 slips to 2028. $50k to $500k a year, no procurement department.

**Data center and power developers.** Hyperscaler site-selection teams, colo
developers, behind-the-meter power developers. They lose money the other way. One
wrong site is tens of millions in land options, engineering and legal fees, plus
18 to 36 months of dead time. Nebius is the live example. $250k to $1M a year
enterprise, or $10k to $25k per site report, which is the realistic first revenue.

**Air permitting consultancies.** Trinity, ERM, Onterris. They do this by hand
today, so they lose money on the hours. They would rather buy the screen and keep
the billable interpretation. A licensed professional still signs the opinion. That
is why they are a channel rather than a competitor.

**Infrastructure lenders.** They underwrite against the announced energization
date. When the date is wrong, their model is wrong. Same feed, diligence use case.

---

## 6. What is genuinely built, and what is a demonstration

Read this twice. A judge who finds soft ground you did not admit to discounts
everything else you said.

**Built and running.** About 11,400 lines across 15 modules. 47 tests pass with no
API key.

- `agent/emissions.py` and `agent/pathway.py`. The potential-to-emit calculator and
  the permit decision engine. AP-42 emission factors with their table citations,
  the List of 28, the PSD and nonattainment thresholds, offset ratios, eight state
  overlays, and about twenty rules that each fire with a citation and a
  months-added number. Every number in this document came out of these two files.
- `providers/base.py`, `providers/mireye.py`, `providers/cache.py`. The interface
  every physical fact enters through, with `source`, `fetched` and `confidence`
  attached from the first moment. The live Mireye implementation. A SQLite cache so
  re-runs cost nothing. An unresolvable address raises an error rather than
  returning a plausible guess.
- `agent/search.py`. Both search loops. `search_alternate_sites` walks candidate
  parcels in expanding rings and re-runs the engine at each. `search_configs`
  varies the plant at a fixed parcel.
- `ingest/greenbook.py`, `ingest/dockets.py`, `ingest/counties.py`. The EPA Green
  Book parsed to `data/greenbook.json`, CourtListener returning real federal
  dockets, and the hand-entered county posture file.
- `sweep/counties.py`. The national sweep, and it has run: **3,222 counties scored,
  3,028 major PSD, 194 major nonattainment NSR, 67 with a hard stop.** Fastest is
  Texas at 609 days, slowest New Jersey at 1,918.
- `backtest/cases.py`. Three cases, each with dated input provenance and an
  explicit list of facts deliberately excluded.

**Not finished.** `agent/report.py` is missing, so `python3 -m agent.planner` still
fails on import. Check before you record.

**Known soft spots.**

- The timeline model is additive. Each rule that fires adds a fixed number of
  months and they sum. No interaction between them, no cap. It is a defensible
  ordering of sites, not a calibrated forecast of any single site.
- Eight states are modelled with real agency behaviour. The other 42 fall back to
  a flat federal default. The engine says so in its own output.
- The backtest is three cases, two hits and one honest miss. Say the number out
  loud in the video.
- The county map is a screening layer. Permits are issued against parcels, not
  counties, and 90 of the 3,222 counties are only partly in a nonattainment area.
  Say that out loud too.
- The README still says the backtest is two cases and that a 500 MW plant 22 miles
  away is minor NSR. Neither matches the code. Fix the README before you submit.

**One thing the code does that is better than the pitch.** The brief lists "split
the plant below thresholds" as a design option. The code refuses to give you
credit for it. Split a 500 MW plant into four units and the emissions total does
not move, and the engine adds a warning that EPA aggregates units that are
contiguous, under common control, and in the same industrial grouping. That is the
correct legal answer and it costs the pitch a bullet point. Keep it.
