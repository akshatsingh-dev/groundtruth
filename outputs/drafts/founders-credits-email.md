# Draft — email to founders@mireye.com about credits

**Status: UNSENT. The agent does not send email. Akshat sends this.**

Edit the bracketed bits, check the numbers still match what the sweep actually
consumes, then send it from your own client. Send it early — the point is partly
the credits and partly opening a line to the people deciding the internship.

---

**To:** founders@mireye.com
**Subject:** Build challenge entry — need room for a national county sweep (~200k calls)

---

Hi,

I'm building for the Build Challenge, signed up on the Build tier with code BUILD.
You said to email if we needed room to work, so here are real numbers rather than
a vague ask.

The entry is called Deliverable. It works out which air permit a data center power
project needs at a specific parcel, and when the answer is bad it searches outward
for a parcel or a generation config where the answer flips. Announced ≠ deliverable.

Your API is doing all of the physical layer. I'm not building EIA or HIFLD ingest,
I'm not building routing, I'm not scraping FERC queues. `/v1/fetch` utilities and
`grid_interconnect`, `/v1/proximity` nearest-by-road, and the `data_center_siting`
preset cover it. The only things I built outside Mireye are the EPA Green Book
nonattainment file and CourtListener dockets, because those are permit and
litigation records rather than physical facts.

Where the calls go:

| Run | Calls |
|---|---|
| Per-project deep screen (fetch presets + proximity + ask) | 15–40 |
| Alternate-site search, 25 candidate parcels per failed site | 400–1,000 |
| ~3,000 tracked projects, single pass | 50k–100k |
| National county sweep, ~3,140 counties, for the map | 30k–60k |

The alternate-site search is the expensive one and it is also the part that makes
this an agent rather than a report, so I do not want to cut it down. The national
sweep is the artifact the demo ends on: every US county scored on days-until-legal-
power for a 500 MW plant.

If you can put roughly [200k] credits on the account for the challenge window I can
run the full sweep instead of a sampled one. Happy to share what it turns up either
way — the county-level output is probably interesting to you regardless of how the
judging goes.

Two other things while I have you:

1. I've been using `/v1/field-requests` rather than building ingest for gaps. The
   ones I sent: county attainment status by pollutant, distance to nearest Class I
   area, background ambient PM2.5/NO2 at a coordinate, and count plus permitted
   emissions of major stationary sources within X km. All four are pure geometry or
   pure federal-records lookups over public data. [Update this once you know what
   came back — a queued build with a request_id is a fine outcome to report.]

2. Roadmap question rather than a request: any plan for coverage outside the US?
   My product's next market is India, where announced capacity is 6–8 GW by 2030
   and the realistic figure is 3.4–3.6 — same announced-versus-deliverable gap. I
   built the agent behind a provider interface so Mireye is the US implementation
   rather than the architecture. I'd be a customer the day you go international.

Thanks,
Akshat Singh
[repo link]
[email]

---

## Notes before you send

- Confirm the call counts against what `sweep/counties.py` actually reports before
  you claim them. If the sweep came in at 40k, say 40k.
- Fill in item 1 with the real field-request outcomes. If they all came back as
  existing fields, say that — it is a better story than a queued build, because it
  means you saved a day.
- Do not send this from inside the repo, from a script, or from anything automated.
  Your own mail client. That is the guardrail and it is also just correct.
