# Demo script

Two minutes, word for word, matched to §7 of the build brief. Speaking rate
assumed 150 words per minute. Total spoken: about 345 words.

Read the whole thing once before recording. There are two places you must say a
caveat out loud. They are marked **CAVEAT**. Do not cut them for time. A judge who
catches an overclaim discounts everything else.

---

## Before you hit record

**Terminal setup.** Font at 18pt or larger. Dark background. Window sized so a
40-column table fits without wrapping. Clear the scrollback.

**Have these ready in separate tabs so nothing loads on camera:**

1. The Musk transcript quote as a full-screen slide.
2. Terminal, in the repo root, virtualenv active.
3. The county map image or page, already rendered.
4. The backtest output, already run once so the cache is warm.

**Command status as of the last check.** These run clean today:

```bash
python3 -m pytest -q          # 47 passed
python3 -m ingest.greenbook   # parses the EPA export to data/greenbook.json
python3 -m ingest.dockets     # live CourtListener, real federal cases
python3 -m backtest.cases     # all three cases, full output
python3 -m sweep.counties     # 3,222 counties, already cached
python3 -m providers.cache    # cache stats, good B-roll
```

This one does **not** run yet: `python3 -m agent.planner` fails on
`ModuleNotFoundError: No module named 'agent.report'`. Re-check it before you
record. Each beat below has a fallback if it is still broken.

---

## 0:00 – 0:15 · The hook

**On screen:** full-screen slide, black background, the quote in white.

> "It's like those who have lived in software land don't realize that they're about
> to have a hard lesson in hardware. It's actually very difficult to build power
> plants."
> — Elon Musk, 5 Feb 2026

**You say:**

> Elon told Dwarkesh the AI bottleneck isn't chips and it isn't money. It's the
> permits. So I checked whether that's true, and it is, and nobody is screening for
> it. This is Deliverable.

*(35 words, 14 seconds)*

---

## 0:15 – 0:30 · The gap

**On screen:** one slide, four numbers, no chart.

```
16 GW announced for 2026        ~5 GW actually on the ground
$130B blocked in Q1 2026        75 projects, 833 opposition groups
90 GW of on-site generation announced   2.2% operating
```

**You say:**

> Sixteen gigawatts of US data centers were announced for 2026. About five is
> actually on the ground. A hundred and thirty billion dollars of projects got
> blocked in the first quarter alone. And of ninety gigawatts of announced on-site
> power, two point two percent is running.

*(45 words, 16 seconds)*

---

## 0:30 – 1:10 · One live run

**On screen — command:**

```bash
python3 -m agent.planner
```

`agent/planner.py` holds the tool-calling loop and a `demo_project()` at the
bottom. It needs `agent/report.py` to render, which was missing at last check.

**Fallback if the planner still fails:** a prepared script that builds the
`SiteContext` inline and calls `emissions.estimate` then
`pathway.determine_pathway`. Identical numbers, and you say "the Mireye fetch is
wired, I'm running from the SQLite cache for the video." That is true. Show
`python3 -m providers.cache` for two seconds if you want to prove it.

**What appears, in this order.** Every number below except the geocode confidence
is a real output from the engine as it stands today. The confidence value is
whatever the live Mireye call returns.

```
Resolved: Loudoun County, VA  (confidence 0.9x)  [Mireye /v1/geocode]

Config: 500 MW combined_cycle_turbine on natural_gas (dry_low_nox, scr,
        oxidation_catalyst), no enforceable hour cap (PTE at 8760)

Heat input 3,400 MMBtu/hr
PTE: NOx 148 tpy · CO 122 · PM10 98 · PM2.5 98 · SO2 51 · VOC 16 · HCHO 3

Source category: combined cycle -> fossil fuel-fired steam electric plant
        -> ON the List of 28 -> threshold drops 250 tpy to 100 tpy
        [40 CFR 52.21(b)(1)(i)(a)]

County: NONATTAINMENT, ozone (moderate), Washington DC-MD-VA
        [EPA Green Book, 40 CFR 81]

Nonattainment NSR: NOx 148 tpy vs 100 tpy threshold
        LAER required. Offsets: 170 tons at 1.15:1

Class I: Shenandoah National Park, 60 km. FLM notification + AQRV.   +6 mo
Increment: PM2.5 85% consumed by existing sources
Terrain: 180 m relief -> complex-terrain AERMOD                      +2 mo
Litigation: 1 federal case touching this county [CourtListener]      +3 mo
State: Virginia DEQ, 1.25x. One data center gas permit ever issued.  +2 mo

  MAJOR NONATTAINMENT NSR — 34 to 88 months, likely 57
```

