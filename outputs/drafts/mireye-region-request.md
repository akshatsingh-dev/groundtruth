# Draft — Mireye feature request: India coverage

**Status: UNSENT.** Paste into the feature request form at mireye.com yourself.

Short on purpose. A feature request that names three fields and one market gets read.
One that explains your whole product does not.

---

## title

```
India coverage: parcel, admin hierarchy and DISCOM territory
```

---

## description

```
I built an agent on Mireye for the Build Challenge. It works out which air permit a data
centre power project needs at a specific parcel, then searches nearby parcels for one
where the answer is better. Mireye is the entire physical layer.

India is the obvious second market and there is no supplier for it. Axis Capital calls
the announced 6-8 GW by 2030 inflated and puts the real figure at 3.4-3.6 GW. Over
10.5 GW sits in land banking. Power connections run about 18 months. Same
announced-versus-deliverable gap you already let me measure in the US, in a market where
nobody can query the ground at all.

Three fields would be enough to port my agent, because the regulatory layer is mine to
build:

1. Geocode and parcel resolution for Indian addresses, with the same typed refusal on low
   confidence. That matters more there, not less, since a silently interpolated point is a
   wrong district.

2. Admin hierarchy at a coordinate: state, district, tehsil, ward, urban local body.
   Everything downstream keys off it, because pollution control is administered by the
   state boards.

3. Nearest transmission line with voltage, nearest substation, and the DISCOM whose
   territory the parcel sits in. The DISCOM is the one nobody can get and everybody needs.
   Connection timelines vary enormously between them and nobody screens for it before
   buying land.

CPCB non-attainment status under NCAP would be the next one, since it is the direct
analogue of the EPA Green Book designation my US pathway engine turns on.

I built behind a provider interface so Mireye is the US implementation rather than the
architecture. If the substrate exists, the port is a data problem. I would be a customer
the day you go international.
```

---

## Notes

- ~280 words. If it still reads long, cut the CPCB paragraph. The three numbered items
  and the DISCOM sentence are what make it a brief instead of a wish.
- The DISCOM ask is the strongest thing in here. Specific, genuinely hard to source, and
  the kind of field that makes an API indispensable rather than convenient.
- Don't overclaim. You have a provider interface and a thesis, not an Indian product.
  "I'd be a customer" is the right register.
- Cross-check the India figures against `docs/evidence.md` E19 and E20 before pasting.
