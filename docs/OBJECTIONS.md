# Objections

Fifteen questions a judge or a Mireye engineer could ask. Each answer is under 30
seconds spoken, roughly 75 words. Where the honest answer is "I don't know yet,"
it says so, because the framing that makes it a strength is the true one.

Rule for all fifteen: answer the question asked, then stop. Do not fill silence
with a second version of the same answer.

---

## 1. How is this different from Sightline Climate or Data Center Watch?

They track. I compute.

Sightline and Data Center Watch tell you a project was announced, and later that it
was delayed or cancelled. Neither of them works out which permit the plant needs at
that specific parcel, and neither searches for a parcel where the answer is
different. That is the whole product. If they add it, I lose the wedge, and I would
rather say that out loud than pretend the space is empty.

**If pushed:** "They'd be a distribution partner before they'd be a competitor. I
compute a field they'd want in their feed."

---

## 2. Your backtest is three cases. That is not a backtest.

Correct. It is a demonstration and I call it one in the video.

Three cases cannot validate a model. What they can do is show the engine fires on
the right *mechanism*, not just the right outcome. On the Stargate site it returns a
hard stop on the gas pipeline rather than the air permit, and the pipeline
right-of-way is exactly what got denied. On Nebius the config search says go
non-combustion, and Nebius switched to fuel cells in May 2026. And one of the three
is a miss, which is in the output.

**If pushed:** "Each case freezes its inputs at a date before the failure and lists
which facts I deliberately kept out, so you can check I did not feed it the answer.
The real validation is a panel of issued permits with their application dates. That
is a data acquisition problem and the first thing I'd do with a month."

---

## 3. A licensed engineer has to sign this. So what are you actually selling?

The screen, not the opinion.

A licensed professional stamps a permit applicability determination and carries the
liability. I am not trying to replace that and I could not. What I am selling is the
decision that happens 18 months earlier: which of these forty parcels do we pay a
consultant to look at. That decision is made today on power, fibre and price, with
no air permit input at all.

**If pushed:** "It also means the consultancies are a channel rather than a
competitor. They keep the billable interpretation and buy the screen. That is a
better business than fighting them."

---

## 4. How much of this is just Mireye's own data center siting preset?

None of the part that decides the answer.

Their preset tells you whether a site is *good*: slope, flood, transmission
distance, queue position. Ninety fields, and I use it. But it stops where my
question starts. It does not know the county's attainment status, it does not know
what the plant's potential to emit is, and it cannot tell you which permit that
combination produces. This is the layer immediately after their API already said
yes.

**If pushed:** "Mireye is the physical substrate. The regulatory decision tree is
1,000 lines of my code and it would work over any provider that answers the same
interface."

---

## 5. What happens when your hardcoded county file goes stale?

It goes stale, and the output says which fields are hand-entered.

Twenty counties, entered by hand, because a scraper for county moratoria was not
worth six hours in a four-day build and would have been less accurate. Every
trigger that comes from that file cites `ingest/counties.json` in the output, so a
user can see exactly which claims are hand-maintained. The right fix is a
field-request to Mireye, or a monthly re-check, not a scraper.

**If pushed:** "The air permit layer, which is the part that matters, comes from the
EPA Green Book and the CFR. Those move on a published schedule, not on a county
board vote."

---

## 6. You modelled 8 states. What about the other 42?

They get a federal default, and the engine says so in its own output.

`FEDERAL_DEFAULT_OVERLAY` is a 1.0x multiplier with a note that reads "This state is
not one of the eight modelled in detail. Treat the range as wider than shown." That
note appears in the result. The federal decision tree, which is most of the answer,
is national. What is missing for the other 42 is the state agency's speed and its
state-specific toxics and modelling rules.

**If pushed:** "Adding a state is about two hours of reading permit records and one
dictionary entry. It's a data problem with a known unit cost, which is the good kind
of gap."

---

## 7. Did you validate your emission factors against a real permit application?

No. I validated them against AP-42, which is what a permit application uses as its
starting point.

Every factor in the module carries its AP-42 table number. The controlled NOx rate
it produces for a combined-cycle plant, 0.0099 lb/MMBtu after dry low-NOx and SCR,
sits at the tight end of what current BACT determinations achieve. So it is in the
right place. But I have not reconciled a full run against an issued permit, and I
would not claim I have.

**If pushed:** "The known weak spot is carbon monoxide. The uncontrolled AP-42
factor is high relative to modern permitted combined-cycle plants. With an
oxidation catalyst it lands at 122 tons a year, which is defensible. Without one,
the model overstates it."

---

## 8. Why should we believe your timeline model?

Believe the ordering. Do not believe the point estimate.

