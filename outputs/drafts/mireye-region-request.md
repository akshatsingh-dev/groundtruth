# Draft — Mireye feature request: India coverage

**Status: UNSENT.** Paste this into the feature request form at mireye.com yourself.
Email field is already prefilled with yours.

The form has two fields, `title` and `description`. Both are below, ready to paste.

Keep it specific. A request that names the fields, the regions and the use case is a
product brief. A request that says "please support India" is a wish.

---

## title

```
India coverage: parcel, power and air-quality fields for the second-largest data centre buildout
```

---

## description

```
I built an agent on Mireye for the Build Challenge. It works out which air permit a data
centre power project needs at a specific parcel, and when the answer is bad it searches
outward for a parcel or a generation config where it changes. Everything physical comes
from your API. The whole US layer is Mireye.

The reason I'm asking about India rather than "international" generally is that it's the
same problem you already solve, with the same gap and no supplier.

The numbers: Axis Capital calls India's announced 6-8 GW by 2030 inflated and puts the
realistic figure at 3.4-3.6 GW operational by mid-2030. Operational stock is about 1.8 GW
of IT load today (Savills, H1 2026). More than 10.5 GW is sitting in land banking, which
is the local phrasing for announced and not broken ground. Power connections run about 18
months and gensets from Caterpillar, Cummins and MTU are booked out two years. An
operator on the record: "The 28-36 month timeline is the real story here. In Singapore or
parts of the US you can get a facility up in 12-18 months."

That's your announced-versus-deliverable gap, in a market where nobody can currently
query the ground.

What I'd need, roughly in the order it would unblock work:

1. Geocode and parcel resolution for Indian addresses, with the same typed refusal on low
   confidence that /v1/geocode already does. The refusal behaviour matters more here, not
   less, because Indian addressing is messier and a silently interpolated point is a wrong
   district.

2. Administrative hierarchy at a coordinate: state, district, tehsil or taluka, ward,
   and the relevant urban local body. This is the equivalent of your county/tract lookup
   and it's what every downstream regulatory question keys off, because pollution control
   is administered at state level by the SPCBs.

3. Power proximity. Nearest transmission line with voltage, nearest substation, nearest
   gas pipeline, and the DISCOM whose territory the parcel falls in. The DISCOM one is the
   single highest-value field, because connection timelines vary enormously between them
   and nobody screens for it before buying land.

4. CPCB air quality: whether the parcel sits in a non-attainment city under the National
   Clean Air Programme, and the nearest CAAQMS monitor with its recent readings. NCAP
   non-attainment status is the closest analogue to the EPA Green Book designation that
   drives my whole US pathway engine.

5. Terrain, elevation and land cover, which you already have globally in the underlying
   datasets. Terrain drives dispersion modelling and it's the same physics everywhere.

6. Water. Groundwater extraction is a live constraint on Indian data centres in a way it
   mostly isn't in the US. CGWA notified block status at a coordinate, plus surface water
   proximity, would be genuinely differentiating.

If you wanted to scope it smaller, items 1, 2 and 3 alone would be enough to port my
agent, because the regulatory layer is mine to build. The physical layer is the part I
can't build and you can.

Two other regions with the same shape, in case it helps you prioritise: Malaysia (Johor,
where the Singapore overflow went) and Ireland (where Dublin has an effective grid
moratorium). Both are smaller than India and both have the announced-versus-deliverable
gap in an acute form.

I built my agent behind a PhysicalFactsProvider interface specifically so Mireye is the
US implementation rather than the architecture. If the substrate exists, the port is a
data problem rather than a rewrite. I'd be a customer the day you go international.
```

---

## Notes before you send

- Trim it if the form complains about length. The parts that must survive are the three
  numbers in paragraph three, and items 1, 2 and 3 of the list. Those are what make it a
  brief instead of a wish.
- The DISCOM point is the strongest thing in here. It's specific, it's genuinely hard to
  get, and it's the kind of field that makes an API indispensable rather than convenient.
- Don't overclaim the roadmap. You have a provider interface and a thesis, not an Indian
  product. The request reads better as "I'd be a customer" than as "I'm launching there."
- Cross-check the India figures against `docs/evidence.md` E19, E20 and E21 before you
  paste. E21 in particular is Savills, not Axis, and Axis gives a different number for
  the same thing using a different measure.
