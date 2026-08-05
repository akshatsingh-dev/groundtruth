# Compute economics — engineering note

What a permit delay costs in dollars, and why every number in that chain is
where it is.

Everything below was captured on **5 August 2026** against the live Cumberland
County, NJ run: 400 MW of onsite simple-cycle generation, 300 MW of IT load,
major nonattainment NSR at 66 months likely against a 16-month announced
schedule, 53 months of negative slack.

Two files:

- `ingest/gpu_pricing.py` — what an accelerator-hour is worth today, and where
  that came from
- `agent/economics.py` — megawatts to accelerators to dollars, and the inverse

---

## 1. Pricing sources

Four sources, all queryable today with no account, no key and no card. Checked
by running them, not by reading a docs page.

| Source | Endpoint | Auth | Kind | What it gives |
|---|---|---|---|---|
| Vast.ai | `GET console.vast.ai/api/v0/bundles/?q=<json>` | none | marketplace spot | Live offer book. 31 rentable on-demand H100 SXM offers today. |
| SF Compute | `GET sfcompute.com/prices` | none | marketplace spot | 30-day daily series of **cleared** cluster prices, embedded in the page payload. |
| RunPod | `POST api.runpod.io/graphql` (`gpuTypes`) | none | published list | `securePrice` and `communityPrice` per GPU type. |
| Lambda | `GET lambda.ai/pricing` | none | published list | On-demand rate card, per GPU per hour. HTML, so the parse is the brittle part. |

Checked and not used:

| Source | Why not |
|---|---|
| Lambda API `cloud.lambdalabs.com/api/v1/instance-types` | **401 without a paid account.** The web rate card is the only keyless route to their numbers. |
| Together AI | Rate card is per-token for inference endpoints. Different unit. Not comparable to a GPU-hour. |
| Fireworks AI | Same. Per-token. |
| Vast.ai bid market | Real, and cheaper, but it is interruptible. A 300 MW campus sells uninterrupted capacity, so blending the bid book in would understate the comparison. Excluded, `type: "on-demand"` only. |

### Two kinds of price, kept apart

`marketplace_spot` is what capacity clears at. `published_list` is a posted ask.
They differ by 50% on H100 SXM today and the module never averages them into one
figure. Every quote carries its `kind`, its source, its fetch timestamp and its
derivation string.

### What the sources say, 5 Aug 2026

H100 SXM, the unit of account:

| Source | Kind | $/GPU-hr | Band | Derivation |
|---|---|---:|---|---|
| Vast.ai | marketplace spot | 2.52 | 1.73–3.07 (p25/p75) | median of 31 rentable on-demand offers, `dph_total / num_gpus` |
| SF Compute | marketplace spot | 2.27 | 2.19–2.33 (day low/high) | cleared cluster price index, daily average |
| **consolidated spot** | | **2.40** | **1.73–3.07** | median across the two sources |
| RunPod Secure | published list | 3.29 | community 2.69 | rate card |
| Lambda on-demand | published list | 3.99 | 3.99–4.29 by instance size | rate card, 8-GPU node |
| **consolidated list** | | **3.64** | **2.69–4.29** | median across the two sources |

Full coverage:

| Class | Spot $/hr | Spot band | List $/hr | Node W/GPU |
|---|---:|---|---:|---:|
| H100 SXM | 2.40 | 1.73–3.07 | 3.64 | 1,275 |
| H200 SXM | 4.21 | 3.82–4.34 | 4.59 | 1,275 |
| A100 SXM 80GB | 1.06 | 0.83–1.19 | 2.19 | 812 |
| B200 | 5.94 | 5.50–6.25 | 6.74 | 1,790 |
| H100 NVL | 2.60 | 2.40–2.80 | 3.19 | 700 |
| L40S | 0.60 | 0.47–0.80 | 0.99 | 600 |

### Known problems with these numbers

**Vast's public endpoint pages at 64 offers.** Sorted cheapest-first. A class
with more listings than that comes back truncated and its median is biased low.
The module detects the cap and says so in the derivation string. H100 SXM
returned 31 offers in both sort directions, so that class is the complete
population, not a page.

**Vast's book is thin and jumpy.** Two queries eleven minutes apart returned
medians of 2.20 and 2.52 on the same 31-offer population. That is a real
property of a retail marketplace, and it is one reason for the one-day cache
TTL: a screen re-run in the afternoon should not produce a different valuation
than the morning's.

