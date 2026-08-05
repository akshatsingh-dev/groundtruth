# Objections

Eighteen questions a judge or a Mireye engineer could ask. Each answer is under 30
seconds spoken, roughly 75 words. Where the honest answer is "I don't know yet," it
says so, because the framing that makes it a strength is the true one.

Rule for all eighteen: answer the question asked, then stop. Don't fill silence with a
second version of the same answer.

---

## 1. How is this different from Sightline Climate or Data Center Watch?

They track. I compute.

Sightline and Data Center Watch tell you a project was announced, and later that it was
delayed or cancelled. Neither works out which permit the plant needs at that specific
parcel, and neither searches for a parcel where the answer is different. That's the
whole product. If they add it I lose the wedge, and I'd rather say that out loud than
pretend the space is empty.

**If pushed:** "They'd be a distribution partner before they'd be a competitor. I
compute a field they'd want in their feed."

---

## 2. Your backtest is three cases. That is not a backtest.

Correct. It's a demonstration and I call it one in the video.

Three cases can't validate a model. What they can do is show the engine fires on the
right *mechanism*, not just the right outcome. On the Stargate site it returns a hard
stop on the gas pipeline rather than the air permit, and the pipeline right-of-way is
exactly what got denied, twice. On Nebius the config search names fuel cells, and
Nebius switched to Bloom fuel cells on 20 May 2026, eighty days after the freeze date.
The third case is a miss and the output says so.

**If pushed:** "Each case freezes its inputs at a date before the failure and lists
which facts I deliberately kept out, so you can check I didn't feed it the answer. The
real validation is a panel of issued permits with their application dates. That's a
data acquisition problem and the first thing I'd do with a month."

---

## 3. A licensed engineer has to sign this. So what are you actually selling?

The screen, not the opinion.

A licensed professional stamps a permit applicability determination and carries the
liability. I'm not trying to replace that and I couldn't. I'm selling the decision that
happens 18 months earlier: which of these forty parcels do we pay a consultant to look
at. That decision is made today on power, fibre and price, with no air permit input at
all.

**If pushed:** "It also means the consultancies are a channel rather than a competitor.
They keep the billable interpretation and buy the screen."

---

## 4. How much of this is just Mireye's own data center siting preset?

None of the part that decides the answer.

Their preset tells you whether a site is *good*: slope, flood, transmission distance,
queue position. Ninety fields, and I use it. But it stops where my question starts. It
doesn't know the county's attainment status, it doesn't know the plant's potential to
emit, and it can't tell you which permit that combination produces. This is the layer
immediately after their API already said yes.

**If pushed:** "Mireye is the physical substrate. The regulatory decision tree is
`agent/pathway.py`, about 1,100 lines, and it'd work over any provider that answers the
same interface."

---

## 5. What happens when your hardcoded county file goes stale?

It goes stale, and the output says which fields are hand-entered.

Twenty-seven county records, entered by hand, because a scraper for county moratoria
wasn't worth six hours in a four-day build and would have been less accurate. The file
says so in its own header: chosen for signal, not for national coverage. Every trigger
that comes from it cites `ingest/counties.json` in the output. Anything not in the file
falls back to "no county-level blocker known," which is an absence of evidence and is
labelled as one.

**If pushed:** "The air permit layer comes from the EPA Green Book and the CFR. Those
move on a published schedule, not on a county board vote."

---

## 6. You modelled 8 states. What about the other 42?

They get a federal default, and the engine says so in its own output.

`FEDERAL_DEFAULT_OVERLAY` is a 1.0x multiplier with a note that reads "This state is not
one of the eight modelled in detail. Treat the range as wider than shown." That note
appears in the result. The federal decision tree, which is most of the answer, is
national. What's missing for the other 42 is the state agency's speed and its
state-specific toxics and modelling rules.

**If pushed:** "One thing that is *not* state-modelled and still applies everywhere it
should: the Ozone Transport Region. That's statutory, it covers twelve states plus DC
and nine Northern Virginia jurisdictions, and it fires in 256 counties whether or not I
modelled the agency."

---

## 7. Did you validate your emission factors against a real permit application?

No. I validated them against AP-42, which is what a permit application uses as its
starting point.

