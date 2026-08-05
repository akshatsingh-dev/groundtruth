# Demo script

Two minutes, word for word, built around the run that actually exists in
`outputs/demo/`. Speaking rate assumed 150 words per minute. Total spoken: about 350
words.

Read the whole thing once before recording. There are two caveats you must say out
loud. They're marked **CAVEAT** and they're bolded in the speech. Don't cut them for
time. A judge who catches an overclaim discounts everything else.

---

## Before you hit record

**Terminal setup.** Font at 18pt or larger. Dark background. Window wide enough that a
40-column table doesn't wrap. Clear the scrollback.

**Have these ready in separate tabs so nothing loads on camera:**

1. The Musk quote as a full-screen slide.
2. Terminal, in the repo root.
3. `outputs/county_map.html` open in a browser, already rendered, scrolled to the map.
4. `outputs/demo/report.md` open in a pager or editor, scrolled to the top.

**Commands, verified 5 August 2026.** All of these run clean and none of them spends
Mireye credits:

```bash
.venv/bin/python -m pytest -q            # 52 passed
.venv/bin/python -m backtest.cases       # all three cases, full output
.venv/bin/python -m sweep.counties --fresh   # 3,222 counties, 0.5s, 0 credits
.venv/bin/python -m sweep.map            # writes outputs/county_map.html and .svg
.venv/bin/python -m providers.cache      # cache stats, good B-roll
.venv/bin/python -m ingest.greenbook     # parses the EPA export to data/greenbook.json
.venv/bin/python -m ingest.dockets       # live CourtListener, real federal cases
```

**One command you should not run on camera.** This is the one that produced the demo:

```bash
.venv/bin/python -m agent.planner --out outputs/demo
```

It hits the live Mireye API. The captured run cost 94 credits and we're budgeting
them. Show `outputs/demo/report.md` instead and say the command out loud. The run is
real, it's dated, and the trace is in `outputs/demo/trace.json` with all 13 tool calls
in order.

---

## 0:00 – 0:15 · The hook

**On screen:** full-screen slide, black background, quote in white. This is verbatim
from the Dwarkesh episode published 5 February 2026. Don't paraphrase it and don't
stitch it to anything else.

> "They have to do a study for a year. A year later, they'll come back to you with
> their interconnect study."
> — Elon Musk, 5 February 2026

**You say:**

> Musk told Dwarkesh the AI bottleneck isn't chips and it isn't money. It's getting
> permission to switch the power on. I checked whether that's true. It is, and nobody
> screens for it. This is Deliverable.

*(38 words, 15 seconds)*

