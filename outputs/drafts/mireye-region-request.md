# Draft — Mireye feature request

**Status: UNSENT.** Paste into the feature request form at mireye.com yourself.

Written for someone who knows geodata and knows nothing about air permitting. No jargon
without a plain-English gloss on the same line.

---

## title

```
India coverage: address resolution, admin hierarchy, electricity utility territory
```

---

## description

```
Some background, since this isn't an obvious use of the API.

Data centres now build their own gas power plants on site, because grid connection
queues are years long. To run a power plant you need an air permit from the state. Which
permit you need, and whether it takes 6 months or 5 years, depends almost entirely on
where the land is. Air quality status of that county, how much pollution headroom is
left there, whether a national park is nearby. Nobody checks this before buying the
land, so projects get announced with dates that were never achievable.

I built a screener for it on Mireye. Give it a site, it works out which permit the power
plant needs there and roughly how long that takes. If the answer is bad, it searches
sites nearby and alternative plant designs until it finds one where the answer is
better.

Mireye is the whole physical layer: location, terrain, land cover, transmission lines,
substations, gas pipelines, who lives nearby. Around it I pulled EPA air quality
designations (463 across 245 counties, parsed out of their dBASE files), CourtListener
for lawsuits against developers and counties, Sentinel-2 imagery off AWS Open Data to
check whether ground has actually been broken yet, spot GPU rental prices from Vast.ai,
SF Compute, RunPod and Lambda to work out what a delay costs in lost revenue, a local
news signal for community opposition, and 27 county building-moratorium records entered
by hand.

Two things it turned up. Run against all 3,222 US counties, a 500 MW gas plant needs the
hardest tier of air permit in every single one, and the gap between the fastest county
and the slowest is 1,309 days for identical equipment. And one data_center_siting call
at Ashburn VA returns both 120 m to a 230 kV line and in_air_quality_nonattainment: true,
with a national park 63 km away that triggers a federal review. Great site by every
infrastructure measure. About 54 months before you can legally switch it on.

I'd like to do this in India next and there's currently no equivalent to Mireye there.
Axis Capital puts India's announced 6-8 GW by 2030 at a realistic 3.4-3.6 GW. Over 10.5
GW is sitting on land nobody has broken ground on. Grid connections take about 18 months.
Same gap, and no way to query the ground at all.

The version I actually want to build there is for the agencies, not the developers. A
state pollution control board or a district planning office is answering the same
question I am, from the other side of the desk, with a fraction of the staff. Right now
an application lands and someone works through the siting and air-quality checks by hand,
which is why consents take 28 to 36 months. The same agent, pointed the other way,
pre-screens an application in a day: here is what this site is, here is what this plant
would emit, here are the checks that actually apply, here is what's missing from the
file. It doesn't decide anything. It removes the part that's slow and mechanical, so a
reviewer spends their time on the judgement.

That's a better first customer than a developer, for three reasons. The bottleneck is
genuinely on the agency side, so it's where the time actually gets saved. Agencies
procure, and they have a budget line for tooling where a developer has a project cost.
And a faster, more consistent review is a public good rather than a private advantage,
which matters for who will take the meeting.

Three things would be enough for me to port this, since the permit logic is mine to
build:

1. Address and location resolution for Indian addresses, with the same refusal on a
   low-confidence match that /v1/geocode already does. Addressing is messier there, so a
   guessed point lands in the wrong district and every downstream answer is wrong.

2. Administrative hierarchy at a coordinate: state, district, tehsil, ward, urban local
   body. Pollution control in India is run by state-level boards, so which state and
   district you're in determines the entire regulatory answer.

3. Which electricity distribution company (DISCOM) covers that point, plus nearest
   transmission line with voltage and nearest substation. Connection timelines vary a lot
   between DISCOMs and it's genuinely hard to source anywhere else.

Item 2 is the one the agency version depends on entirely. If you can't resolve which
district and which state board a point falls under, there's nothing to hand a reviewer.

I built behind a provider interface so Mireye is the US implementation rather than
something the code is welded to. If the data exists for India, porting is a data problem
rather than a rewrite. Happy to share what the US version turned up either way.
```

---

## Notes

- ~470 words. Longer than the last draft on purpose: the first paragraph buys the reader
  the context to care about the rest. Without it "air permit" means nothing to them.
- Jargon removed: parcel, nonattainment NSR, PSD, Class I area, potential to emit.
  Where a term had to stay (`in_air_quality_nonattainment`) it is a literal field name
  from their own API, which they will recognise.
- Cut order if the form complains: the buyer note, then the second finding, then the
  India stats down to the 6-8 vs 3.4-3.6 line. Keep paragraph one whatever happens.
- Cross-check the India figures against `docs/evidence.md` E19 and E20 before pasting.
