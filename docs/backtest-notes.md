# Backtest notes

Read this before you say anything about the backtest on camera.

## What this is not

It is not a backtest in the sense a fund means the word. n = 3. I picked the cases.
I knew the answers before I wrote the inputs. There is no out-of-sample set, no
control group, no null hypothesis, and no way to compute a hit rate that means
anything.

Three is not a sample. It is three anecdotes with the arithmetic shown.

## What a real one would require

A **point-in-time panel**: for every project in the universe, a snapshot of everything
that was knowable about it on every date, with no later information leaking backward.

Concretely, to backtest this product properly you would need, per project per week:

- The generation config **as filed at that moment** — not as built, not as amended.
  Configs change. Project Jupiter went from 41 gas turbines to 2.45 GW of fuel cells in
  four months. A panel that records only the final config has already seen the answer.
- The county's attainment designation **as of that date**. Designations move.
  Philadelphia-Wilmington-Atlantic City went Moderate → Serious effective 30 July 2024,
  which cut the NOx major-source threshold in half. Any screen run against today's Green
  Book on a 2023 project is contaminated.
- PSD increment consumption as of that date, which is a function of every permit issued
  in the area up to that date. This one is genuinely hard — increment tracking is done
  inconsistently across states and is not published as a time series anywhere.
- Every county ordinance, moratorium and zoning posture as of that date, which mostly
  exists as PDFs of meeting minutes.
- Docket state as of that date.
- And the label: did it energise on the announced date, and if not, what bound first.

That last one is the killer. The label requires knowing not just that a project slipped
but *why* — air permit vs. interconnect vs. fuel supply vs. capital vs. the tenant
walking. That is a human coding exercise across hundreds of projects, and it is
adversarial, because developers do not announce the real reason.

Building that panel is a multi-year data engineering problem. It is also the single
most common way alt-data startups die: they build a signal that works on today's data,
a fund asks for five years of point-in-time history, and the honest answer is that the
history does not exist and cannot be reconstructed. Nobody was writing it down.
`docs/build-brief.md` §11 risk 2 says this. It is right.

So: I did not build a panel in four days, and neither did anyone else in this contest.

## What this is instead

Three real projects. For each one, a freeze date before the project visibly hit the
wall. Inputs assembled only from what was in the public record on that date, each field
carrying the date it became public and the source it came from. Then the engine runs and
we compare what it said to what happened.

The claim is narrow: **from pre-failure public facts, the engine names the mechanism
that actually bound.** Not the date. The mechanism.

| case | frozen | engine said | what actually bound |
|---|---|---|---|
| Nebius / DataOne, Vineland NJ | 2026-03-01 | major nonattainment NSR, NOx 1,271 tpy against a 50 tpy Serious-ozone threshold, 1,525 tons of offsets | Air permit never issued. Combustion abandoned 20 May 2026 for Bloom fuel cells. Schedule slipped to 2027. |
| Project Jupiter, Santa Teresa NM | 2026-02-01 | major nonattainment NSR **plus a hard stop on gas reachability** (28 km to adequate supply) **plus source-aggregation risk** on the two-microgrid split | Pipeline right-of-way denied 20 Mar 2026 and again 14 Jul 2026. Turbine applications withdrawn 27 Apr 2026. |
| xAI Colossus 1, Memphis TN | 2024-09-01 | major PSD, ~26 months | Ran anyway. ~100k GPUs training inside a 122-day buildout, no CAA permit. |

Two hits and one miss, and the miss is the most useful of the three.

## Which facts are genuinely pre-failure and which are contaminated

### Nebius Vineland — mostly clean

**Genuinely pre-failure.** The engine count and 403 MW nameplate (Sierra Club, 27 Feb
2026), the site location (same), the NJDEP application under review and not granted
(same), the Serious ozone designation (30 Jul 2024), the Ozone Transport Region (1990),
the NJ EJ statute (April 2023), the Class I distance (a 1977 statutory list and a
straight-line calculation). The failure — the Bloom swap — is 20 May 2026, eighty days
after the freeze.

**Contaminated or assumed.** Emission controls were never disclosed; I assumed SCR plus
an oxidation catalyst, which is *favourable to the developer* and still lands the
project 25× over the threshold. The prime mover being lean-burn is a fact about the
Bergen product line, not a project disclosure. The Corning aggregation question broke on
21 April 2026 and is excluded — it would have given a second independent reason to
expect major-source treatment, so excluding it makes the case harder, not easier.

**The honest weakness.** I left `residential_within_1km` as `None`, so the EJ hard stop
never fires. Vineland qualifies as an overburdened community, but the DataOne lots
themselves reportedly fall just outside the OBC boundary and no headcount within 1 km
was ever published. Filling that field would have produced a much more dramatic output
and would have been me writing the answer into the input.

### Project Jupiter — clean on the mechanism, easy on one input

**Genuinely pre-failure.** The turbine count and simple-cycle type, the two-microgrid
split 1.25 miles apart, the applicant's own claimed 248.9 / 249.97 tpy NOx, and NMED's
19 December 2025 letter calling the applications incomplete and the 1.1-ton margin "not
practically enforceable" — all public by 19 December 2025. The Marginal ozone
designation dates to 30 November 2021. The freeze is 1 February 2026; the first denial
is 20 March 2026.