It is an additive model. Base range per pathway, a state multiplier, and a fixed
number of months per trigger that fired. The triggers do not interact and nothing
caps the total. The base ranges come from agency guidance and observed permit
histories, not from a regression, because there is no public permit-outcome dataset
at parcel resolution to regress against.

**If pushed:** "So the claim is: Loudoun is worse than Mecklenburg is worse than
Ellis, and every reason is individually citable. The claim is not that Loudoun is
57 months rather than 48 or 70."

---

## 9. Is this actually an agent, or a decision tree with an LLM on top?

The decision tree is the part that should be deterministic. The agent is the part
around it.

A permit applicability determination should give the same answer every time it is
run on the same facts. Making that stochastic would be a bug. What is agentic is
the query planning, which Mireye calls to make depends on what the pathway question
needs, and the two search loops in `agent/search.py`, which decide where to look
next based on what came back.

**If pushed, and honestly:** "Ask me which parts ran unattended in the video and I
will tell you exactly. I'd rather do that than have you find out."

---

## 10. Your headline says "move 22 miles, minor NSR instead of PSD." Your own engine never produces that at 500 megawatts.

You are right, and I changed the claim.

At 500 megawatts, NOx comes out at 148 tons a year, which is over the 100 ton
threshold everywhere in the country. So no relocation makes a 500 MW combined-cycle
plant a minor source. The real result is major nonattainment NSR to major PSD, 57
months to 20. That is a bigger saving than the one I originally wrote down. Minor
NSR shows up at 300 megawatts and below, or with a fuel cell, or under an
enforceable hour cap.

**This is a good question to get.** It means someone read the code.

---

## 11. What is your moat? Anyone can read 40 CFR 52.21.

The regulations are public. The assembly is not, and neither is the ground truth.

Three things are hard to copy. The state agency behaviour model, which is
observation, not law. The connection between a parcel's physical facts and the
regulatory trigger they fire, which is where Mireye is doing work nobody else can
easily replicate. And, eventually, the panel of outcomes over time, which compounds
and which is the actual defensible asset.

**If pushed:** "Honestly, the four-day moat is thin. The two-year moat is the
outcome panel. I would say that to an investor too."

---

## 12. Alt data buyers want years of point-in-time history. You have four days.

That is the main reason alt-data startups die, and I am not pretending otherwise.

A hedge fund wants to backtest a signal across cycles. I cannot give them that
today and building it is a multi-year data engineering problem. Which is why the
first revenue is not the fund subscription. It is per-site reports to developers at
ten to twenty-five thousand dollars, where the buyer needs one answer now and does
not care about history.

**If pushed:** "The panel builds itself if the per-site business exists. Every screen
I run is a dated observation. That is the sequencing."

---

## 13. Why wouldn't a developer's own consultant already know this?

They would, for the parcel you paid them to look at.

Trinity or ERM will give you a correct answer for one site, on a consulting
engagement, on a consulting timeline. Nobody commissions that for forty candidate
parcels before an option is signed, because the study bill exceeds the option cost.
So the screen never happens and the site gets picked on power, fibre and price. The
gap is not expertise. It is unit economics.

**If pushed:** "That is also exactly why they'd buy it rather than fight it."

---

## 14. Permits are issued against parcels. Your map is county-level. Isn't that misleading?

It is a screening layer and I say that on camera. The JSON says it too, in a field
called `resolution_note`.

Attainment designation is genuinely county-level or area-level, so that part is
correct at county resolution. What is not county-level is increment consumption,
Class I distance, terrain and pipeline reachability, which vary within a county and
can flip the answer. The sweep also flags 90 counties that are only *partly* in a
nonattainment area, which is precisely where a county-level screen goes wrong. So
the map narrows 3,222 counties to a shortlist. The parcel run is the answer.

**If pushed:** "If I fixed one thing first it would be running the engine at parcel
resolution across a shortlist rather than at county interior points."

---

## 15. What is the hardest thing you have not solved?

Increment consumption at parcel resolution.

Attainment status is a lookup. Class I distance is geometry. But how much of the
PSD increment is actually left in a specific area requires reconstructing every
permit issued since the baseline date in that area, and states track it
inconsistently and mostly not in machine-readable form. Right now that field comes
in as a number I supply. Making it real is the hardest data problem in the product.

**If pushed:** "It is also the highest-value field, because it is the one that turns
a clean county into a closed one, and almost nobody screens for it."

---

## Three things not to say

**Do not say "comprehensive."** The state coverage is 8 of 50 and the backtest is 3.

**Do not say the search loop is fully autonomous** unless it is by the time you
record. Say what is scripted.

**Do not defend a number you cannot trace.** If someone asks where a figure came
from and you do not know, say "that one comes out of the emissions module, let me
pull the citation" rather than guessing. Every number in the engine has a citation
attached. Use that.