**SF Compute is the better single number** and the module weights it equally
anyway. It is a traded average across a real order book for contiguous clusters,
which is closer to what a 300 MW campus would be selling than a retail
single-node ask. Series entries of `0` mean no trades that day, not free
compute, and are dropped — H200 and B200 have no traded series today.

**Lambda's parse is HTML.** It will break when they redesign the page. It fails
to a missing source and a note, not an exception.

### Cache and offline

Everything goes through `providers/cache.py` at a **one-day TTL**. Rates move
daily, not hourly. A cache hit carries the original fetch timestamp forward, so
a replayed mark is never stamped with `now()`.

With no network, the module falls back to a dated table captured from these same
endpoints on 5 Aug 2026. Every fallback figure is flagged `stale=true`, the
table's `basis` reads `fallback`, and the valuation headline changes from "at
today's spot rate" to "at the 2026-08-05 reference rate". There is a circuit
breaker: after two transport failures it stops dialling, so a machine with no
network gets an answer immediately rather than 24 seconds of connect timeouts.

`GPU_PRICING_OFFLINE=1` forces the fallback path without touching the network.

---

## 2. The arithmetic chain

Cumberland, 400 MW plant, 300 MW IT load, 53.1 months of delay, priced in
H100 SXM.

```
PUE           = 400 MW generation / 300 MW IT load          = 1.33
Accelerators  = 300 MW x 1,000 kW/MW / 1.275 kW per GPU     = 235,294
Delayed hours = 53.1 months x 730 hr/month                  = 38,763 hr
GPU-hours     = 235,294 x 38,763                            = 9.12e9
Billable      = 9.12e9 x 80% utilisation                    = 7.30e9
Foregone      = 7.30e9 x $2.40/GPU-hr                       = $17.5B
Per month     = $17.5B / 53.1                               = $329M
```

Range: **$8.8B to $29.3B**, likely **$17.5B**. Per month **$165M to $551M**,
likely **$329M**.

### Every assumption and its basis

| Assumption | Value | Basis |
|---|---|---|
| PUE | 1.33, **derived** | 400 MW of generation stated for a 300 MW IT load. Not assumed — it is the ratio the project itself implies. Where a project states only a plant size, the module assumes 1.30 and flags the IT load as derived. |
| Power per accelerator | 1,275 W at the server, 700 W at the board | NVIDIA DGX H100 datasheet: 10.2 kW maximum system power for 8 GPUs. The gap between 700 and 1,275 is host CPU, DRAM, NICs, NVSwitch and PSU losses. |
| Cooling and facility overhead | **not** in the 1,275 W figure | It is on the other side of PUE. Counting it in both places overstates power per GPU by ~30% and understates the accelerator count by the same. This is the single easiest way to get this arithmetic wrong. |
| Accelerator count margin | ×1.08 to ×0.88 on node watts | Low count carries an 8% design margin, which is how a hall is actually sized. High count assumes sustained training draw at 88% of datasheet maximum. |
| Hours per month | 730.0 | 8,760/12, so it reconciles with the PTE math, which is all built on an 8,760-hour year. |
| Utilisation | 60 / 80 / 92% | 60% is a merchant fleet that has not filled. 80% is committed tenants with normal churn, node failure and reprovisioning. 92% is effectively pre-sold with a maintenance floor. 100% is not reachable. |
| Rate | $2.40/GPU-hr, band 1.73–3.07 | Median across Vast.ai and SF Compute marketplace spot. Never blended with the $3.64 list rate. |
| Sole power source | yes | Read off `Project.grid_tied`, which the Cumberland run sets to `False`. The plant is behind-the-meter primary power, so the air permit blocks the whole IT load. |
| Delay | 53.1 months | Negative slack against the announced energization date, not the pathway duration. A project with a realistic schedule has a long pathway and no delay. |
| GPU class | H100 SXM | The market's unit of account. B200 would give a different count and a different rate; the module supports six classes. |

---

## 3. The counterfactual, stated plainly

**The capacity would have been energised on the announced date, filled with
H100-class accelerators, and sold at spot at 80% utilisation for all 53 delayed
months.**

That is generous, in four specific ways:

1. It assumes a buyer at spot for the whole period. 235,000 accelerators is a
   large fraction of the entire public spot market. A fleet that size does not
   clear at the price it was quoted before it entered — it is the price.
2. It assumes the accelerators were procured and installed on the same schedule
   as the power. In practice GPU allocation, transformers and the building are
   separate critical paths and any of them can bind first.
3. It assumes the air permit is the binding constraint. This repo's own README
   says turbine delivery, construction and interconnection are not modelled.
4. It treats deferred revenue as lost revenue. The project still gets built,
   later. This is the value of the option to start earlier, undiscounted.

**It is an opportunity cost, not a cash loss.** A real operator on a contracted
lease has a different and usually smaller number, because a lease trades price
for certainty. The module prices that case separately whenever a reference
contract exists for the site: at the Nebius/Microsoft implied rate of $11.6M per
MW-year, the same 53 months is **$15.4B** rather than $17.5B. That is the
conservative mark and it is the one to quote to a developer.

**It is a mark at today's rate, not a forecast.** H100 spot traded 2.04 → 2.27
on the SF Compute cleared index over the 31 days to 5 Aug 2026, up 11%. Over the
longer run it has fallen hard from launch-scarcity levels. A rate that moves 11%
in a month is not a rate you extrapolate 53 months. The output never describes
the total as an expected value, and the headline says "at today's spot rate"
explicitly.

**It does not double count.** `plant_share_of_it_load` is the guard. If the
campus is grid-connected and the onsite plant is firming rather than the sole
source, the air permit is not blocking the whole IT load. The module reads
`Project.grid_tied` and, when the plant is not the sole source and no share was
supplied, labels the figure an upper bound rather than quietly claiming the full
load. At a 35% share the Cumberland number falls from $17.5B to $5.8B.

---

## 4. Sensitivity

$B foregone over 53.1 months at 235,294 accelerators. Rows are utilisation,
columns are $/GPU-hour.

| util \ rate | $1.73 | $2.00 | $2.27 | **$2.40** | $3.07 | $3.64 |
|---|---:|---:|---:|---:|---:|---:|
| 60% | 9.5 | 10.9 | 12.4 | 13.1 | 16.8 | 19.9 |
| 70% | 11.0 | 12.8 | 14.5 | 15.3 | 19.6 | 23.2 |
| **80%** | 12.6 | 14.6 | 16.6 | **17.5** | 22.4 | 26.6 |
| 92% | 14.5 | 16.8 | 19.0 | 20.1 | 25.8 | 30.5 |

`$1.73` is the Vast p25, `$2.27` the SF Compute cleared index, `$2.40` the
consolidated spot mark, `$3.07` the Vast p75, `$3.64` the consolidated published
list rate. The list-rate column is shown for scale and is not part of the range.

Rate is the widest driver: the observed spot band alone spans 1.8x. Utilisation
spans 1.5x. Together they are a 2.7x range before any view on the future.

Watts per accelerator is the third axis and the one nobody argues about, which
is why it is worth showing:

| Node W/GPU | Accelerators at 300 MW | Likely $B |
|---:|---:|---:|
| 1,100 | 272,727 | 20.3 |
| **1,275** | **235,294** | **17.5** |
| 1,400 | 214,285 | 15.9 |
| 1,800 (B200 class) | 166,666 | 12.4 |

A 10% error in watts per accelerator is a 10% error in the answer. That is why
the figure is a datasheet citation and not a round number.

---

## 5. Cross-check against the $17.4B Microsoft deal

The Cumberland site sits under a reported **$17.4B, five-year Nebius/Microsoft
capacity agreement for 300 MW of IT load** (docs/evidence.md claim E12). That
implies **$11.6M per MW-year**.

The spot counterfactual implies **$13.2M per MW-year**, a ratio of **1.14x**.

That holds, and it holds in the right direction. Spot should price above a
five-year take-or-pay lease, because a lease buys certainty at a discount. A
14% premium is the right magnitude for that discount. If the ratio came back at
10x or 0.1x, something in the chain above would be wrong — most likely watts per
accelerator, or plant nameplate substituted for IT load — and the module's
`cross_check.verdict` says `FAILS` outside a 0.33x–3.0x band rather than
shipping the number.

