# Mireye Build Challenge — what we are entering

**Deadline: 10 August 2026. Winners announced 15 August 2026.**
Today is 5 August 2026 (Wednesday). Submit Monday morning.

## The ask, verbatim

> Combine Mireye with something weird. Solve a real problem. Show us someone would pay for it.

**Prizes**

| Place | Prize |
|---|---|
| 1st | **Internship at Mireye** — this is what we are going for |
| 2nd | $2,500 (2.5M credits) |
| 3rd | $2,000 (2M credits) |
| 4th | $1,700 (1.7M credits) |
| 5th | $1,400 (1.4M credits) |
| 6th | $1,100 (1.1M credits) |
| 7th | $800 (800k credits) |
| 8th | $500 (500k credits) |

**What they give:** APIs + an MCP server for the physical world. Any US address or
coordinate, hundreds of cited facts — terrain, hazards, power, water, soil,
buildings, land. Every value returns with `source` and a timestamp, "so what you
build can show its work."

## The one hard rule

> We want agents — things that **reason, decide, and act** on physical-world data.
> Not a website with a map on it.

Our answer to "act": the alternate-site search and the config search. It does not
stop at a report. It goes and finds a parcel where the answer changes, and a
generation config that flips the permit pathway. See `agent/search.py`.

## Judging criteria

1. **What did you combine us with?** Their examples: court filings, permit databases,
   satellite imagery, ship tracking, eBird, spot GPU pricing, tax-delinquency rolls,
   local news. "Mireye is one input — the interesting part is what sits next to it."
   → We hit **court filings** (CourtListener/RECAP) and **permit databases**
   (EPA Green Book nonattainment + Title V/NEI major sources) — examples 1 and 2 on
   their own list.
2. **Is it a real problem?** "Someone loses money, time or health today because this
   doesn't exist." → Nebius: 400 MW onsite gas plant, no air permit, under a $17.4B
   Microsoft deal. New Mexico blocked the pipeline feeding a 2.45 GW Stargate site.
   $130B of projects blocked in Q1 2026 alone.
3. **Who writes the cheque?** "'Developers might like this' is not a buyer." → Hedge
   funds long GEV/Vertiv/Bloom/Constellation ($50k–500k/yr alt data), hyperscaler and
   colo site-selection teams ($250k–1M/yr, or $10–25k per site report), air permitting
   consultancies (Trinity, ERM, Onterris) as a channel, infra lenders.

**"If it would fit in our marketing deck, pick something else."**
Their deck screens whether a site is *good* — slope, flood, 345 kV, queue position.
We screen whether they will **let you switch it on**. That is the layer immediately
after their API already said yes. Lead every piece of copy with that sentence.

## Getting started (account)

- Sign up with code `BUILD` → free Build tier for one month: https://www.mireye.com/account
- Nine starter skills: https://www.mireye.com/templates
- More credits: email **founders@mireye.com** — "we'd rather you had room to work."
  Our ask is real: national county sweep ≈ 30k–60k calls, 3,000 tracked projects
  ≈ 50k–100k calls. See §3 of the build brief.

## Submission form fields (Google Form, akshat's account)

- Name *
- Email *
- Git Repo Link *
- One Pager Link *
- 2 Minute Demo Video Link (optional but recommended — we are doing it)
- **Feedback for Mireye *** ← this is the interview. Draft lives in
  `outputs/drafts/mireye_feedback.md`. Five people who would be coworkers read it.


## Full build brief

`docs/build-brief.md` — problem framing, sources policy, buyers, rubric mapping,
4-day plan, demo script, guardrails, README rules.
