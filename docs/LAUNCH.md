# Launch material

Everything here is fact-checked against `evidence.md`. Where the original draft of a line
was wrong, the wrong version is shown struck out with the reason, because the corrected
version is usually the better line anyway.

Rule for all of it: every number is sourced, and nothing claims revenue, customers or a
raise that doesn't exist.

---

## Bio line

> Ground truth for the AI buildout. Announced ≠ deliverable.

Alternates, depending on where it sits:

> Building the credit rating for American infrastructure.

> The layer after the siting deck says yes.

---

## Launch post

```
Elon told Dwarkesh the bottleneck isn't chips or money. It's permits.

"You have to get permits. Try getting the permits for that. See what happens."

So I checked.

16 GW of US data centers announced for 2026. About 5 GW actually on the ground.
$130B of projects blocked or delayed in Q1 alone. 833 opposition groups across
49 states. Of ~90 GW of announced onsite generation, 2.2% is running.

The market prices announced capacity as if it's deliverable capacity. It isn't.

So I built Groundtruth. It works out which air permit a plant needs at that exact
parcel, checks the county's posture, pulls the court dockets, and looks at
satellite imagery for whether there's a hole in the ground yet. Every physical
fact cited to its federal source with a timestamp.

Then it does the useful part. When a site fails it searches outward and finds one
nearby that doesn't.

I scored all 3,222 US counties. Not one of them makes a 500 MW onsite gas plant a
minor permit.

Built on @mireye_ for the physical layer.

[county map]
```

The map is the visual asset. Nobody has seen it.

### If you want a second, sharper opener

```
I scored every county in America on how long it takes to legally power a 500 MW
data center.

Zero of 3,222 counties allow it as a minor permit.
The spread between the fastest and slowest is 1,309 days. Same equipment.

[map]
```

That version leads with the finding instead of the quote. It's less LARP and more
result. Test both.

---

## Corrections to the earlier draft

Post the corrected versions. Each of these would have been caught.

**Nebius.** ~~"Nebius can't get an air permit for a 400 MW plant under a $17.4 billion
Microsoft deal."~~ Stale, and present tense makes it wrong. The permit was never denied.
It stalled, and on 20 May 2026 Nebius abandoned combustion and switched to 328 MW of
Bloom fuel cells. Say it this way instead, because it's a better story:

> Nebius stalled on an air permit for 403 MW of gas engines at Vineland NJ. My config
> search, run on inputs frozen at 1 March 2026, says go non-combustion. They announced
> fuel cells 80 days later.

**The Musk hardware quote.** ~~"It's like those who have lived in software land don't
realize that they're about to have a hard lesson in hardware — that it's actually very
difficult to build power plants... the utility industry is a very slow industry. They
impedance match to the government, to the public utility commission."~~ That's three
separate sentences stitched with an ellipsis, and the wording is off. Use the third
sentence alone. It's the strongest of the three and it's exact:

> "The utility industry is a very slow industry. They pretty much impedance match to the
> government, to the Public Utility Commissions."

**The fund manager quote.** ~~"Announced capital is not deliverable capacity. Those are
different things, and the market keeps pricing them the same."~~ **This quote does not
exist.** Zero hits on the exact string, not in either article it was attributed near. It
is the best-sounding sentence in the original brief and it is the one that gets you
caught. Either say it unattributed in your own voice, which makes it a thesis:

> Announced capital is not deliverable capacity. The market prices them the same. That's
> the trade.

Or use one that's real, from Michael Shawn of Peregrine Private Client:

> "In a permit-constrained market, the winner isn't whoever spends the most. It's whoever
> already controls the land, the interconnect, and the power."

**The EPA turbine rule.** Most coverage has this backwards, including the first draft of
our own docs. The 15 January 2026 NSPS (91 Fed. Reg. 1910, subpart KKKKa) did **not**
close the nonroad-engine loophole. It finalised a *conditional* exclusion that isn't
operative, because EPA hasn't done the Title II rulemaking it depends on. Correct framing:

> Everyone reported that the January EPA rule closed the trailer-mounted turbine
> loophole. It didn't. It created a conditional exclusion that doesn't take effect until
> a rulemaking that hasn't happened. The fast path isn't closed, it's unsettled, and
> there's a federal injunction hearing this month.

That's a genuinely contrarian, checkable take. Worth its own post.

**xAI.** The 19 days is hardware-install-to-training inside a 122-day buildout, not the
whole build. And the April 2026 NAACP suit is over **Colossus 2 in Southaven,
Mississippi** (N.D. Miss.), not Memphis. Earthjustice is on the docket; SELC was on the
February notice of intent, not the complaint.

**Morgan Stanley.** Say "38 GW hole before mitigations." Their base case still leaves
1 to 11 GW short after mitigations, and someone will check.

---

## Thread follow-ups

Post over the week. Each is a standalone post with one visual.

1. **The two-county comparison.** Same 500 MW plant, Ashburn VA vs Anderson County TX.
   54 months against 20. Screenshot the decision tree from the README.
2. **The January 2026 EPA rule that everyone reported backwards.** Highest-signal post in
   the set, because it's contrarian and checkable.
3. **The county map, zoomed to one state**, with the fastest and slowest five and the
   reason for each.
4. **The alternate-site search in action.** One before and after. Include the honest part:
   moving from New Jersey to Delaware doesn't escape the Ozone Transport Region, because
   Delaware is in it too. What it escapes is New Jersey's EJ statute and state toxics
   programme.
5. **CO, not NOx.** On a 15 MW turbine with DLN and SCR fitted, the binding pollutant is
   CO at 57 tpy, because neither control touches it. An oxidation catalyst drops it under
   10. Small, specific, and the kind of thing that makes engineers trust you.

---

## LinkedIn version

Same spine, different order. Lead with **16 GW announced against ~5 GW real** rather than
the Musk quote, and move Musk to the second paragraph. End on the buyer rather than the
map. Add one line on what you learned building it.

---

## Rules

- Every number gets a source. Keep it that way.
- No claimed revenue, customers, or raise.
- Don't let the backtest carry more than three cases and one self-declared miss can bear.
- "Built on Mireye" in every post. It costs nothing and it's correct.
- If someone challenges a number, send them `docs/evidence.md`. That file exists so you
  never have to argue from memory.
