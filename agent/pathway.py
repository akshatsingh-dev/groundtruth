"""Air permit pathway decision engine.

Given a potential-to-emit estimate and the regulatory facts about a specific
parcel, work out which permit the project actually needs and roughly how long
that takes at that state's agency.

The decision tree, in the order an air permitting engineer runs it:

1.  Is the source in one of the 28 named categories? That sets the PSD major
    source threshold at 100 tpy instead of 250 tpy. Data centers are not on the
    list. A combined-cycle plant's HRSG usually is, because it is a "fossil
    fuel-fired steam electric plant of more than 250 million Btu per hour heat
    input." A simple-cycle turbine with no steam cycle usually is not. That one
    distinction moves the threshold by 150 tpy.
2.  For each pollutant, is the county attainment or nonattainment?
    Attainment -> PSD applies. Nonattainment -> nonattainment NSR applies, with a
    much lower major threshold that scales with severity of the classification.
3.  Compare PTE against the applicable threshold.
4.  If over: major review. BACT (attainment) or LAER plus emission offsets
    (nonattainment). Dispersion modeling. Public comment. Long.
5.  If under only because of a permit condition: synthetic minor.
6.  If comfortably under: minor NSR, or permit-by-rule in the states that have one.
7.  Overlays that extend the timeline regardless: Class I areas within range,
    PSD increment already consumed by nearby majors, Title V, state toxics
    programs, NSPS and NESHAP applicability.

Sources for the thresholds are cited inline. Nothing here is a substitute for a
licensed professional's applicability determination — this is a screen that tells
you which conversation you are about to have.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .emissions import (
    SIGNIFICANT_EMISSION_RATES,
    EmissionsEstimate,
    GenerationConfig,
    PrimeMover,
    hours_for_tpy_target,
)

# --------------------------------------------------------------------------
# Pathways
# --------------------------------------------------------------------------


class Pathway(str, Enum):
    """Ordered easiest to hardest. `rank` is used to compare two sites."""

    PERMIT_BY_RULE = "permit_by_rule"
    MINOR_NSR = "minor_nsr"
    SYNTHETIC_MINOR = "synthetic_minor"
    MAJOR_PSD = "major_psd"
    MAJOR_NA_NSR = "major_nonattainment_nsr"

    @property
    def rank(self) -> int:
        return list(Pathway).index(self)

    @property
    def label(self) -> str:
        return {
            Pathway.PERMIT_BY_RULE: "Permit by rule / general permit",
            Pathway.MINOR_NSR: "Minor NSR construction permit",
            Pathway.SYNTHETIC_MINOR: "Synthetic minor (federally enforceable limits)",
            Pathway.MAJOR_PSD: "Major PSD",
            Pathway.MAJOR_NA_NSR: "Major nonattainment NSR",
        }[self]


#: Base timeline in months from complete application to issued permit, before
#: state-specific adjustment. Ranges are (optimistic, likely, pessimistic).
_BASE_MONTHS: dict[Pathway, tuple[float, float, float]] = {
    Pathway.PERMIT_BY_RULE: (1.0, 2.0, 4.0),
    Pathway.MINOR_NSR: (4.0, 6.0, 10.0),
    Pathway.SYNTHETIC_MINOR: (5.0, 8.0, 14.0),
    Pathway.MAJOR_PSD: (14.0, 24.0, 36.0),
    Pathway.MAJOR_NA_NSR: (20.0, 30.0, 48.0),
}


# --------------------------------------------------------------------------
# List of 28
# --------------------------------------------------------------------------

#: 40 CFR 52.21(b)(1)(i)(a). Sources in these categories are PSD-major at 100 tpy.
#: Everything else is major at 250 tpy. Reproduced short-form; the two that matter
#: for onsite data center power are the steam electric plant and the boiler entries.
LIST_OF_28 = (
    "Fossil fuel-fired steam electric plants of more than 250 million Btu/hr heat input",
    "Coal cleaning plants (with thermal dryers)",
    "Kraft pulp mills",
    "Portland cement plants",
    "Primary zinc smelters",
    "Iron and steel mill plants",
    "Primary aluminum ore reduction plants",
    "Primary copper smelters",
    "Municipal incinerators capable of charging more than 250 tons of refuse per day",
    "Hydrofluoric, sulfuric, and nitric acid plants",
    "Petroleum refineries",
    "Lime plants",
    "Phosphate rock processing plants",
    "Coke oven batteries",
    "Sulfur recovery plants",
    "Carbon black plants (furnace process)",
    "Primary lead smelters",
    "Fuel conversion plants",
    "Sintering plants",
    "Secondary metal production plants",
    "Chemical process plants",
    "Fossil fuel boilers (or combinations thereof) totaling more than 250 million Btu/hr heat input",
    "Petroleum storage and transfer units with a total storage capacity exceeding 300,000 barrels",
    "Taconite ore processing plants",
    "Glass fiber processing plants",
    "Charcoal production plants",
    "Nitric acid plants",
    "Any other stationary source category regulated under section 111 or 112 with "
    "a potential to emit 100 tpy or more (as designated by the Administrator)",
)


@dataclass(frozen=True)
class SourceCategoryFinding:
    on_list_of_28: bool
    category: str | None
    threshold_tpy: float
    reasoning: str
    citation: str


def classify_source_category(config: GenerationConfig) -> SourceCategoryFinding:
    """Decide whether the plant is PSD-major at 100 tpy or at 250 tpy.

    This is where most screens go wrong. A data center is not a listed category.
    The *power plant on its site* can be, and whether it is comes down to whether
    there is a steam cycle and whether heat input clears 250 MMBtu/hr.
    """
    citation = "40 CFR 52.21(b)(1)(i)(a); the 'List of 28' named source categories"
    heat_input = config.heat_input_mmbtu_hr
    steam_category = LIST_OF_28[0]

    if config.prime_mover is PrimeMover.COMBINED_CYCLE_TURBINE and heat_input > 250:
        return SourceCategoryFinding(
            True,
            steam_category,
            100.0,
            f"Combined cycle: the HRSG and steam turbine make this a fossil fuel-fired steam "
            f"electric plant, and heat input is {heat_input:,.0f} MMBtu/hr, over the 250 MMBtu/hr "
            f"cutoff. Major source threshold drops from 250 tpy to 100 tpy. The data center "
            f"itself is not a listed category — the power plant on its site is.",
            citation,
        )

    if config.prime_mover is PrimeMover.COMBINED_CYCLE_TURBINE:
        return SourceCategoryFinding(
            False,
            None,
            250.0,
            f"Combined cycle but heat input is only {heat_input:,.0f} MMBtu/hr, under the "
            f"250 MMBtu/hr cutoff in the listed category. Threshold stays at 250 tpy.",
            citation,
        )

    if config.prime_mover is PrimeMover.SIMPLE_CYCLE_TURBINE:
        return SourceCategoryFinding(
            False,
            None,
            250.0,
            f"Simple cycle, no steam cycle, so not a 'steam electric plant' and no boiler. "
            f"Not a listed category despite {heat_input:,.0f} MMBtu/hr of heat input. Major "
            f"source threshold is 250 tpy. Worth confirming with the state — a few agencies "
            f"read the boiler entry more broadly than EPA does.",
            citation,
        )

    if config.prime_mover in (PrimeMover.RECIP_LEAN_BURN, PrimeMover.RECIP_RICH_BURN, PrimeMover.DIESEL_RECIP):
        return SourceCategoryFinding(
            False,
            None,
            250.0,
            f"Reciprocating engines are not a listed category and are not boilers. "
            f"Major source threshold is 250 tpy. Note that engines carry much higher "
            f"NOx per MMBtu than turbines, so 250 tpy is easier to hit than it looks.",
            citation,
        )

    return SourceCategoryFinding(
        False, None, 250.0, "Non-combustion prime mover, not a listed category.", citation
    )


# --------------------------------------------------------------------------
# Nonattainment thresholds
# --------------------------------------------------------------------------

#: Major source thresholds in nonattainment areas, tons per year, by pollutant
#: and classification. 40 CFR 51.165(a)(1)(iv)(A) and CAA 182 / 187.
#: Ozone thresholds apply to both VOC and NOx as precursors.
_NA_THRESHOLDS: dict[str, dict[str, float]] = {
    "ozone": {
        "marginal": 100.0,
        "moderate": 100.0,
        "serious": 50.0,
        "severe": 25.0,
        "severe-15": 25.0,
        "severe-17": 25.0,
        "extreme": 10.0,
        "unclassified": 100.0,
    },
    "co": {"moderate": 100.0, "serious": 50.0, "unclassified": 100.0},
    "pm10": {"moderate": 100.0, "serious": 70.0, "unclassified": 100.0},
    "pm25": {"moderate": 100.0, "serious": 70.0, "unclassified": 100.0},
    "so2": {"unclassified": 100.0},
    "no2": {"unclassified": 100.0},
    "lead": {"unclassified": 100.0},
}

#: Emission offset ratios required in nonattainment areas. You must buy this much
#: reduction from an existing source per ton you emit. Offsets may simply not be
#: available, which is a hard stop rather than a delay.
_OFFSET_RATIOS: dict[str, float] = {
    "marginal": 1.1,
    "moderate": 1.15,
    "serious": 1.2,
    "severe": 1.3,
    "severe-15": 1.3,
    "severe-17": 1.3,
    "extreme": 1.5,
    "unclassified": 1.0,
}

#: Ozone Transport Region major source threshold for NOx and VOC, tons per year.
#: CAA 184 requires every OTR state to apply moderate-nonattainment requirements
#: statewide, whether or not the local monitors are clean.
OTR_MAJOR_THRESHOLD_TPY = 50.0

#: Permit-by-rule and general-permit eligibility gates.
#: Real state PBRs are not written as a tons-per-year test alone. They carry
#: equipment and heat-input limits, so a screen that checks only tonnage will
#: hand a 75 MW combined-cycle plant a permit-by-rule answer it cannot have.
#: 100 MMBtu/hr is roughly a 10 MW simple-cycle or 15 MW combined-cycle unit,
#: which is the scale these rules are actually written for.
PBR_MAX_TPY = 25.0
PBR_MAX_HEAT_INPUT_MMBTU_HR = 100.0

#: Which PTE pollutants count against which nonattainment designation.
_NA_POLLUTANT_MAP: dict[str, tuple[str, ...]] = {
    "ozone": ("NOx", "VOC"),
    "pm25": ("PM2.5", "SO2", "NOx"),  # direct PM2.5 plus precursors
    "pm10": ("PM10",),
    "co": ("CO",),
    "so2": ("SO2",),
    "no2": ("NOx",),
    "lead": (),
}


# --------------------------------------------------------------------------
# Site regulatory context
# --------------------------------------------------------------------------


@dataclass
class NonattainmentStatus:
    """One EPA Green Book row, normalised."""

    pollutant: str  # "ozone", "pm25", ...
    classification: str  # "moderate", "severe-15", "unclassified"
    area_name: str
    source: str = "EPA Green Book"
    fetched: str | None = None


@dataclass
class MajorSourceNearby:
    """An existing permitted major source. Matters because PSD increment is a
    finite budget shared across everyone in the area — if the sources already
    there consumed it, a new project has nothing left to model against."""

    name: str
    distance_km: float
    nox_tpy: float | None = None
    so2_tpy: float | None = None
    pm25_tpy: float | None = None
    source: str = "EPA NEI / Title V permit records"


@dataclass
class SiteContext:
    """Everything about a location that changes the permit answer.

    Physical fields come from Mireye and arrive with their own source and
    timestamp. Regulatory fields come from the Green Book, the state overlay
    table, and the county file.
    """

    state: str  # two-letter
    county: str
    county_fips: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    nonattainment: list[NonattainmentStatus] = field(default_factory=list)
    class_i_areas: list[tuple[str, float]] = field(default_factory=list)  # (name, km)
    major_sources_nearby: list[MajorSourceNearby] = field(default_factory=list)
    increment_consumed: dict[str, float] = field(default_factory=dict)  # pollutant -> fraction

    #: Non-air blockers, from the county file and CourtListener.
    moratorium: bool = False
    moratorium_note: str | None = None
    zoning_posture: str | None = None  # "by-right" | "special-exception" | "hostile"
    litigation: list[str] = field(default_factory=list)

    #: Physical facts from Mireye that feed dispersion and reachability.
    gas_pipeline_km: float | None = None
    transmission_km: float | None = None
    transmission_kv: float | None = None
    nearest_airport_km: float | None = None
    terrain_relief_m: float | None = None
    residential_within_1km: int | None = None
    provenance: dict[str, dict] = field(default_factory=dict)

    def na_for(self, pollutant_group: str) -> NonattainmentStatus | None:
        for status in self.nonattainment:
            if status.pollutant == pollutant_group:
                return status
        return None


# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------


@dataclass
class Trigger:
    """One thing that fired, why, and what it costs in months."""

    name: str
    fired: bool
    detail: str
    citation: str
    months_added: float = 0.0


@dataclass
class PathwayResult:
    pathway: Pathway
    months_low: float
    months_likely: float
    months_high: float
    source_category: SourceCategoryFinding
    triggers: list[Trigger]
    controlling_pollutant: str | None
    controlling_tpy: float | None
    applicable_threshold: float | None
    bact_pollutants: dict[str, float]
    offsets_required_tons: float | None
    hard_stops: list[str]
    narrative: list[str]

    @property
    def fired(self) -> list[Trigger]:
        return [t for t in self.triggers if t.fired]

    def summary(self) -> str:
        stop = " — HARD STOP" if self.hard_stops else ""
        return (
            f"{self.pathway.label}: {self.months_low:.0f}-{self.months_high:.0f} months "
            f"(likely {self.months_likely:.0f}){stop}"
        )


# --------------------------------------------------------------------------
# State overlays
# --------------------------------------------------------------------------

#: State agency behaviour. `multiplier` scales the base timeline, `notes` is what
#: an experienced consultant would tell you about that agency. Eight states are
#: modelled from public permit records and agency guidance; everything else falls
#: back to the federal default. That gap is stated plainly in the README.
STATE_OVERLAYS: dict[str, dict] = {
    "VA": {
        "agency": "Virginia DEQ",
        "multiplier": 1.25,
        "permit_by_rule": False,
        "notes": "DEQ has approved exactly one air permit for a data center campus with on-site "
        "gas generation. Assume the first-of-its-kind treatment, not a routine review.",
        "state_toxics": True,
        "source": "Virginia Mercury, 20 Jul 2026",
    },
    "TX": {
        "agency": "TCEQ",
        "multiplier": 0.75,
        "permit_by_rule": True,
        "notes": "TCEQ standard permits and permits-by-rule for small combustion are genuinely "
        "fast. Fastest major-state pathway in the country for onsite generation.",
        "state_toxics": True,
        "source": "30 TAC Chapter 106 / 116 standard permits",
    },
    "GA": {
        "agency": "Georgia EPD",
        "multiplier": 1.0,
        "permit_by_rule": False,
        "notes": "Workable minor NSR. Atlanta metro ozone nonattainment is the thing to check — "
        "it changes county by county.",
        "state_toxics": False,
        "source": "Georgia EPD Air Protection Branch",
    },
    "OH": {
        "agency": "Ohio EPA DAPC",
        "multiplier": 0.95,
        "permit_by_rule": True,
        "notes": "General permits exist for engines and small turbines. Cleveland and Cincinnati "
        "metro ozone status matters.",
        "state_toxics": False,
        "source": "Ohio EPA general permits",
    },
    "AZ": {
        "agency": "ADEQ / Maricopa County ACDD",
        "multiplier": 1.15,
        "permit_by_rule": False,
        "notes": "Maricopa County runs its own air district. Phoenix is ozone nonattainment and "
        "PM10 nonattainment — two separate offset problems on the same parcel.",
        "state_toxics": False,
        "source": "Maricopa County Air Quality Department Rule 200 series",
    },
    "NJ": {
        "agency": "NJ DEP",
        "multiplier": 1.6,
        "permit_by_rule": False,
        "notes": "Whole state is in the Ozone Transport Region, so NOx is regulated as if "
        "nonattainment regardless of local monitors. NJ DEP also runs an environmental justice "
        "law (N.J.S.A. 13:1D-157) that lets it deny a permit in an overburdened community "
        "outright. This is the Nebius failure mode.",
        "state_toxics": True,
        "otr": True,
        "ej_denial_authority": True,
        "source": "NJ DEP EJ Law N.J.S.A. 13:1D-157, effective April 2023",
    },
    "NM": {
        "agency": "NMED Air Quality Bureau",
        "multiplier": 1.35,
        "permit_by_rule": False,
        "notes": "Small bureau, few reviewers, and the state has shown it will block the gas "
        "supply rather than the plant. Pipeline reachability is the real constraint here, not "
        "the air permit.",
        "state_toxics": False,
        "source": "NMED AQB; New Mexico pipeline denial for the Stargate site",
    },
    "IL": {
        "agency": "Illinois EPA",
        "multiplier": 1.2,
        "permit_by_rule": False,
        "notes": "Chicago metro ozone nonattainment (severe) covers the collar counties. Offsets "
        "in the Chicago area are thin and expensive.",
        "state_toxics": False,
        "source": "Illinois EPA Bureau of Air",
    },
}

FEDERAL_DEFAULT_OVERLAY = {
    "agency": "state agency (not individually modelled)",
    "multiplier": 1.0,
    "permit_by_rule": False,
    "notes": "This state is not one of the eight modelled in detail. Timeline is the federal "
    "default with no state-specific adjustment. Treat the range as wider than shown.",
    "state_toxics": False,
    "source": "40 CFR 51/52 federal minimums",
}


#: The Ozone Transport Region, CAA 184(a). These states must apply moderate
#: nonattainment requirements for NOx and VOC across their whole territory,
#: regardless of what the local monitors say.
#:
#: This is separate from STATE_OVERLAYS on purpose. Only eight states are modelled
#: in detail, but the OTR is a statutory fact about twelve, and leaving it attached
#: to the modelled ones made the alternate-site search recommend moves that looked
#: better than they are. A move from New Jersey to Pennsylvania does not escape the
#: OTR — both are in it — and a screen that says otherwise is selling a saving that
#: does not exist.
OTR_STATES = frozenset({"CT", "DE", "ME", "MD", "MA", "NH", "NJ", "NY", "PA", "RI", "VT", "DC"})

#: Virginia is in the OTR only for the Washington DC metro portion, so it is
#: handled at county level rather than statewide. 40 CFR 81.347.
OTR_VA_COUNTIES = frozenset(
    {
        "Arlington",
        "Fairfax",
        "Loudoun",
        "Prince William",
        "Stafford",
        "Alexandria",
        "Falls Church",
        "Manassas",
        "Manassas Park",
    }
)


def in_otr(state: str, county: str | None = None) -> bool:
    state = state.upper()
    if state in OTR_STATES:
        return True
    if state == "VA" and county:
        return county.replace(" County", "").strip() in OTR_VA_COUNTIES
    return False


def overlay_for(state: str, county: str | None = None) -> dict:
    """The state agency's behaviour, plus any statutory overlay that applies
    whether or not we modelled that state in detail."""
    overlay = STATE_OVERLAYS.get(state.upper(), FEDERAL_DEFAULT_OVERLAY)
    if in_otr(state, county) and not overlay.get("otr"):
        overlay = dict(overlay)
        overlay["otr"] = True
        overlay["source"] = f"{overlay['source']}; CAA 184(a) Ozone Transport Region"
    return overlay


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------


def determine_pathway(est: EmissionsEstimate, site: SiteContext) -> PathwayResult:
    """Run the decision tree. Returns the pathway, a timeline, and every trigger
    that fired with its citation."""

    config = est.config
    category = classify_source_category(config)
    overlay = overlay_for(site.state, site.county)
    triggers: list[Trigger] = []
    narrative: list[str] = []
    hard_stops: list[str] = []

    narrative.append(f"Config: {config.describe()}.")
    narrative.append(
        f"Heat input {est.heat_input_mmbtu_hr:,.0f} MMBtu/hr. "
        f"PTE: " + ", ".join(f"{p} {t:,.0f} tpy" for p, t in sorted(est.tons_per_year.items(), key=lambda kv: -kv[1]) if p != "CO2e")
    )
    narrative.append(f"Source category: {category.reasoning}")

    # ---------------- Step 1: nonattainment NSR ----------------
    psd_threshold = category.threshold_tpy
    na_hits: list[tuple[NonattainmentStatus, str, float, float]] = []  # status, pollutant, tpy, threshold

    for status in site.nonattainment:
        thresholds = _NA_THRESHOLDS.get(status.pollutant, {})
        threshold = thresholds.get(status.classification.lower(), thresholds.get("unclassified", 100.0))
        for pollutant in _NA_POLLUTANT_MAP.get(status.pollutant, ()):
            tpy = est.tons_per_year.get(pollutant, 0.0)
            if tpy >= threshold:
                na_hits.append((status, pollutant, tpy, threshold))

    # Ozone Transport Region. CAA 184 makes every OTR state apply moderate
    # nonattainment requirements for NOx and VOC statewide, whether or not the
    # local monitors are clean. Without this a New Jersey parcel with no Green
    # Book listing scores as attainment and gets a PSD answer it will not get in
    # practice — which is exactly the Vineland failure mode.
    if overlay.get("otr") and not site.na_for("ozone"):
        otr_status = NonattainmentStatus(
            pollutant="ozone",
            classification="moderate",
            area_name=f"{site.state.upper()} statewide (Ozone Transport Region)",
            source="CAA 184; 40 CFR 51.165",
        )
        for pollutant in ("NOx", "VOC"):
            tpy = est.tons_per_year.get(pollutant, 0.0)
            if tpy >= OTR_MAJOR_THRESHOLD_TPY:
                na_hits.append((otr_status, pollutant, tpy, OTR_MAJOR_THRESHOLD_TPY))

    if site.nonattainment:
        listing = "; ".join(
            f"{s.pollutant} ({s.classification}, {s.area_name})" for s in site.nonattainment
        )
        triggers.append(
            Trigger(
                "nonattainment_designation",
                True,
                f"{site.county} County, {site.state} is designated nonattainment for: {listing}.",
                "EPA Green Book, 40 CFR 81",
            )
        )
        narrative.append(f"County is nonattainment for {listing}.")
    else:
        triggers.append(
            Trigger(
                "nonattainment_designation",
                False,
                f"{site.county} County, {site.state} is attainment or unclassifiable for all "
                f"criteria pollutants. PSD applies rather than nonattainment NSR.",
                "EPA Green Book, 40 CFR 81",
            )
        )

    # ---------------- Step 2: PSD major ----------------
    psd_hits = {
        p: t
        for p, t in est.tons_per_year.items()
        if p not in ("CO2e", "HCHO") and t >= psd_threshold
    }

    # ---------------- Step 3: pick the pathway ----------------
    offsets_required = None
    controlling_pollutant: str | None = None
    controlling_tpy: float | None = None
    applicable_threshold: float | None = None

    if na_hits:
        status, pollutant, tpy, threshold = max(na_hits, key=lambda h: h[2] / h[3])
        pathway = Pathway.MAJOR_NA_NSR
        controlling_pollutant, controlling_tpy, applicable_threshold = pollutant, tpy, threshold
        ratio = _OFFSET_RATIOS.get(status.classification.lower(), 1.0)
        offsets_required = tpy * ratio
        triggers.append(
            Trigger(
                "major_nonattainment_nsr",
                True,
                f"{pollutant} PTE of {tpy:,.0f} tpy is over the {threshold:,.0f} tpy major "
                f"threshold for a {status.classification} {status.pollutant} nonattainment area. "
                f"Requires LAER (no cost defense, unlike BACT) and {ratio:.2f}:1 emission "
                f"offsets — {offsets_required:,.0f} tons of verified reductions bought from "
                f"existing sources in the area.",
                "CAA 173; 40 CFR 51.165(a)(1)(iv)(A)",
                months_added=6.0,
            )
        )
        narrative.append(
            f"Nonattainment NSR: {pollutant} at {tpy:,.0f} tpy vs a {threshold:,.0f} tpy "
            f"threshold. Offsets needed: {offsets_required:,.0f} tons at {ratio:.2f}:1."
        )
        if ratio >= 1.3:
            hard_stops.append(
                f"Offsets at {ratio:.2f}:1 in a {status.classification} area. Offset credits in "
                f"severe and extreme areas are frequently unavailable at any price. Confirm the "
                f"state's ERC registry has {offsets_required:,.0f} tons before optioning the land."
            )

    elif psd_hits:
        controlling_pollutant, controlling_tpy = max(psd_hits.items(), key=lambda kv: kv[1])
        applicable_threshold = psd_threshold
        pathway = Pathway.MAJOR_PSD
        triggers.append(
            Trigger(
                "major_psd",
                True,
                f"{controlling_pollutant} PTE of {controlling_tpy:,.0f} tpy is over the "
                f"{psd_threshold:,.0f} tpy PSD major source threshold. Requires BACT, one year "
                f"of preconstruction ambient monitoring data or an approved waiver, AERMOD "
                f"dispersion modeling against NAAQS and increment, and public comment.",
                category.citation,
                months_added=0.0,
            )
        )
        narrative.append(
            f"Major PSD: {controlling_pollutant} at {controlling_tpy:,.0f} tpy vs a "
            f"{psd_threshold:,.0f} tpy threshold."
        )

    else:
        largest_pollutant, largest_tpy = est.max_criteria_tpy()
        controlling_pollutant, controlling_tpy = largest_pollutant, largest_tpy
        applicable_threshold = psd_threshold
        if config.enforceable_limit and config.run_hours < 8760:
            pathway = Pathway.SYNTHETIC_MINOR
            triggers.append(
                Trigger(
                    "synthetic_minor",
                    True,
                    f"Under the {psd_threshold:,.0f} tpy threshold only because of a federally "
                    f"enforceable {config.run_hours:,.0f} hr/yr cap. Largest pollutant "
                    f"{largest_pollutant} at {largest_tpy:,.0f} tpy. The cap becomes a permit "
                    f"condition with recordkeeping, and it is a real operating constraint — "
                    f"{config.run_hours / 8760:.0%} availability, not full-time baseload.",
                    "40 CFR 52.21(b)(4) definition of potential to emit",
                )
            )
            narrative.append(
                f"Synthetic minor: {largest_pollutant} held to {largest_tpy:,.0f} tpy by a "
                f"{config.run_hours:,.0f} hr/yr enforceable cap ({config.run_hours / 8760:.0%} "
                f"availability)."
            )
        elif (
            overlay.get("permit_by_rule")
            and largest_tpy < PBR_MAX_TPY
            and est.heat_input_mmbtu_hr <= PBR_MAX_HEAT_INPUT_MMBTU_HR
        ):
            pathway = Pathway.PERMIT_BY_RULE
            triggers.append(
                Trigger(
                    "permit_by_rule",
                    True,
                    f"{overlay['agency']} offers a permit by rule or general permit for sources "
                    f"this size. Largest pollutant {largest_pollutant} at {largest_tpy:,.0f} tpy.",
                    overlay["source"],
                )
            )
            narrative.append(f"Permit by rule available in {site.state}.")
        else:
            pathway = Pathway.MINOR_NSR
            triggers.append(
                Trigger(
                    "minor_nsr",
                    True,
                    f"Largest criteria pollutant {largest_pollutant} at {largest_tpy:,.0f} tpy, "
                    f"under the {psd_threshold:,.0f} tpy major threshold with room to spare. "
                    f"Minor NSR construction permit.",
                    "40 CFR 51.160; state minor NSR program",
                )
            )
            narrative.append(
                f"Minor NSR: {largest_pollutant} at {largest_tpy:,.0f} tpy, under "
                f"{psd_threshold:,.0f} tpy."
            )

    # ---------------- Step 4: overlays that add time ----------------

    # Class I areas. PSD requires notifying the Federal Land Manager for Class I
    # areas within 100 km, and the FLM's AQRV finding can stop a project on
    # visibility grounds alone even when the NAAQS analysis passes.
    if site.class_i_areas:
        nearest_name, nearest_km = min(site.class_i_areas, key=lambda a: a[1])
        major = pathway in (Pathway.MAJOR_PSD, Pathway.MAJOR_NA_NSR)
        if nearest_km <= 100:
            triggers.append(
                Trigger(
                    "class_i_aqrv",
                    True,
                    f"{nearest_name} is a Class I area {nearest_km:.0f} km away. Federal Land "
                    f"Manager notification is required and an air quality related values analysis "
                    f"(visibility, deposition) is expected. The FLM can object on AQRV grounds "
                    f"even when the NAAQS modeling passes."
                    + ("" if major else " Applies once the project is a major source; at minor "
                       "levels this is a flag rather than a requirement."),
                    "40 CFR 52.21(p); FLAG 2010 guidance",
                    months_added=6.0 if major else 0.0,
                )
            )
        elif nearest_km <= 300:
            triggers.append(
                Trigger(
                    "class_i_aqrv",
                    True,
                    f"{nearest_name} is a Class I area {nearest_km:.0f} km away — outside the "
                    f"100 km notification radius but inside the range where FLMs have asked for "
                    f"long-range visibility modeling on large sources.",
                    "FLAG 2010 guidance",
                    months_added=2.0 if major else 0.0,
                )
            )
        else:
            triggers.append(
                Trigger("class_i_aqrv", False, f"Nearest Class I area is {nearest_km:.0f} km away, "
                        f"well outside AQRV range.", "40 CFR 52.21(p)")
            )
    else:
        triggers.append(
            Trigger("class_i_aqrv", False, "No Class I area within screening range.",
                    "40 CFR 52.21(p)")
        )

    # PSD increment. A finite budget for how much the air can degrade in an area,
    # shared across every source. If prior sources consumed it, there is nothing
    # left to model into and the project has to buy reductions or move.
    for pollutant, consumed in site.increment_consumed.items():
        if consumed >= 0.8:
            triggers.append(
                Trigger(
                    "psd_increment_consumed",
                    True,
                    f"{consumed:.0%} of the {pollutant} PSD Class II increment in this area is "
                    f"already consumed by existing sources "
                    f"({len(site.major_sources_nearby)} major sources within screening radius). "
                    f"A new major source has to fit in what is left, which usually means tighter "
                    f"controls than BACT would otherwise require, or a stack height and location "
                    f"change, or waiting for someone else to shut down.",
                    "40 CFR 52.21(c); increment tracking via state SIP and EPA NEI",
                    months_added=6.0 if pathway in (Pathway.MAJOR_PSD, Pathway.MAJOR_NA_NSR) else 0.0,
                )
            )
            if consumed >= 0.95:
                hard_stops.append(
                    f"{pollutant} PSD increment is {consumed:.0%} consumed. A major source here "
                    f"may be un-permittable at any timeline."
                )
        elif consumed >= 0.5:
            triggers.append(
                Trigger(
                    "psd_increment_consumed",
                    True,
                    f"{consumed:.0%} of the {pollutant} PSD increment is consumed. Modeling will "
                    f"be tight but is likely to close.",
                    "40 CFR 52.21(c)",
                    months_added=2.0 if pathway in (Pathway.MAJOR_PSD, Pathway.MAJOR_NA_NSR) else 0.0,
                )
            )

    # Title V operating permit. Separate from the construction permit and runs
    # after it, though most states let you build while it is pending.
    max_criteria = max(
        (t for p, t in est.tons_per_year.items() if p not in ("CO2e", "HCHO")), default=0.0
    )
    hap = est.total_hap_tpy()
    if max_criteria >= 100 or hap >= 10:
        triggers.append(
            Trigger(
                "title_v",
                True,
                f"Title V operating permit required — "
                + (f"criteria pollutant PTE {max_criteria:,.0f} tpy over 100 tpy" if max_criteria >= 100
                   else f"single HAP (formaldehyde) PTE {hap:,.1f} tpy over 10 tpy")
                + ". Runs after the construction permit; usually does not block construction but "
                "does add annual compliance cost and a public comment window of its own.",
                "40 CFR Part 70",
                months_added=0.0,
            )
        )
    else:
        triggers.append(
            Trigger("title_v", False, f"Under Title V thresholds "
                    f"({max_criteria:,.0f} tpy criteria, {hap:,.1f} tpy HAP).", "40 CFR Part 70")
        )

    # NSPS / NESHAP. Not pathway-deciding but they set the control floor. The
    # January 2026 turbine rule left the trailer-mounted question open rather than
    # settling it; see the trigger detail and docs/evidence.md claim E1.
    if config.prime_mover in (PrimeMover.SIMPLE_CYCLE_TURBINE, PrimeMover.COMBINED_CYCLE_TURBINE):
        triggers.append(
            Trigger(
                "nsps_turbine",
                True,
                "NSPS Subpart KKKK applies, and EPA's 15 January 2026 rule (91 Fed. Reg. 1910) "
                "added Subpart KKKKa. That rule did not settle the trailer-mounted question, and "
                "it did not settle it in the direction most coverage claims. It finalised a "
                "conditional exclusion removing turbines from the 'stationary combustion turbine' "
                "definition where the unit qualifies as a nonroad engine and is certified under "
                "Title II. The exclusion is not operative: it takes effect only if EPA adopts "
                "Title II standards for portable turbines, a separate rulemaking that has not "
                "happened. Meanwhile the NAACP is asking a federal court in Mississippi to shut "
                "down 27 unpermitted turbines at xAI's Colossus 2, with a preliminary injunction "
                "hearing set for late August 2026. Underwriting a trailer-mounted fast path today "
                "means underwriting an open legal question, not a loophole.",
                "40 CFR 60 Subpart KKKK and new Subpart KKKKa; 91 Fed. Reg. 1910 (15 Jan 2026); "
                "NAACP v. xAI (N.D. Miss.), PI hearing late Aug 2026",
            )
        )
    elif config.prime_mover in (PrimeMover.RECIP_LEAN_BURN, PrimeMover.RECIP_RICH_BURN, PrimeMover.DIESEL_RECIP):
        triggers.append(
            Trigger(
                "nsps_rice",
                True,
                "NSPS Subpart IIII (compression ignition) or JJJJ (spark ignition) plus NESHAP "
                "Subpart ZZZZ apply. Emergency-engine exemptions do not apply to engines "
                "providing primary or peaking power — that distinction is where projects get "
                "caught after the fact.",
                "40 CFR 60 Subpart IIII/JJJJ; 40 CFR 63 Subpart ZZZZ",
            )
        )

    # State toxics programs. Separate from the federal HAP program and frequently
    # the thing that actually sets stack height.
    if overlay.get("state_toxics"):
        triggers.append(
            Trigger(
                "state_toxics",
                True,
                f"{site.state} runs a state air toxics program on top of the federal HAP rules. "
                f"Expect a separate modeling demonstration for formaldehyde and, for engines, "
                f"acrolein. This often drives stack height more than the NAAQS analysis does.",
                overlay["source"],
                months_added=2.0,
            )
        )

    if overlay.get("otr"):
        triggers.append(
            Trigger(
                "ozone_transport_region",
                True,
                f"{site.state} is in the Ozone Transport Region. NOx is subject to "
                f"nonattainment-style requirements statewide regardless of local monitor data, "
                f"and the major source threshold for VOC/NOx is 50 tpy.",
                "CAA 184; 40 CFR 51.165",
                months_added=3.0,
            )
        )

    if overlay.get("ej_denial_authority"):
        detail = (
            f"{site.state} gives the agency authority to deny a permit outright in an "
            f"overburdened community, independent of whether the emissions modeling passes. "
            f"This is a discretionary denial risk, not a timeline risk."
        )
        triggers.append(
            Trigger("ej_denial_authority", True, detail, overlay["source"], months_added=4.0)
        )
        if site.residential_within_1km and site.residential_within_1km > 500:
            hard_stops.append(
                f"{site.state} EJ law plus {site.residential_within_1km:,} residents within 1 km. "
                f"The agency can deny this permit on EJ grounds alone."
            )

    # Terrain. Complex terrain forces a more expensive dispersion model run and
    # usually a taller stack.
    if site.terrain_relief_m and site.terrain_relief_m > 150:
        triggers.append(
            Trigger(
                "complex_terrain",
                True,
                f"{site.terrain_relief_m:.0f} m of terrain relief within the modeling domain. "
                f"AERMOD in complex terrain, with terrain-following receptors, and likely a "
                f"taller stack than flat-site design would need.",
                "Mireye /v1/fetch terrain; EPA Appendix W",
                months_added=2.0,
            )
        )

    # Non-air blockers.
    if site.moratorium:
        triggers.append(
            Trigger(
                "county_moratorium",
                True,
                site.moratorium_note or f"{site.county} County has a data center moratorium in effect.",
                "hand-entered county file (ingest/counties.json)",
            )
        )
        hard_stops.append(
            f"{site.county} County moratorium: "
            f"{site.moratorium_note or 'no new data center approvals'}. The air permit timeline "
            f"is irrelevant until this lifts."
        )
    if site.zoning_posture == "hostile":
        triggers.append(
            Trigger(
                "zoning_posture",
                True,
                f"{site.county} County has denied or heavily conditioned recent data center "
                f"applications. Expect a special exception hearing with organised opposition.",
                "hand-entered county file (ingest/counties.json)",
                months_added=6.0,
            )
        )
    if site.litigation:
        triggers.append(
            Trigger(
                "litigation",
                True,
                f"{len(site.litigation)} federal case(s) touching this developer or county: "
                + "; ".join(site.litigation[:3]),
                "CourtListener / RECAP",
                months_added=3.0,
            )
        )

    # Gas reachability. New Mexico is the reference failure: the plant was
    # permittable, the pipeline that fed it was not.
    if config.fuel.value == "natural_gas" and site.gas_pipeline_km is not None:
        if site.gas_pipeline_km > 25:
            triggers.append(
                Trigger(
                    "gas_reachability",
                    True,
                    f"Nearest gas transmission pipeline is {site.gas_pipeline_km:.0f} km away. A "
                    f"lateral that long is its own permitting project, with its own easements and "
                    f"its own opposition. New Mexico blocked exactly this for a 2.45 GW Stargate "
                    f"site — the plant was not the problem, the pipeline was.",
                    "Mireye /v1/fetch utilities preset",
                    months_added=12.0,
                )
            )
            hard_stops.append(
                f"Gas pipeline is {site.gas_pipeline_km:.0f} km away. Fuel supply is a separate "
                f"permitting project and is the more likely failure point than the air permit."
            )
        elif site.gas_pipeline_km > 8:
            triggers.append(
                Trigger(
                    "gas_reachability",
                    True,
                    f"Gas pipeline {site.gas_pipeline_km:.0f} km away. A lateral is needed; "
                    f"budget easement acquisition in parallel with the air permit.",
                    "Mireye /v1/fetch utilities preset",
                    months_added=4.0,
                )
            )
        else:
            triggers.append(
                Trigger(
                    "gas_reachability",
                    False,
                    f"Gas pipeline {site.gas_pipeline_km:.1f} km away. Reachable.",
                    "Mireye /v1/fetch utilities preset",
                )
            )

    # Source aggregation. Splitting a plant to duck a threshold only works when
    # the pieces are genuinely separate sources, and agencies look hard at this.
    if config.units > 1:
        triggers.append(
            Trigger(
                "source_aggregation_risk",
                True,
                f"Config splits the plant into {config.units} units to stay under thresholds. "
                f"EPA aggregates sources that are contiguous or adjacent, under common control, "
                f"and in the same major industrial grouping. Units serving one data center campus "
                f"will almost certainly be aggregated. Treat this option as a conversation with "
                f"the agency, not a design decision.",
                "40 CFR 52.21(b)(6) 'building, structure, facility, or installation'",
                months_added=3.0,
            )
        )

    # ---------------- Step 5: timeline ----------------
    low, likely, high = _BASE_MONTHS[pathway]
    added = sum(t.months_added for t in triggers if t.fired)
    multiplier = overlay["multiplier"]
    months_low = low * multiplier + added * 0.5
    months_likely = likely * multiplier + added
    months_high = high * multiplier + added * 1.5

    narrative.append(
        f"{overlay['agency']} timeline multiplier {multiplier:.2f}x, plus {added:.0f} months from "
        f"{len([t for t in triggers if t.fired and t.months_added])} triggers. "
        f"{overlay['notes']}"
    )

    bact = est.significant() if pathway in (Pathway.MAJOR_PSD, Pathway.MAJOR_NA_NSR) else {}
    if bact:
        control_word = "LAER" if pathway is Pathway.MAJOR_NA_NSR else "BACT"
        narrative.append(
            f"{control_word} required for: "
            + ", ".join(
                f"{p} ({t:,.0f} tpy vs {SIGNIFICANT_EMISSION_RATES[p]:,.0f} tpy significance)"
                for p, t in sorted(bact.items(), key=lambda kv: -kv[1])
            )
        )

    return PathwayResult(
        pathway=pathway,
        months_low=months_low,
        months_likely=months_likely,
        months_high=months_high,
        source_category=category,
        triggers=triggers,
        controlling_pollutant=controlling_pollutant,
        controlling_tpy=controlling_tpy,
        applicable_threshold=applicable_threshold,
        bact_pollutants=bact,
        offsets_required_tons=offsets_required,
        hard_stops=hard_stops,
        narrative=narrative,
    )


def synthetic_minor_cap(est: EmissionsEstimate, site: SiteContext) -> dict | None:
    """What run-hour cap would drop this project to synthetic minor, and what does
    that cost in availability.

    Returns None if the project is already minor, or if no cap gets there.
    """
    config = est.config
    category = classify_source_category(config)
    threshold = category.threshold_tpy

    for status in site.nonattainment:
        thresholds = _NA_THRESHOLDS.get(status.pollutant, {})
        na_threshold = thresholds.get(status.classification.lower(), 100.0)
        threshold = min(threshold, na_threshold)

    pollutant, tpy = est.max_criteria_tpy()
    if tpy < threshold:
        return None

    hours = hours_for_tpy_target(config, pollutant, threshold * 0.9)  # 10% compliance margin
    if hours is None or hours < 1000:
        return {
            "feasible": False,
            "pollutant": pollutant,
            "threshold_tpy": threshold,
            "reason": (
                f"Holding {pollutant} under {threshold:,.0f} tpy would need a cap of "
                f"{hours:,.0f} hr/yr ({hours / 8760:.0%} availability)"
                if hours
                else f"No run-hour cap gets {pollutant} under {threshold:,.0f} tpy"
            )
            + ". That is not a data center power plant, it is a peaker.",
        }

    return {
        "feasible": True,
        "pollutant": pollutant,
        "threshold_tpy": threshold,
        "cap_hours": hours,
        "availability": hours / 8760,
        "reason": (
            f"A federally enforceable cap of {hours:,.0f} hr/yr ({hours / 8760:.0%} availability) "
            f"holds {pollutant} under {threshold:,.0f} tpy with a 10% compliance margin. That is "
            f"a real operating constraint — the plant cannot serve baseload load alone at that cap."
        ),
    }