**You say:**

> Here's a real site. Five hundred megawatt combined-cycle gas plant, Loudoun
> County, Virginia. Best controls available. Watch what it does. Combined cycle
> means there's a steam turbine, which puts it on a federal list of twenty-eight
> source categories, which drops the major-source threshold from two-fifty tons a
> year to a hundred. It's at a hundred and forty-eight. The county's in ozone
> nonattainment, so that's not PSD, it's nonattainment New Source Review. Offsets:
> a hundred and seventy tons. Shenandoah is sixty kilometres away, so the Park
> Service gets a veto. Every line has its citation next to it. Fifty-seven months.

*(105 words, 40 seconds — this is tight. Practise it.)*

---

## 1:10 – 1:35 · The act

**On screen — command:**

`agent/search.py` is built. Two entry points:

```python
search_alternate_sites(site, config, provider=..., radius_km=..., n_candidates=24)
search_configs(site, config)
```

`search_alternate_sites` lays candidate points on expanding rings, resolves each
through the provider, rebuilds a `SiteContext`, and re-runs `determine_pathway`.
`search_configs` varies the `GenerationConfig` and uses
`pathway.synthetic_minor_cap` to find the binding hour cap.

**Fallback if the planner still cannot drive them:** call the two functions from a
prepared script. They work standalone. Do not claim the loop chose the candidates
if you hand-fed them.

**One thing to be careful about.** `search_alternate_sites` defaults to a 15 km
radius. Mecklenburg County is roughly 180 miles from Loudoun, and Ellis County is
in another state, so neither comes out of a default-radius ring search. Either set
the radius wide enough that they are genuinely in scope, or present those two as a
comparison you ran rather than as something the loop discovered. Do not blur it.

**What appears:**

```
ALTERNATE SITES — same 500 MW plant, config unchanged

  Loudoun County, VA      major NA NSR       57 mo    1,718 days
  Mecklenburg County, VA  major PSD          34 mo    1,034 days   -22.5 mo
  Ellis County, TX        major PSD          20 mo      608 days   -36.5 mo

CONFIG CHANGES — same parcel, Loudoun

  + federally enforceable cap, 5,337 hr/yr
      -> SYNTHETIC MINOR, 17 months          -39.5 mo
      -> 61% availability. The plant cannot serve baseload alone at that cap.
```

**You say:**

> Most tools stop at "your permit is bad." This one goes and finds the answer. Same
> plant, different dirt: move to Mecklenburg County and it's twenty-two months
> faster. Ellis County, Texas, thirty-six. Or stay put and change the plant. Accept
> a legally binding cap of five thousand three hundred hours and you drop to
> synthetic minor. Seventeen months instead of fifty-seven. And it tells you the
> price: that's sixty-one percent availability. You're dark for thirty-nine percent
> of the year.

*(76 words, 26 seconds)*

---

## 1:35 – 1:50 · Backtest · **CAVEAT 1**

**On screen — command:**

```bash
python3 -m backtest.cases
```

This runs. Scroll straight to the summary table at the bottom. Do not try to show
the per-case input ledgers on camera, there is no time.

**What appears (the summary block):**

```
case                       frozen      engine said               months       grade
-----------------------------------------------------------------------------------
Nebius / DataOne, Vineland 2026-03-01  major_nonattainment_nsr   42-108       Hit
Project Jupiter (Stargate) 2026-02-01  major_nonattainment_nsr   38-99 +STOP  Hit on the
                                                                              binding constraint
xAI Colossus 1, Memphis    2024-09-01  major_psd                 15-39        Miss

Two of three flagged the mechanism that actually bound. The third is an
honest miss: the engine prices the compliant path and xAI did not take it.
```

**You say, verbatim:**

