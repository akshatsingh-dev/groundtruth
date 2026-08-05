# Draft — Mireye feature request

**Status: UNSENT.** Paste into the feature request form at mireye.com yourself.

Tone check: report what you did, then ask. No lecturing them about their own product.

---

## title

```
India coverage: parcel resolution, admin hierarchy, DISCOM territory
```

---

## description

```
I built an air permit screener on Mireye for the Build Challenge. It takes a parcel,
works out which permit an onsite power plant needs there, and when the answer is bad it
searches nearby parcels and generation configs for one where it changes.

Mireye is the whole physical layer. Alongside it I pulled EPA Green Book nonattainment
designations (463 across 245 counties, parsed from their dBASE files), CourtListener for
federal dockets against developers and counties, spot GPU pricing from Vast.ai, SF
Compute, RunPod and Lambda to price what a delay costs, and 27 county moratorium records
entered by hand. Everything physical came from you.

Two things I found using it. Across all 3,222 counties, a 500 MW onsite gas plant is a
major source everywhere, with 1,309 days between the fastest county and the slowest. And
one data_center_siting call at Ashburn VA returns both 120 m to a 230 kV line and
in_air_quality_nonattainment: true with Shenandoah NP at 63,478 m. Good site, 54 months
to legal power, same 106 fields.

What I'd like next is India, where there's currently no equivalent. Axis Capital puts the
announced 6-8 GW by 2030 at a realistic 3.4-3.6 GW, over 10.5 GW sits in land banking,
and power connections run about 18 months. Same gap, no way to query the ground.

Three fields would be enough for me to port this, since the regulatory logic is mine to
build:

1. Parcel resolution for Indian addresses, with the same typed refusal on low confidence.
   Addressing is messier there, so an interpolated point is a wrong district.

2. Admin hierarchy at a coordinate: state, district, tehsil, ward, urban local body.
   Pollution control is administered by the state boards, so everything downstream keys
   off it.

3. DISCOM territory, plus nearest transmission line with voltage and nearest substation.
   Connection timelines vary a lot between DISCOMs and it's hard to get anywhere else.

One note in case it's useful for prioritising: in India the buyer is likely the district
planning office or the state pollution control board rather than a developer, since the
agencies are the bottleneck. That version depends on point 2.

I built behind a provider interface so Mireye is the US implementation rather than the
architecture. If the substrate exists the port is a data problem. Happy to share what the
US version turned up either way.
```

---

## Notes

- ~330 words. Cut order if the form complains: the buyer note, then the second finding,
  then the India stats down to the 6-8 vs 3.4-3.6 line.
- Sources are named so it reads as a real integration rather than a demo.
- The two findings are stated flat, without commentary. Let them draw the conclusion.
- Ends on offering something rather than asking for something.
- Cross-check the India figures against `docs/evidence.md` E19 and E20 before pasting.