**The input that makes this easier than it looks.** `gas_pipeline_km = 28` comes from
Energy Transfer's own right-of-way application, filed 29 January 2026, which says
18 miles of new 24-inch pipe are needed. That is three days before the freeze, so it is
legitimately pre-failure — but it is also a number handed to me by the party whose
pipeline was about to be denied. A cold screen would have had to derive that distance
from a pipeline map. Mireye's `utilities` preset would do it, but I did not run it
retroactively, so I cannot claim I would have found the same number independently. Say
this if anyone asks.

**Modelling choice worth defending.** I ran PTE at 8760 hours with no enforceable cap.
That is not me stacking the deck — it is NMED's own finding, in writing, before the
freeze. The variant that treats the cap as enforceable at 3,400 hr/yr lands in the same
pathway anyway, so the choice does not change the answer.

**Where my numbers and theirs diverge.** The applicant claimed ~499 tpy NOx total. The
engine computes 1,277 tpy. That gap is not a bug in either. It is entirely the
enforceability question — whether the hours cap counts against potential to emit. That
is the thing NMED objected to, and it is the thing the engine is built to surface.

### xAI Memphis — knowingly contaminated, and labelled as such

The 35-turbine count and the 420 MW figure only became public through the 2025 permit
fight and aerial imagery. A genuine September 2024 screen would not have had them. This
case is an illustration of what the engine says about a config, not a test of whether it
could have predicted anything. It is in the file because it is the honest counterexample
and leaving it out would be the dishonest choice.

## What the miss actually teaches

The engine said major PSD, roughly two years. It was right about the law and wrong about
the world, because xAI took the position that trailer-mounted turbines are nonroad
engines and ran them.

**The engine prices the compliant path. It has no variable for a developer's appetite
for running unpermitted and litigating.** That is a real limitation of the product, not
of the backtest, and it is the first thing a sophisticated buyer will notice. The
correct response is that the risk did not go away — it moved. xAI now has a Shelby
County permit under appeal, a Clean Air Act suit over Colossus 2 in Southaven
Mississippi, and a preliminary injunction hearing in late August 2026. The engine's
~26-month number may turn out to have been right about the calendar and wrong about the
order of events.

One correction while we are here, because the usual telling of this story is wrong and
it is in the brief: the 15 January 2026 EPA rule did **not** close the nonroad reading.
It finalised a conditional exclusion that would *widen* it, contingent on a Title II
rulemaking that has not happened. See `docs/evidence.md` claim E1. Do not say "the
loophole closed" on camera.

## One thing that did check out independently

I assembled the attainment designations by hand from EPA and state sources before
`ingest/greenbook.py` landed. They match the ingested Green Book export
(`data/greenbook.json`, EPA export date 2026-07-31) exactly: Cumberland County NJ
Serious for 2015 ozone, Doña Ana County NM Marginal, Shelby County TN and DeSoto County
MS both absent from the nonattainment list. Two hand-built paths agreeing is not proof,
but it is the one input in this backtest I did not have to take on trust.

The cross-check also surfaced two things I would have missed and have now excluded:
Doña Ana's ozone designation is **partial-county**, and the county carries a **second**
nonattainment designation for PM10 (Anthony, NM, also partial) that I cannot confirm
covers the Santa Teresa site. Partial-county designations are the single most likely way
a screen like this returns a confident wrong answer.

## Other things that would make a judge discount this

- **The absolute timelines are not calibrated.** Vineland comes out at 42–108 months,
  likely 69. I have no evidence a real NJDEP major NA NSR takes six years. The
  *ordering* is defensible — this pathway is much longer than that pathway — the
  absolute months are a stacked model of base ranges, a state multiplier and additive
  trigger penalties that nobody has fit to observed permit durations. Present the
  pathway and the relative delta, not the month count, as the output.
- **The state multipliers are hand-set.** Eight states, from public permit records and
  agency guidance, by me, in one sitting. NJ 1.6 and TX 0.75 are directionally right and
  numerically invented.
- **Class I distances are great-circle from area centroids**, computed in the case file,
  not boundary-to-boundary and not a Mireye proximity call. Good enough to fire a
  100 km trigger; not good enough for an application.
- **Two of the three cases resolved in the same direction — toward Bloom fuel cells.**
  That is a real 2026 pattern and it is also a reason the sample is not independent.
- **I chose the freeze dates.** Moving Vineland's freeze back three months would remove
  the engine count and the case would collapse.

## The claim you are allowed to make

> On three real projects, using only facts that were public before each one hit trouble,
> the engine named the constraint that actually bound in two of them, and the third is a
> case where it was right about the law and the developer ignored the law.

## The sentence to say out loud in the video

Say this, at 1:35, before showing the result. Not after.

> "This is three cases I picked, and I already knew how they ended. It is a
> demonstration, not a backtest — a real one needs a point-in-time panel across hundreds
> of projects, and that is a multi-year data problem, not a weekend. What it does show is
> that from pre-failure public facts, the engine named the thing that actually bound:
> the ozone threshold at Vineland, the pipeline in New Mexico. And on the third one, xAI,
> it was wrong — it priced the legal path, and xAI just ran the turbines anyway."

Saying the third one was wrong is the part that buys you the first two.