Every factor in the module carries its AP-42 table number. The controlled NOx rate it
produces for a combined-cycle plant, 0.0099 lb/MMBtu after dry low-NOx and SCR, sits at
the tight end of what current BACT determinations achieve. So it's in the right place.
I haven't reconciled a full run against an issued permit and I won't claim I have.

**If pushed:** "The known weak spot is carbon monoxide. The uncontrolled AP-42 factor
is high relative to modern permitted combined-cycle plants. With an oxidation catalyst
it lands at 122 tons a year, which is defensible. Without one it's 1,221 and the model
overstates it."

---

## 8. Why should we believe your timeline model?

Believe the ordering. Don't believe the point estimate.

It's additive. Base range per pathway, a state multiplier, and a fixed number of months
per trigger that fired. The triggers don't interact and nothing caps the total. The base
ranges come from agency guidance and observed permit histories, not from a regression,
because there's no public permit-outcome dataset at parcel resolution to regress
against.

**If pushed:** "So the claim is: Loudoun is worse than Mecklenburg is worse than
Brewster, and every reason is individually citable. The claim is not that Loudoun is
54.5 months rather than 45 or 70."

---

## 9. Is this actually an agent, or a decision tree with an LLM on top?

The decision tree is the part that should be deterministic. The agent is the part
around it.

A permit applicability determination should give the same answer every time it runs on
the same facts. Making that stochastic would be a bug. What's agentic is the query
planning, which Mireye calls to make depends on what the pathway question needs, and
the two search loops in `agent/search.py`, which decide where to look next based on
what came back. The demo run made 13 tool calls and spent 94 credits, and the whole
sequence is in `outputs/demo/trace.json`.

**If pushed:** "Ask me which parts ran unattended in the video and I'll tell you
exactly. I'd rather do that than have you find out."

---

## 10. Your headline says "move 22 miles, minor NSR instead of PSD." Your own engine never produces that at 500 megawatts.

You're right, and the claim is gone.

At 500 megawatts with full controls, NOx comes out at 147.7 tons a year. That's over the
100 ton List-of-28 threshold in every county in the country. The national sweep proves
it: 3,222 counties, 2,843 major PSD, 379 major nonattainment NSR, zero minor. So no
relocation makes a 500 MW combined-cycle plant a minor source. The real result is major
nonattainment NSR to major PSD, 48.5 months in Loudoun to 20 in Brewster County, Texas.
Bigger than the saving I originally wrote down.

**This is a good question to get.** It means someone read the code.

---

## 11. What is your moat? Anyone can read 40 CFR 52.21.

The regulations are public. The assembly isn't, and neither is the ground truth.

Three things are hard to copy. The state agency behaviour model, which is observation,
not law. The connection between a parcel's physical facts and the regulatory trigger
they fire, which is where Mireye is doing work nobody else can easily replicate. And
eventually the panel of outcomes over time, which compounds.

**If pushed:** "Honestly, the four-day moat is thin. The two-year moat is the outcome
panel. I'd say that to an investor too."

---

## 12. Alt data buyers want years of point-in-time history. You have four days.

That's the main reason alt-data startups die and I'm not pretending otherwise.

A hedge fund wants to backtest a signal across cycles. I can't give them that today and
building it is a multi-year data engineering problem. Which is why the first revenue
isn't the fund subscription. It's per-site reports to developers at ten to twenty-five
thousand dollars, where the buyer needs one answer now and doesn't care about history.

**If pushed:** "The panel builds itself if the per-site business exists. Every screen I
run is a dated observation."

---

## 13. Why wouldn't a developer's own consultant already know this?

They would, for the parcel you paid them to look at.

Trinity or ERM will give you a correct answer for one site, on a consulting engagement,
on a consulting timeline. Nobody commissions that for forty candidate parcels before an
option is signed, because the study bill exceeds the option cost. So the screen never
happens and the site gets picked on power, fibre and price. The gap isn't expertise.
It's unit economics.

**If pushed:** "Which is also why they'd buy it rather than fight it."

---

## 14. Permits are issued against parcels. Your map is county-level. Isn't that misleading?

It's a screening layer and I say that on camera. The JSON says it too, in a field called
`resolution_note`.

Attainment designation is genuinely county-level or area-level, so that part is correct
at county resolution. What isn't county-level is increment consumption, Class I
distance, terrain and pipeline reachability, all of which vary inside a county and can
flip the answer. The sweep also flags 91 counties that are only *partly* in a
nonattainment area, which is precisely where a county-level screen goes wrong. The map
narrows 3,222 counties to a shortlist. The parcel run is the answer.