The totals line up too, for a reason worth stating: 53 months at a 14% premium
is arithmetically close to 60 months at the contract rate. $17.5B of foregone
spot revenue against a $17.4B five-year contract is not a coincidence and it is
not a fit — it is what falls out when the delay is 53 of the contract's 60
months.

**The high case does not pass this check and is labelled accordingly.** $29.3B
implies $22.0M per MW-year, **1.9x** the signed rate. That is the 75th percentile
of a thin retail offer book applied to 267,000 accelerators. A fleet that size
would move the price it was selling into long before it got there. The high case
is a bound on the arithmetic, not a scenario anyone should underwrite.

---

## 6. The inverse, and the cost of being wrong

**One month of permit delay at Cumberland is worth $329M** ($165M to $551M).
That is the number a developer acts on, because it does not require guessing how
long the delay runs.

`cost_of_being_wrong()` prices discovering the problem at month 9 instead of
before optioning the land, using the brief's own figures (§4, buyer 2: one wrong
site is tens of millions in options, engineering and legal, plus 18 to 36
months):

| | |
|---|---:|
| Sunk capital, unrecoverable | $10M – $60M, likely $30M |
| Months lost (9 burned + 18–36 to re-site) | 27 – 45 |
| Schedule opportunity cost | $11.9B likely |
| **Total** | **$11.9B** |
| Screen cost before optioning | $10k – $25k |

The sunk capital is the number a developer thinks about. The schedule is
**~400x** larger and is the number that decides whether the project still makes
sense. The sunk capital is destroyed; the schedule cost is deferred and
undiscounted, so read it as the value of the option to start earlier. That is
what the screen actually sells.

---

## 7. What recovers it

This is why the number is a cost of not looking rather than a fact.

At Cumberland the config search finds solid oxide fuel cells: minor NSR, 21.6
months, **44 months saved**. Against $329M per month that recovers **$14.5B** of
the $17.5B. The option was available on day one.

That is not hypothetical. Nebius made exactly that substitution at this site on
20 May 2026 — 328 MW of Bloom fuel cells — 80 days after the date the inputs
here were frozen at. The counterfactual "no compute for 53 months" is falsified
in this specific case, by the developer, eight months in. The screen's value is
naming the alternative on day one instead.

The alternate-site search reports the same way when it finds a better parcel.
Land, fiber and interconnection at the alternate parcel are not priced here.

---

## 8. What would make this rigorous

In rough order of how much it would move the answer.

1. **The IT load is not an input to the project model.** Today it is derived from
   plant nameplate over an assumed PUE unless a caller supplies it, and that is a
   ±15% error on every dollar figure. The Cumberland case gets 308 MW derived
   against a real 300 MW. `Project` needs an `it_load_mw` field.
2. **Accelerator mix.** Every campus is priced as a single GPU class. Real
   fleets are mixed and the mix shifts across a 53-month window, from H100 to
   B200 to whatever ships in 2029. Pricing a four-year delay in today's silicon
   is an approximation nobody has a good answer for.
3. **A forward curve.** Spot is a mark. A defensible multi-year number needs a
   term structure, and SF Compute's reservation market is the closest public
   thing to one. Their page carries a 30-day history; the term curve is not in
   the public payload.
4. **Contracted lease rates at scale.** One reference contract is not a
   benchmark. Ten public capacity agreements with a stated IT load would turn the
   cross-check from a sanity test into a comparables set, and would let the
   module quote a contracted number as the default rather than as an aside.
5. **Ramp.** A 300 MW campus does not energise all at once. Revenue ramps over
   12–24 months, so the first months of a delay are worth less than the last.
   The module treats the delay as a flat block, which overstates the early
   months.
6. **The other critical paths.** The delay is priced as if the air permit were
   the only thing standing between the site and revenue. Turbine lead times,
   transformer lead times and interconnection queues all bind, and where one of
   them binds later than the permit the permit delay is worth nothing at the
   margin. Pricing the permit alone is only correct when it is the binding
   constraint, and this module does not verify that it is.
7. **Discounting.** Deferred revenue over four years should be discounted.
   Nothing here is.
8. **Sample depth on the spot side.** 31 offers on the deepest class, with a
   64-row page cap on the endpoint. A paid Vast.ai or SF Compute account, or a
   scrape of several marketplaces at a fixed daily time, would give a mark worth
   putting in a report rather than one worth putting in a screen.