*(Alternate slide if you'd rather lead on the regulator: "The utility industry is a
very slow industry. They pretty much impedance match to the government, to the Public
Utility Commissions." Same episode, also verbatim.)*

---

## 0:15 – 0:30 · The gap

**On screen:** one slide, four numbers, no chart.

```
16 GW announced for 2026            ~5 GW actually on the ground
$130B blocked in Q1 2026            75 projects, 833 opposition groups
90 GW of on-site generation         2.2% operating
59 projects behind that 90 GW       ~60% still just an announcement
```

**You say:**

> Sixteen gigawatts of US data centers were announced for 2026. About five is on the
> ground. A hundred and thirty billion dollars of projects got blocked in the first
> quarter alone. And of ninety gigawatts of announced on-site power, two point two
> percent is running.

*(45 words, 16 seconds)*

---

## 0:30 – 1:10 · One real run

**On screen:** `outputs/demo/report.md`, scrolled from the top. Say the command that
produced it while the file is on screen:

```bash
.venv/bin/python -m agent.planner --out outputs/demo
```

The site is Vineland, Cumberland County, New Jersey. 39.4862, -75.0257. 400 MW of
uncontrolled simple-cycle gas turbines. This is the Nebius parcel.

**What's on screen, in this order.** Every number is copied straight out of the file.

```
2% probability of energizing on the announced schedule
  16 months to the announced date. 3 to prepare + 66 of agency review = 69 required.

Resolved: Cumberland County, NJ (FIPS 34011), NJ DEP

Heat input 4,200 MMBtu/hr
PTE: NOx 5,887 tpy · CO 1,509 · PM10 121 · PM2.5 121 · SO2 63 · VOC 39 · HCHO 13

Pathway: MAJOR NONATTAINMENT NSR — 41 to 104 months, likely 66
  Controlling: NOx at 5,887 tpy against a 50 tpy threshold

  nonattainment designation   0    ozone serious, Philadelphia-Atlantic City PA-NJ
  major nonattainment nsr    +6    LAER, 1.20:1 offsets = 7,064 tons
  title v                     0    5,887 tpy over the 100 tpy line
  nsps turbine                0    KKKK + new KKKKa. Not a closed loophole.
  state toxics               +2    NJ formaldehyde and acrolein modelling
  ozone transport region     +3    CAA 184. 50 tpy statewide, clean monitors or not.
  ej denial authority        +4    N.J.S.A. 13:1D-157. NJDEP can deny outright.
  litigation                 +3    2 federal cases, D.N.J. [CourtListener]

Claude Agent SDK tool-calling loop (claude-opus-5) · 13 tool calls · 94 credits
```

**You say:**

> Here's a real run on a real parcel. Four hundred megawatts of gas turbines in
> Vineland, New Jersey. The agent resolves the site, buys the physical facts it needs
> from Mireye, and works the permit tree. Potential to emit is five thousand eight
> hundred and eighty-seven tons of NOx a year. The threshold it has to clear is fifty.
> Not fifty percent over. A hundred and seventeen times. Cumberland County is serious
> ozone nonattainment, and New Jersey is inside the Ozone Transport Region, which sets
> that fifty tons by statute no matter what the local monitors read. Offsets: seven
> thousand tons. Sixty-six months. The announced date is sixteen months out. Every
> line has its citation.

*(118 words, 47 seconds. This is the tightest beat in the script. Practise it.)*

---

## 1:10 – 1:40 · The act

**On screen:** stay in `outputs/demo/report.md`, scroll to "Alternate site" and
"Config alternatives".

```
ALTERNATE SITE — same 400 MW plant, config unchanged
  Move 37 miles W to New Castle County, DE.  66 mo -> 42 mo.  Save ~24 months.
  Clears: ej_denial_authority, state_toxics
  Screened 13 of 16 parcels out to 120 km for 80 credits

CONFIG AT THIS PARCEL — same dirt, different plant
  Switch to solid oxide fuel cells   -> MINOR NSR, 21.6 months, +44 saved
  Add SCR                            -> still major NNSR, 66 months, +0
  Combined cycle                     -> still major NNSR, 66 months, +0
```

**You say:**

> Most tools stop at "your permit is bad." This one goes and finds the answer. It laid
> sixteen candidate parcels on rings out to a hundred and twenty kilometres, resolved
> thirteen of them, and came back with New Castle County, Delaware. Thirty-seven miles
> west, twenty-four months faster. And here's the part I want to be precise about:
> that does **not** escape the Ozone Transport Region, because Delaware is in it too.
> What it escapes is New Jersey's own stack. The EJ denial statute and the state
> toxics programme. Then it holds the parcel still and changes the plant. Only one
> config flips the pathway: solid oxide fuel cells. Minor NSR. Forty-four months
> saved. Our backtest freezes this project at the first of March. On the twentieth of
> May, Nebius replaced the engines with Bloom fuel cells. Eighty days after our
> cutoff, the developer did the thing the search names.

*(147 words, 59 seconds. This runs long. See the cut below.)*

**Cut to 30 seconds if you need the time.** 78 words:

> Most tools stop at "your permit is bad." This one searches. Sixteen candidate
> parcels out to a hundred and twenty kilometres, and it comes back with Delaware,
> thirty-seven miles west, twenty-four months faster. Note what that saves: New
> Jersey's EJ statute and state toxics, **not** the transport region, because Delaware
> is in that too. Then it changes the plant instead of the site. Fuel cells flip it to
> minor NSR, forty-four months saved. Nebius made exactly that swap eighty days after
> our cutoff date.

---

## 1:40 – 1:52 · Backtest · **CAVEAT 1**

**On screen — command:**

```bash
.venv/bin/python -m backtest.cases
```

Scroll straight to the summary table at the bottom. Don't try to show the per-case
input ledgers, there's no time.

**What appears:**

```
case                       frozen      engine said                months       grade
------------------------------------------------------------------------------------
Nebius / DataOne — Vinela  2026-03-01  major_nonattainment_nsr    42-108        Hit
Project Jupiter (OpenAI /  2026-02-01  major_nonattainment_nsr    38-99 +STOP  Hit on the
                                                                               binding constraint
xAI Colossus 1 — Memphis,  2024-09-01  major_psd                  15-39         Miss

Two of three flagged the mechanism that actually bound. The third is an
honest miss: the engine prices the compliant path and xAI did not take it.
```

**You say, verbatim:**

> I ran it backwards on three projects, inputs frozen before each one failed. It gets
> Nebius. It gets the Stargate site in New Mexico, and there it flags the gas pipeline
> rather than the air permit, which is exactly what got denied. It misses xAI, and the
> miss is in the output, because xAI energised without a permit and the engine only
> prices the legal path. **Three cases, one of them a self-declared miss. That's a
> demonstration that it names the right mechanism. It is not validation and I'm not
> calling it validation.**

*(88 words, 35 seconds. Too long for the slot. Use the cut.)*

**Cut version, 55 words, 22 seconds:**

> Ran it backwards on three projects, inputs frozen before each failed. It gets Nebius.
> It gets the Stargate site, and there it flags the pipeline rather than the plant,
> which is what actually bound. It misses xAI, because xAI energised without a permit.
> **Three cases. One is a miss and it says so. Demonstration, not validation.**

*(The bolded sentence is mandatory. Say it at normal speed, not as a throwaway.)*

---

## 1:52 – 2:00 · The map · **CAVEAT 2**

**On screen:** `outputs/county_map.html`, held still. No zooming, no panning.

Regenerate it beforehand if you want it fresh:

```bash
.venv/bin/python -m sweep.counties --fresh && .venv/bin/python -m sweep.map
```

The numbers behind it, in case anyone asks: 3,222 counties scored. 2,843 major PSD.
379 major nonattainment NSR. Zero minor. 77 carrying a hard stop. Fastest is Brewster
County, Texas at 609 days. Slowest is New Jersey at 1,918.

**You say, verbatim:**

> Every US county, scored on days until legal power for a five hundred megawatt gas
> plant. Three thousand two hundred and twenty-two of them. Not one makes it a minor
> permit. **This is county-level, so it's a screening layer, not a parcel answer.**
> Announced is not deliverable.

*(43 words, 15 seconds. The bolded clause is mandatory.)*

**End on the map. No outro card, no music, no "thanks for watching."**

---

## Timing check

| Beat | Words | Seconds |
|---|---|---|
| Hook | 38 | 15 |
| The gap | 45 | 16 |
| The run | 118 | 47 |
| The act (cut version) | 78 | 31 |
| Backtest (cut version) | 55 | 22 |
| Map | 43 | 15 |
| **Total** | **377** | **146** |

Twenty-six seconds over two minutes. Cut in this order, and stop when you're under:

1. The alternate-slide line in the hook. Not spoken anyway.
2. "Not fifty percent over. A hundred and seventeen times." from the run. Saves 8
   seconds and the 5,887-against-50 number already carries it.
3. The whole gap beat except the first sentence. Saves 12 seconds.

Never cut either **CAVEAT**.

---

## The 60-second version

For a hallway, or if the form caps length.

> Sixteen gigawatts of US data centers were announced for 2026. About five is on the
> ground. The bottleneck isn't chips or money. It's the air permit for the power plant
> you build on site.
>
> Here's what nobody prices: which permit you need is decided by where the land is,
> not by what you're building. Same five hundred megawatt gas plant. Loudoun County,
> Virginia: ozone nonattainment, inside the Ozone Transport Region, Shenandoah sixty-
> three kilometres away. Forty-eight and a half months. Brewster County, Texas: twenty
> months. Same machine, same fuel.
>
> So I built an agent that computes that pathway from an address, with every fact
> cited to its federal source. Then it does the useful part. It searches outward for a
> parcel where the same plant is faster, and it searches across designs at the parcel
> you already own. On the live run it moved a New Jersey project thirty-seven miles to
> Delaware and saved twenty-four months, and it found that switching to fuel cells
> saves forty-four. Nebius made that exact swap eighty days after our backtest cutoff.
>
> Built on Mireye for the physical layer. Three cases in the backtest, one of them a
> miss, so that part's a demonstration, not proof.

*(212 words, about 60 seconds at pace.)*

---

## The 30-second version

> Sixteen gigawatts of data centers announced for 2026. Five on the ground. The gap is
> permits, and the unpriced fact is that which permit you need depends on where the
> land is, not what you're building. The same five hundred megawatt gas plant is
> forty-eight months in Loudoun County, Virginia and twenty in Brewster County, Texas.
> I built an agent that computes that from an address, cites every fact, and then goes
> and finds you a parcel or a plant design where the answer is different. It's for
> hedge funds pricing announced capacity as deliverable, and for the site-selection
> teams who find out after they've bought the land.

*(107 words, about 30 seconds.)*

---

## One line, if that's all you get

> Mireye tells you whether a site is good. We tell you whether they'll let you switch
> it on.

---

## Things to have an answer ready for

Not scripted. Just don't be surprised.

**"Your report says the January 2026 EPA rule didn't close the turbine loophole."**
Correct, and that's the fixed version. The rule finalised a conditional exclusion that
isn't operative because EPA hasn't adopted the Title II standards it depends on. The
fast path is unsettled, not closed, and there's a preliminary injunction hearing in
Mississippi this month. Full answer in `docs/OBJECTIONS.md`, question 16.

**"xAI built Colossus in 19 days. Your model says two years."** Get the facts right
before you concede anything. The 19 days is hardware install to first training run.
The full Colossus 1 buildout in South Memphis was 122 days, roughly 420 MW of
trailer-mounted turbines, no Clean Air Act construction permit, under Shelby County's
reading that a unit parked somewhere under 364 days is a nonroad engine. Then concede
the real point: the engine prices the compliant path and has no variable for "run it
anyway and litigate." That's in the backtest verdict in those words.

**"Which lawsuit?"** Two sites, one state line apart, and people mix them up. Memphis,
Tennessee is Colossus 1, and its fight is a Shelby County permit appeal by the NAACP
and SELC. Southaven, Mississippi is Colossus 2, 27-plus turbines, and that's where the
April 2026 Clean Air Act suit was filed in N.D. Miss. Earthjustice is on that docket.
SELC is not. DOJ moved to intervene and dismiss on 16 June 2026, and the preliminary
injunction hearing is late this month.

**"Sixty-six months is not credible."** Agree with the shape of that. The claim is that
the model orders sites correctly, not that 66 is right and 55 is wrong. Question 8 in
OBJECTIONS.

**"Why is the demo site 400 MW simple-cycle uncontrolled when the sweep is 500 MW
combined-cycle with full controls?"** Because they answer different questions. The demo
is the Nebius configuration as proposed. The sweep needs one fixed reference plant so
3,222 counties are comparable. Both are stated in their own output.