**If pushed:** "If I fixed one thing first it'd be running the engine at parcel
resolution across a shortlist rather than at county interior points."

---

## 15. What is the hardest thing you have not solved?

Increment consumption at parcel resolution.

Attainment status is a lookup. Class I distance is geometry. But how much of the PSD
increment is actually left in a specific area requires reconstructing every permit
issued since the baseline date there, and states track it inconsistently and mostly not
in machine-readable form. Right now that field comes in as a number I supply. Making it
real is the hardest data problem in the product.

**If pushed:** "It's also the highest-value field, because it's the one that turns a
clean county into a closed one, and almost nobody screens for it."

---

## 16. Your own docs said the EPA rule closed the loophole. Now they say the opposite. Which is it?

The opposite. The old version was wrong and I fixed it in the engine, not just in the
prose.

On 15 January 2026 EPA published a new NSPS for stationary combustion turbines, 91 Fed.
Reg. 1910, creating subpart KKKKa. I originally wrote that it closed the "nonroad
engine" reading that let xAI energise trailer-mounted turbines without a construction
permit. It does the reverse in direction. It finalises a **conditional exclusion**
taking turbines out of the stationary definition where they qualify as nonroad engines
and are certified under Title II. That exclusion isn't operative, because EPA hasn't
adopted Title II standards for portable turbines and that's a separate rulemaking.

So the fast path is unsettled, not closed. Which is the more interesting answer anyway.
The NAACP is asking a federal court in Mississippi to shut down 27 unpermitted turbines
at xAI's Colossus 2, with a preliminary injunction hearing set for late August 2026.
Anyone underwriting a trailer-mounted fast path today is underwriting an open legal
question.

**If pushed:** "Read the trigger text in the output. It says all of that, and its
citation names the rule, the new subpart and the case. I'd rather ship the correction
than ship the sentence that sounded better."

---

## 17. You moved the project to Delaware, and Delaware is in the same transport region. So what did you actually save?

New Jersey's state-specific stack. Not the transport region, and I don't claim it.

Both counties sit inside the Ozone Transport Region under CAA 184, so the 50 tpy NOx
threshold follows the project across the river. New Castle County is still major
nonattainment NSR. What clears is New Jersey's environmental justice denial authority
under N.J.S.A. 13:1D-157, which lets NJDEP refuse a permit outright regardless of the
modelling, and New Jersey's state air toxics programme. That's 24 months, 66 down to
42, and the report names the two triggers it cleared rather than just showing a smaller
number.

**If pushed:** "This is a fix, not a feature. The old engine attached the OTR only to
the eight states I'd modelled in detail, which made moves like New Jersey to
Pennsylvania look like escapes. They aren't. The region is now attached to all twelve
states plus DC and the nine Northern Virginia jurisdictions, and it fires in 256
counties. The search stopped selling a saving that doesn't exist."

---

## 18. You say no county in America allows a minor permit at 500 MW. Isn't that just an argument against building at 500 MW?

Partly yes, and that's a finding, not a dodge.

The 3,222-county result says the question is never "can I avoid major review at 500
megawatts." It's "which flavour of major review, and how many months," and that answer
runs from 609 days to 1,918 depending on the county and the agency. Below 340 megawatts
with full controls in a clean county, minor NSR opens up. So one real output of this
tool is: don't build one 500 MW block if the schedule matters more than the site
consolidation.

**If pushed:** "That's the config search doing its job. It found the same thing three
ways at the Vineland parcel. Drop the size, switch to fuel cells, or accept an
enforceable hour cap. Only one of the three is commercially real for a data center, and
the engine prices all three instead of just naming them. The hour cap at Ashburn is
5,337 hours, which is 61% availability, and the function's own text says a plant can't
serve baseload at that cap."

---

## Three things not to say

**Don't say "comprehensive."** State coverage is 8 of 50 and the backtest is 3.

**Don't say the search loop is fully autonomous** unless it is by the time you record.
Say what's scripted. The demo run's 13 tool calls are in `outputs/demo/trace.json` in
order.

**Don't defend a number you can't trace.** If someone asks where a figure came from and
you don't know, say "that one comes out of the emissions module, let me pull the
citation" rather than guessing. Every number in the engine has a citation attached.