> I ran it backwards against three projects, freezing the inputs at a date before
> each one failed. On Nebius it says major nonattainment NSR and the config search
> says swap to a non-combustion design. Nebius swapped to fuel cells in May. On the
> Stargate site it returns a hard stop on the pipeline, not the plant, which is
> what actually happened. The third one it misses: xAI energised without a permit,
> and the engine only prices the legal path. **That's three cases. It's a
> demonstration that it names the right mechanism, not an out-of-sample test, and
> I'm not calling it validation.**

*(103 words. This is 34 seconds at normal pace, which is too long for the 15 second
slot.)*

**Cut to fit.** Use this version, 47 words, 17 seconds:

> Ran it backwards on three projects, inputs frozen before each one failed. It gets
> Nebius and it gets the Stargate site, and on Stargate it flags the pipeline
> rather than the plant, which is what actually bound. It misses xAI, because xAI
> energised without a permit. **Three cases. Demonstration, not validation.**

*(The bolded sentence is mandatory. Say it at normal speed, not as a throwaway.)*

---

## 1:50 – 2:00 · The map · **CAVEAT 2**

**On screen:** the national county map, held still. No zooming, no panning.

The numbers behind it, from `data/county_scores.json`, in case anyone asks: 3,222
counties scored, 3,028 major PSD, 194 major nonattainment NSR, 67 carrying a hard
stop. Fastest is Texas at 609 days. Slowest is New Jersey at 1,918.

**You say, verbatim:**

> Every US county, scored on days until legal power for a 500 megawatt plant. Three
> thousand two hundred and twenty-two of them. **County-level, so it's a screening
> layer, not a parcel answer.** Announced is not deliverable.

*(37 words, 12 seconds. The bolded clause is mandatory.)*

**End on the map. No outro card, no music sting, no "thanks for watching."**

---

## Timing check

| Beat | Words | Seconds |
|---|---|---|
| Hook | 35 | 14 |
| The gap | 45 | 16 |
| Live run | 105 | 40 |
| The act | 76 | 26 |
| Backtest (short version) | 47 | 17 |
| Map | 37 | 12 |
| **Total** | **345** | **125** |

Five seconds over. Cut "and nobody is screening for it" from the hook, and
"Analysts model the revenue" if you added it. Do not cut a caveat.

---

## The 60-second version

For a hallway, or if the form has a length cap.

> Sixteen gigawatts of US data centers were announced for 2026. About five is
> actually on the ground. The bottleneck isn't chips or money, it's the air permit
> for the power plant you build on site.
>
> Here's the thing nobody prices: which permit you need is decided by where the
> land is, not what you're building. Same five hundred megawatt gas plant. Loudoun
> County, Virginia: it's on a federal list of twenty-eight source categories, the
> county's in ozone nonattainment, Shenandoah is sixty kilometres away. Fifty-seven
> months. Put the identical plant in Ellis County, Texas: twenty months.
>
> So I built an agent that computes that pathway from an address, with every fact
> cited to its federal source. And then it does the useful part. It searches
> outward for a parcel where the same plant is faster, and it searches across
> designs at the parcel you already own. Move to Texas, save thirty-six months. Or
> stay and accept a five-thousand-hour operating cap, save thirty-nine, and give up
> thirty-nine percent of your uptime. It prices the trade instead of just finding
> it.
>
> Built on Mireye for the physical layer. Three cases in the backtest, so that
> part's a demonstration, not proof.

*(190 words, about 60 seconds at speaking pace.)*

---

## The 30-second version

> Sixteen gigawatts of data centers announced for 2026. Five on the ground. The gap
> is permits, and the specific unpriced fact is that which permit you need depends
> on where the land is, not what you're building. Same five hundred megawatt gas
> plant is fifty-seven months in Loudoun County and twenty in Ellis County, Texas.
> I built an agent that computes that from an address, cites every fact, and then
> goes and finds you a parcel or a plant design where the answer is different. It's
> for hedge funds pricing announced capacity as if it were deliverable, and for the
> site-selection teams who find out after they've bought the land.

*(103 words, about 30 seconds.)*

---

## One line, if that is all you get

> Mireye tells you whether a site is good. We tell you whether they'll let you
> switch it on.
