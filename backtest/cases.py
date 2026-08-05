"""Backtest: reconstruct the pre-failure record for three real projects.

This is not an out-of-sample test. n = 3, the cases were picked because they are
well documented, and I already know how each one turned out. What it does test is
narrower and still worth doing: **given only facts that were public before the
project ran into trouble, does the pathway engine name the thing that went wrong?**

The discipline is the freeze date. Each case has a `cutoff`. Every field in the
`SiteContext` and `GenerationConfig` below carries the date it became public and
the source it came from, and nothing dated after the cutoff is allowed in. Facts I
had to throw away for that reason are listed in `excluded` on each case, so you can
see the shape of what I gave up.

Where a fact was never public, the field is left `None` rather than guessed. That
costs the demo some triggers. It is the right trade — a backtest that fills gaps
with the answer is not a backtest.

Read `docs/backtest-notes.md` before quoting any of this. It says plainly which
facts are genuinely pre-failure, which are contaminated, and what the honest claim
is.

Run:  python -m backtest.cases
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.emissions import (
    Control,
    Fuel,
    GenerationConfig,
    PrimeMover,
    estimate,
)
from agent.pathway import (
    NonattainmentStatus,
    Pathway,
    PathwayResult,
    SiteContext,
    determine_pathway,
)

# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Fact:
    """One input field, when it became public, and where it came from.

    `knowable_by` is the date the fact was in the public record — not the date of
    the event it describes. A permit filed in November and reported in December is
    knowable by December.
    """

    value: Any
    knowable_by: str  # ISO date
    source: str
    note: str = ""

    def line(self, name: str) -> str:
        note = f"  [{self.note}]" if self.note else ""
        return f"    {name:<26} {self.value!r:<34} {self.knowable_by}  {self.source}{note}"


@dataclass
class Case:
    key: str
    name: str
    site_label: str
    #: Freeze date. Nothing after this is allowed into the config or the site.
    cutoff: str
    #: When the project visibly hit the wall.
    failure_date: str
    #: What actually happened, in one paragraph, with dates.
    outcome: str
    #: The prediction we are grading the engine against.
    outcome_short: str
    facts: dict[str, Fact]
    config: GenerationConfig
    site: SiteContext
    #: Post-cutoff facts deliberately kept out, and why they would have helped.
    excluded: list[str] = field(default_factory=list)
    #: Config variants to run alongside the base case. The first entry is the base.
    variants: list[tuple[str, GenerationConfig]] = field(default_factory=list)
    #: Honest read on whether the engine got it right.
    verdict: str = ""


# --------------------------------------------------------------------------
# Case 1 — Nebius / DataOne, Vineland, New Jersey
# --------------------------------------------------------------------------
#
# Microsoft signed a $17.4B five-year capacity deal with Nebius in September 2025.
# Nebius's first US site is Vineland, in Cumberland County, New Jersey, developed
# with DataOne. The plan was to skip the interconnection queue entirely and run the
# campus off ~400 MW of onsite natural gas reciprocating engines.
#
# It did not get the air permit. In May 2026 Nebius signed Bloom Energy and
# replaced the engines with solid oxide fuel cells.
#
# Cutoff: 1 March 2026. By then the engine count, the site, the county, the
# ozone designation and the NJ EJ statute were all public. The Bloom pivot
# (20 May 2026) was not.

_VINELAND_FACTS = {
    "site": Fact(
        "off S. Lincoln Ave & Sheridan Ave, Vineland, NJ",
        "2026-02-27",
        "Sierra Club NJ, 27 Feb 2026; WHYY, 25 Mar 2026",
        "street-level location only; no parcel ID published",
    ),
    "county": Fact("Cumberland County, NJ", "2026-02-27", "same"),
    "latitude": Fact(
        39.447, "2026-02-27", "derived from the published cross-streets",
        "approximate, not a Mireye geocode",
    ),
    "longitude": Fact(-75.010, "2026-02-27", "derived from the published cross-streets"),
    "generation_mw": Fact(
        403.0,
        "2026-02-27",
        "Sierra Club NJ: '36 Bergen Engine units with a combined 403 MW potential'",
        "WHYY later reported 32 gas engines + 6 diesel emergency; 403 MW is the "
        "larger and more conservative published figure",
    ),
    "prime_mover": Fact(
        "recip_lean_burn",
        "2026-02-27",
        "Bergen Engines gas gensets are 4-stroke lean burn",
        "product-line fact, not project-specific disclosure",
    ),
    "controls": Fact(
        "SCR + oxidation catalyst",
        None,
        "NOT DISCLOSED — assumed",
        "assumed in the developer's favour. Controls were never made public. "
        "Running uncontrolled would make the case look worse than the record supports",
    ),
    "it_load_mw": Fact(300.0, "2024-06", "Vineland Planning Board site plan approval"),
    "microsoft_deal": Fact("$17.4B, 5 years", "2025-09", "Nebius/Microsoft announcement"),
    "announced_energization": Fact(
        "onsite gas online during 2026; 7 of 9 compute tranches depend on it",
        "2026-06-03",
        "Cleanview / distilled.earth",
        "POST-CUTOFF for the tranche detail. Used only as the schedule we grade "
        "against, never as an engine input",
    ),
    "air_permit": Fact(
        "application PCP250002, applicant DataOne, under NJDEP review",
        "2026-02-27",
        "NJDEP; Sierra Club NJ, 27 Feb 2026 ('no official air permits granted')",
    ),
    "ozone_designation": Fact(
        "Philadelphia-Atlantic City PA-NJ, 2015 8-hr ozone, Serious",
        "2024-07-30",
        "EPA Green Book; reclassified Moderate to Serious eff. 30 Jul 2024",
        "matches the ingested Green Book export (data/greenbook.json, EPA export "
        "2026-07-31): whole county, not partial. Design value 0.073 ppm. The county "
        "also carries a Marginal designation under the 2008 ozone NAAQS, which does "
        "not change the answer",
    ),
    "otr": Fact("entire state of NJ is in the Ozone Transport Region", "1990", "CAA 184"),
    "ej_law": Fact(
        "NJDEP may deny a permit outright in an overburdened community",
        "2023-04",
        "N.J.S.A. 13:1D-157; NJDEP EJ rules effective April 2023",
    ),
    "class_i": Fact(
        ("Brigantine Wilderness (Edwin B. Forsythe NWR)", 59.0),
        "1977",
        "CAA 162(a) mandatory Class I federal areas",
        "great-circle km from the site to the published area centroid, computed "
        "here — not a Mireye proximity call and not boundary-to-boundary",
    ),
    "terrain_relief_m": Fact(
        15.0, "public", "USGS NED — outer coastal plain, effectively flat",
        "included because it is uncontroversial; the trigger only fires above 150 m",
    ),
}

VINELAND = Case(
    key="nebius_vineland",
    name="Nebius / DataOne — Vineland, NJ",
    site_label="Vineland, Cumberland County, New Jersey",
    cutoff="2026-03-01",
    failure_date="2026-05-20",
    outcome=(
        "NJDEP never issued the air permit. Application PCP250002 sat under review "
        "through the spring while two town halls (January and March 2026) drew "
        "organised opposition, the city council pulled a $6.2M loan, and NJDEP "
        "weighed whether to aggregate the site with the adjacent Corning plant as a "
        "single stationary source. On 20 May 2026 Nebius announced a 10-year, "
        "up-to-$2.6B agreement with Bloom Energy and replaced the engines with "
        "328 MW of solid oxide fuel cells. Nebius's own site page now describes "
        "Vineland as 'classified as a minor emissions source' and operational 'by "
        "2027' — a slip from the 2026 gas schedule the Microsoft tranches assumed."
    ),
    outcome_short="Combustion abandoned. Swapped to fuel cells 20 May 2026. Schedule slipped to 2027.",
    facts=_VINELAND_FACTS,
    config=GenerationConfig(
        mw=403.0,
        prime_mover=PrimeMover.RECIP_LEAN_BURN,
        fuel=Fuel.NATURAL_GAS,
        controls=(Control.SCR, Control.OXIDATION_CATALYST),
        run_hours=8760.0,
        enforceable_limit=False,
    ),
    site=SiteContext(
        state="NJ",
        county="Cumberland",
        latitude=39.447,
        longitude=-75.010,
        nonattainment=[
            NonattainmentStatus(
                pollutant="ozone",
                classification="serious",
                area_name="Philadelphia-Wilmington-Atlantic City, PA-NJ-MD-DE",
                fetched="2024-07-30",
            )
        ],
        class_i_areas=[("Brigantine Wilderness", 59.0)],
        terrain_relief_m=15.0,
        # Deliberately None below. See `excluded`.
        gas_pipeline_km=None,
        residential_within_1km=None,
        increment_consumed={},
        litigation=[],
        provenance={k: {"knowable_by": f.knowable_by, "source": f.source} for k, f in _VINELAND_FACTS.items()},
    ),
    excluded=[
        "residential_within_1km — left None. Vineland qualifies as an overburdened "
        "community and roughly half its population is in NJDEP-designated OBC tracts, "
        "but reporting says the DataOne lots themselves fall just outside the OBC "
        "boundary. No published headcount within 1 km exists. Setting a number here "
        "would fire the EJ hard stop and would be me inventing the answer.",
        "gas_pipeline_km — left None. The project proposed 36 onsite gas engines, so "
        "gas was clearly reachable, but no distance was ever published. Gas supply was "
        "not this project's failure mode.",
        "increment_consumed — left empty. No PSD increment tracking data was pulled "
        "for the Philadelphia area. This omission makes the engine's answer shorter, "
        "not longer.",
        "The 20 May 2026 Bloom Energy agreement — the outcome. Post-cutoff by 80 days.",
        "The Corning aggregation question — reported 21 Apr 2026, post-cutoff. Would "
        "have added a second, independent reason to expect major-source treatment.",
    ],
    variants=[
        (
            "as proposed: 403 MW Bergen lean-burn gas engines",
            GenerationConfig(
                mw=403.0,
                prime_mover=PrimeMover.RECIP_LEAN_BURN,
                fuel=Fuel.NATURAL_GAS,
                controls=(Control.SCR, Control.OXIDATION_CATALYST),
            ),
        ),
        (
            "what they actually switched to: 328 MW Bloom fuel cells",
            GenerationConfig(
                mw=328.0,
                prime_mover=PrimeMover.FUEL_CELL,
                fuel=Fuel.NATURAL_GAS,
            ),
        ),
    ],
    verdict=(
        "Hit, on the right mechanism. The engine calls major nonattainment NSR off the "
        "Serious ozone designation, not off anything NJ-specific, and the config search "
        "names fuel cells as the flip. Nebius made exactly that swap 80 days after the "
        "cutoff. The engine's absolute timeline (~69 months likely) is longer than the "
        "record can support and should be read as 'this does not happen on a 2026 "
        "schedule', not as a date."
    ),
)


# --------------------------------------------------------------------------
# Case 2 — Project Jupiter (OpenAI / Oracle Stargate), Santa Teresa, New Mexico
# --------------------------------------------------------------------------
#
# 1,400 acres at Santa Teresa in Doña Ana County, developed by BorderPlex Digital
# Assets with STACK, leased to Oracle for OpenAI. Behind-the-meter from the start.
#
# The original air permit applications, prepared by Trinity Consultants, covered two
# separate microgrids about 1.25 miles apart — east and west — running simple-cycle
# gas turbines. Each application claimed NOx just under 250 tpy: 248.9 and 249.97.
# On 19 December 2025 NMED called the applications incomplete and said a facility
# "that is 1.1 tons away from the 250" threshold is "not practically enforceable."
#
# Two things then went wrong. Oracle withdrew the turbine applications and refiled
# with Bloom fuel cells (announced 27 April 2026). And the New Mexico State Land
# Office denied the right-of-way for the pipeline that would have fed either design.
#
# Cutoff: 1 February 2026. The applications, the turbine count, the claimed NOx, the
# NMED incompleteness letter, the ozone designation and the pipeline application
# (filed 29 Jan 2026, 18 miles of new 24-inch pipe) were all public by then.

_JUPITER_FACTS = {
    "site": Fact(
        "Santa Teresa, Doña Ana County, NM — ~1,400 acres",
        "2025-09",
        "BorderPlex Digital Assets / Baxtel project record",
    ),
    # No Jupiter coordinate is public. 31.870, -106.690 was an approximate Santa
    # Teresa point and reads as empty desert. The satellite module scanned a 15 km
    # window and ranked 300 m blocks by disturbance; the top cluster sits 6.21 km
    # SSE, 1.6 km off the Pete V. Domenici Highway, 1.1 km from a substation and
    # 3.3 km from an EIA-860M generator marked "UNDER CONSTRUCTION, MORE THAN 50
    # PERCENT COMPLETE". Jupiter has a very large hole in the ground. What it lost
    # was the gas, not the dirt, which is the sharper version of the thesis.
    "latitude": Fact(31.8175, "2025-09", "Santa Teresa, disturbance-ranked", "satellite-located, not a published coordinate"),
    "longitude": Fact(-106.6675, "2025-09", "Santa Teresa, disturbance-ranked", "satellite-located, not a published coordinate"),
    "generation_mw": Fact(
        2800.0,
        "2025-12-09",
        "Albuquerque Journal, 9 Dec 2025: 'up to 2.8 gigawatts total'",
        "the 2.45 GW figure quoted elsewhere is the later fuel-cell design",
    ),
    "prime_mover": Fact(
        "simple_cycle_turbine",
        "2025-12-09",
        "Albuquerque Journal: '41 simple-cycle gas turbines'",
        "sources disagree on whether 41 is per microgrid or across both",
    ),
    "units": Fact(
        2,
        "2025-12-09",
        "two microgrids, east and west, ~1.25 miles apart, filed as separate applications",
        "this is the disclosed fact the aggregation trigger runs on",
    ),
    "controls": Fact(
        "DLN + SCR",
        None,
        "NOT DISCLOSED — inferred",
        "inferred from the applicant's own claimed NOx rate, which implies "
        "roughly 2-3 ppm turbine outlet. Favourable to the developer",
    ),
    "applicant_claimed_nox": Fact(
        (248.9, 249.97),
        "2025-12-09",
        "Albuquerque Journal, tpy per microgrid, east and west",
        "both sit just under the 250 tpy major source threshold. Not used as an "
        "engine input — recorded so the engine's own PTE can be compared to it",
    ),
    "applicant_claimed_so2": Fact((31.83, 27.02), "2025-12-09", "Albuquerque Journal, tpy"),
    "nmed_finding": Fact(
        "applications incomplete; '1.1 tons away from the 250' is 'not practically enforceable'",
        "2025-12-19",
        "NMED letter, via Source New Mexico 19 Dec 2025",
        "this is why the base case runs PTE at 8760 with no enforceable cap",
    ),
    "ozone_designation": Fact(
        "El Paso-Las Cruces, TX-NM, 2015 8-hr ozone, Marginal (partial county)",
        "2021-11-30",
        "EPA Green Book; Sunland Park area expanded and renamed 30 Nov 2021",
        "matches the ingested Green Book export (data/greenbook.json, EPA export "
        "2026-07-31). PARTIAL county — only southern Doña Ana is designated. The "
        "violating monitors are at Sunland Park and Santa Teresa, so this site is "
        "inside it, but partial-county designations are where a screen like this "
        "goes wrong and a boundary check is required before anyone relies on it",
    ),
    "gas_pipeline_km": Fact(
        28.0,
        "2026-01-29",
        "Energy Transfer 'Green Chile' right-of-way application, filed 29 Jan 2026: "
        "18 miles of new 24-inch pipe needed to reach the site",
        "18 miles = 29 km; 28 km used. This is distance to adequate gas supply, which "
        "is what the trigger is actually asking",
    ),
    "class_i": Fact(
        ("Guadalupe Mountains NP", 172.0),
        "1977",
        "CAA 162(a) mandatory Class I federal areas",
        "great-circle km computed here. Next nearest: White Mountain Wilderness 189 km, "
        "Gila Wilderness 211 km, Carlsbad Caverns 215 km",
    ),
    "announced_energization": Fact(
        "initial operations Q4 2026",
        "2025-09",
        "project record at construction start",
    ),
}

JUPITER = Case(
    key="stargate_jupiter",
    name="Project Jupiter (OpenAI / Oracle Stargate) — Santa Teresa, NM",
    site_label="Santa Teresa, Doña Ana County, New Mexico",
    cutoff="2026-02-01",
    failure_date="2026-03-20",
    outcome=(
        "Two failures, in order. On 20 March 2026 the New Mexico State Land Office "
        "denied Energy Transfer's right-of-way for the 18-mile 'Green Chile' lateral "
        "across roughly one mile of state trust land; Land Commissioner Stephanie "
        "Garcia Richard denied it again on 14 July 2026, citing little benefit to the "
        "land trust against clear environmental risk. Separately, on 27 April 2026 the "
        "developers withdrew the simple-cycle turbine applications and refiled with up "
        "to 2.45 GW of Bloom fuel cells, cutting claimed NOx by about 92%. The NMED air "
        "permit hearing is set for 19 October 2026 in Sunland Park. Satellite analysis "
        "cited by Cleanview says the project is likely to miss its 2027 target."
    ),
    outcome_short=(
        "Pipeline right-of-way denied twice (20 Mar, 14 Jul 2026). Turbine applications "
        "withdrawn 27 Apr 2026. Air hearing 19 Oct 2026."
    ),
    facts=_JUPITER_FACTS,
    config=GenerationConfig(
        mw=2800.0,
        prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
        fuel=Fuel.NATURAL_GAS,
        controls=(Control.DLN, Control.SCR),
        run_hours=8760.0,
        enforceable_limit=False,  # NMED's own finding: the cap was not practically enforceable
        units=2,
    ),
    site=SiteContext(
        state="NM",
        county="Doña Ana",
        latitude=31.8175,
        longitude=-106.6675,
        nonattainment=[
            NonattainmentStatus(
                pollutant="ozone",
                classification="marginal",
                area_name="El Paso-Las Cruces, TX-NM",
                fetched="2021-11-30",
            )
        ],
        class_i_areas=[("Guadalupe Mountains NP", 172.0)],
        gas_pipeline_km=28.0,
        terrain_relief_m=None,
        residential_within_1km=None,
        increment_consumed={},
        litigation=[],
        provenance={k: {"knowable_by": f.knowable_by, "source": f.source} for k, f in _JUPITER_FACTS.items()},
    ),
    excluded=[
        "The 20 March 2026 and 14 July 2026 right-of-way denials — the outcome.",
        "The 27 April 2026 switch to Bloom fuel cells — the outcome.",
        "terrain_relief_m — left None. The site sits near the Franklin/Potrillo "
        "ranges and real relief in the modelling domain is plausible, but I did not "
        "verify it. Leaving it None costs the case 2 months, in the engine's favour.",
        "residential_within_1km — left None. Sunland Park and Santa Teresa are "
        "populated but no published count within 1 km exists, and NM has no EJ denial "
        "statute for the trigger to attach to.",
        "increment_consumed — left empty. Existing El Paso-area majors almost "
        "certainly consume some SO2/NO2 increment; not verified, so not used.",
        "PM10 nonattainment — left out. The Green Book also lists Doña Ana County as "
        "Moderate nonattainment for the 1987 PM10 NAAQS ('Dona Ana County; Anthony, "
        "NM'), also partial-county. Anthony is ~20 miles north of Santa Teresa and I "
        "could not verify the site falls inside that boundary. Including it would add "
        "a second NA NSR trigger and make the case look stronger than I can defend.",
    ],
    variants=[
        (
            "as filed, cap treated as NOT enforceable (NMED's finding)",
            GenerationConfig(
                mw=2800.0,
                prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
                fuel=Fuel.NATURAL_GAS,
                controls=(Control.DLN, Control.SCR),
                units=2,
            ),
        ),
        (
            "as filed, cap treated as enforceable at 3,400 hr/yr (39% availability)",
            GenerationConfig(
                mw=2800.0,
                prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
                fuel=Fuel.NATURAL_GAS,
                controls=(Control.DLN, Control.SCR),
                run_hours=3400.0,
                enforceable_limit=True,
                units=2,
            ),
        ),
        (
            "what they actually refiled: 2,450 MW Bloom fuel cells, single plant",
            GenerationConfig(
                mw=2450.0,
                prime_mover=PrimeMover.FUEL_CELL,
                fuel=Fuel.NATURAL_GAS,
            ),
        ),
    ],
    verdict=(
        "Hit on the binding constraint, and for the right reason. The engine returns a "
        "hard stop on gas reachability — 28 km to adequate supply, a lateral that is its "
        "own permitting project — which is precisely what killed the schedule, twice, "
        "before the air permit was ever decided. It also fires the source-aggregation "
        "trigger on the two-microgrid split, which is the same objection NMED raised in "
        "writing on 19 December 2025. Note that the pipeline hard stop fires off one "
        "number I took from the pipeline application itself; that is a strong input, and "
        "the test is easier than a cold screen would be."
    ),
)


# --------------------------------------------------------------------------
# Case 3 — xAI Colossus 1, Memphis, Tennessee (the inverse case)
# --------------------------------------------------------------------------
#
# This one is here because it went the other way. xAI installed up to 35 mobile gas
# turbines at the former Electrolux plant in South Memphis from mid-2024, energised
# them without a Clean Air Act permit, and got roughly 100,000 GPUs training. The
# Shelby County Health Department's position was that it "only regulates gas-burning
# generators if they're in the same location for more than 364 days" — the nonroad
# engine reading.
#
# The engine models the compliant path. xAI did not take the compliant path. So this
# case grades the engine against a project that beat it, and the honest answer is
# that the engine was right about the law and wrong about the behaviour.
#
# One correction to the story as usually told: the January 2026 EPA rule did NOT
# close this reading. See docs/evidence.md, claim E1. And the 2026 NAACP suit is
# about a different site — Colossus 2 in Southaven, Mississippi.
#
# Cutoff: 1 September 2024, before the permit fight became public.

_MEMPHIS_FACTS = {
    "site": Fact(
        "former Electrolux plant, South Memphis, Shelby County, TN",
        "2024-06",
        "widely reported at site announcement",
    ),
    # 35.065, -90.075 was a hand-picked "South Memphis" point and it is 7.31 km off
    # the actual site. Satellite verification read it as empty ground, correctly,
    # because it is empty ground. Mireye geocodes 3231 Paul R Lowry Rd at 0.95
    # rooftop confidence to the point below. The lesson is the product's own:
    # an approximate coordinate is a different parcel, and a different parcel is a
    # different answer.
    "latitude": Fact(35.060553, "2024-06", "3231 Paul R Lowry Rd, Memphis TN", "Mireye geocode, confidence 0.95"),
    "longitude": Fact(-90.155133, "2024-06", "3231 Paul R Lowry Rd, Memphis TN", "Mireye geocode, confidence 0.95"),
    "generation_mw": Fact(
        420.0,
        "2025-04",
        "SELC: 'up to 35 gas turbines on site capable of generating more than "
        "420 megawatts'",
        "POST-CUTOFF. The turbine count was not public in Sept 2024 — it came out "
        "through aerial imagery and the permit fight in 2025. This case is "
        "knowingly contaminated and is presented as an illustration, not a test",
    ),
    "prime_mover": Fact("simple_cycle_turbine", "2025-04", "SELC; trailer-mounted mobile turbines"),
    "controls": Fact(
        "DLN assumed",
        None,
        "NOT DISCLOSED — assumed",
        "assumed in the developer's favour; SELC alleged minimal control",
    ),
    "ozone_designation": Fact(
        "Shelby County TN — Attainment/Unclassifiable, 2015 8-hr ozone",
        "2018-01-16",
        "EPA Green Book, effective 16 Jan 2018",
        "attainment. No nonattainment NSR here. PSD is the operative programme",
    ),
    "class_i": Fact(
        ("Mingo Wilderness, MO", 213.0),
        "1977",
        "CAA 162(a) mandatory Class I federal areas",
        "great-circle km computed here. Next: Sipsey Wilderness 255 km",
    ),
    "announced_energization": Fact("first cluster training within months", "2024-06", "xAI"),
}

MEMPHIS = Case(
    key="xai_memphis",
    name="xAI Colossus 1 — Memphis, TN (inverse case)",
    site_label="South Memphis, Shelby County, Tennessee",
    cutoff="2024-09-01",
    failure_date="n/a — the project succeeded on schedule",
    outcome=(
        "The turbines ran. xAI brought roughly 100,000 GPUs to training in about 19 "
        "days from hardware install, inside a 122-day total buildout, with no Clean "
        "Air Act construction permit, under Shelby County's reading that a unit in "
        "one place for under 364 days is a nonroad engine. The Health Department "
        "issued a permit for 15 turbines on 2 July 2025, which NAACP and SELC "
        "appealed. A separate Clean Air Act suit over the Colossus 2 turbines in "
        "Southaven, Mississippi was filed in April 2026; DOJ moved to intervene and "
        "dismiss on 16 June 2026; a preliminary injunction hearing is set for late "
        "August 2026. The legal question is still open — it was not settled by the "
        "January 2026 NSPS rule."
    ),
    outcome_short=(
        "Energised without a CAA permit. ~100k GPUs training in ~19 days (122-day "
        "buildout). Permit issued for 15 turbines Jul 2025, under appeal."
    ),
    facts=_MEMPHIS_FACTS,
    config=GenerationConfig(
        mw=420.0,
        prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
        fuel=Fuel.NATURAL_GAS,
        controls=(Control.DLN,),
        run_hours=8760.0,
        enforceable_limit=False,
    ),
    site=SiteContext(
        state="TN",
        county="Shelby",
        latitude=35.060553,
        longitude=-90.155133,
        nonattainment=[],  # attainment/unclassifiable for 2015 ozone
        class_i_areas=[("Mingo Wilderness", 213.0)],
        gas_pipeline_km=None,
        terrain_relief_m=None,
        residential_within_1km=None,
        increment_consumed={},
        litigation=[],
        provenance={k: {"knowable_by": f.knowable_by, "source": f.source} for k, f in _MEMPHIS_FACTS.items()},
    ),
    excluded=[
        "The whole case is contaminated. The 35-turbine count and the 420 MW figure "
        "only became public in 2025, through the permit fight. A genuine 2024 screen "
        "would not have had them. This is an illustration of what the engine says "
        "about a config, not a test of whether it could have predicted anything.",
        "TN is not one of the eight modelled states, so the timeline runs on the "
        "federal default multiplier with no state adjustment.",
        "gas_pipeline_km, terrain_relief_m, residential_within_1km, increment — all "
        "left None. Unverified.",
    ],
    variants=[
        (
            "as installed: 420 MW mobile simple-cycle turbines",
            GenerationConfig(
                mw=420.0,
                prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
                fuel=Fuel.NATURAL_GAS,
                controls=(Control.DLN,),
            ),
        ),
    ],
    verdict=(
        "Miss, and the interesting kind. The engine says major PSD, roughly two years, "
        "because that is what the Clean Air Act says about 420 MW of turbines at a fixed "
        "site. xAI energised in weeks by taking the position that the turbines were "
        "nonroad engines. The engine models the compliant path and has no variable for "
        "'developer runs it anyway and litigates.' That is a real limitation and it is "
        "worth saying out loud: this product prices the legal path, not the appetite for "
        "risk. Note also that the engine's ~26-month answer looks a lot like what xAI is "
        "now living through — permit July 2025, appeal, injunction hearing August 2026 — "
        "so the timeline may have been right about the calendar and wrong about the order."
    ),
)


CASES = [VINELAND, JUPITER, MEMPHIS]


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


def run_case(case: Case, verbose: bool = True) -> PathwayResult:
    """Run the base config and every variant. Returns the base result."""
    results: list[tuple[str, PathwayResult]] = []
    for label, config in (case.variants or [("base", case.config)]):
        est = estimate(config)
        results.append((label, determine_pathway(est, case.site)))

    if not verbose:
        return results[0][1]

    base_label, base = results[0]
    est = estimate(case.variants[0][1] if case.variants else case.config)

    print()
    print("=" * 96)
    print(f"  {case.name}")
    print(f"  {case.site_label}")
    print("=" * 96)
    print(f"  record frozen at: {case.cutoff}      visible failure: {case.failure_date}")
    print()

    print("  INPUTS — every field with the date it became public")
    print(f"    {'field':<26} {'value':<34} {'knowable by':<12} source")
    print(f"    {'-' * 26} {'-' * 34} {'-' * 12} {'-' * 20}")
    for name, fact in case.facts.items():
        by = fact.knowable_by or "NEVER PUBLIC"
        note = f"\n      -> {fact.note}" if fact.note else ""
        print(f"    {name:<26} {str(fact.value)[:33]:<34} {by:<12} {fact.source[:44]}{note}")

    print()
    print("  EXCLUDED — facts kept out of the engine")
    for item in case.excluded:
        print(f"    - {item}")

    print()
    print(f"  ENGINE OUTPUT — {base_label}")
    print(f"    PTE: " + ", ".join(
        f"{p} {t:,.0f} tpy"
        for p, t in sorted(est.tons_per_year.items(), key=lambda kv: -kv[1])
        if p not in ("CO2e", "HCHO")
    ))
    if "applicant_claimed_nox" in case.facts:
        claimed = case.facts["applicant_claimed_nox"].value
        print(f"    applicant's own filing claimed NOx {claimed} tpy per unit "
              f"({sum(claimed):,.1f} tpy total)")
        print(f"    engine's PTE at 8760 hr is {est.tons_per_year['NOx'] / sum(claimed):,.0f}x that. "
              f"The gap IS the enforceability question.")
    print()
    print(f"    -> {base.pathway.label}")
    print(f"    -> {base.months_low:.0f}-{base.months_high:.0f} months (likely {base.months_likely:.0f})")
    if base.controlling_pollutant:
        print(f"    -> controlling: {base.controlling_pollutant} at "
              f"{base.controlling_tpy:,.0f} tpy vs {base.applicable_threshold:,.0f} tpy threshold")
    if base.offsets_required_tons:
        print(f"    -> offsets required: {base.offsets_required_tons:,.0f} tons")
    print()
    print("    triggers fired:")
    for trigger in base.fired:
        months = f" (+{trigger.months_added:.0f} mo)" if trigger.months_added else ""
        print(f"      * {trigger.name}{months}")
        print(f"          {trigger.detail[:200]}")
    if base.hard_stops:
        print()
        print("    HARD STOPS:")
        for stop in base.hard_stops:
            print(f"      ! {stop}")

    if len(results) > 1:
        print()
        print("  VARIANTS")
        for label, result in results:
            stop = "  HARD STOP" if result.hard_stops else ""
            print(f"    {label}")
            print(f"        {result.pathway.label}, "
                  f"{result.months_low:.0f}-{result.months_high:.0f} mo "
                  f"(likely {result.months_likely:.0f}){stop}")
        first, last = results[0][1], results[-1][1]
        if last.pathway.rank < first.pathway.rank:
            print()
            print(f"    delta: {first.pathway.label} -> {last.pathway.label}, "
                  f"{first.months_likely - last.months_likely:.0f} months saved")
        if first.hard_stops and last.hard_stops:
            print(f"    but the hard stop survives every config: "
                  f"{last.hard_stops[0].split('.')[0]}.")
            print("    No generation design fixes a fuel supply that cannot be permitted.")

    print()
    print("  WHAT ACTUALLY HAPPENED")
    for line in _wrap(case.outcome, 92):
        print(f"    {line}")
    print()
    print("  VERDICT")
    for line in _wrap(case.verdict, 92):
        print(f"    {line}")

    return base


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        if len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def run_all(verbose: bool = True) -> None:
    """Run every case and print the comparison table."""
    print()
    print("DELIVERABLE — BACKTEST")
    print("n = 3. Cases chosen because they are well documented and I already know how")
    print("they ended. This is a demonstration that the engine names the right failure")
    print("mode from pre-failure inputs. It is not an out-of-sample test. See")
    print("docs/backtest-notes.md.")

    rows = []
    for case in CASES:
        result = run_case(case, verbose=verbose)
        rows.append((case, result))

    print()
    print("=" * 96)
    print("  SUMMARY")
    print("=" * 96)
    print()
    header = f"  {'case':<26} {'frozen':<11} {'engine said':<26} {'months':<12} {'grade'}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for case, result in rows:
        stop = " +STOP" if result.hard_stops else ""
        grade = case.verdict.split(",")[0].split(".")[0].strip()
        print(
            f"  {case.name[:25]:<26} {case.cutoff:<11} "
            f"{result.pathway.value[:25]:<26} "
            f"{result.months_low:.0f}-{result.months_high:.0f}{stop:<7} "
            f"{grade}"
        )
    print()
    for case, result in rows:
        print(f"  {case.name[:25]:<26} actual: {case.outcome_short}")
    print()
    print("  Two of three flagged the mechanism that actually bound. The third is an")
    print("  honest miss: the engine prices the compliant path and xAI did not take it.")
    print()


if __name__ == "__main__":
    run_all()
