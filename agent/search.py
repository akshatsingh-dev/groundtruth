"""The act.

Two search loops. Everything up to here reasons and produces a report; this is
where the agent goes and does something about the answer.

1.  `search_alternate_sites` — generate candidate parcels in an expanding ring
    around a site that failed, resolve each one through the provider, run the
    full pathway on each, and rank them. It crosses county and state lines on
    purpose. That is the whole point: the permit you need is decided by where
    the land is, so the answer usually flips at a county line 20 miles away,
    not at the fence.

2.  `search_configs` — test design changes at the current parcel that move the
    pathway. Controls, prime mover, fuel, an enforceable run-hour cap. Every
    option carries a plain-English note on what it costs, because "accept a
    646 hr/yr cap" is not a design change, it is a different business.

Both loops preserve their reasoning: what was tried, what came back, why one
option beat another. A ranked list with no reasoning is not usable by the
person who has to defend the decision.

This module is the biggest provider consumer in the product, so it caches
aggressively (a dict keyed on rounded coordinates, shared across calls within
a run) and takes a budget object it will not spend past.

It talks to the provider interface and the two engines only. It does not
import `tools.py` or `planner.py`, so the search can be driven from a notebook,
a sweep job, or the agent loop without dragging the loop along.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from providers.base import (
    Fact,
    FactSet,
    Location,
    PhysicalFactsProvider,
    ProximityResult,
    ResolutionError,
)

from .emissions import (
    Control,
    EmissionsEstimate,
    Fuel,
    GenerationConfig,
    PrimeMover,
    estimate,
    hours_for_tpy_target,
)
from .pathway import (
    NonattainmentStatus,
    Pathway,
    PathwayResult,
    SiteContext,
    classify_source_category,
    determine_pathway,
    overlay_for,
    synthetic_minor_cap,
)

_EARTH_RADIUS_KM = 6371.0088
_KM_PER_MILE = 1.609344

#: Rings the alternate-site search walks outward through, in km. It starts
#: close because a short move is a cheap move, and stops at 120 km because past
#: that the fiber, the labour shed and the interconnect study all change and it
#: stops being the same project.
DEFAULT_RINGS_KM: tuple[float, ...] = (15.0, 30.0, 60.0, 120.0)

#: Presets fetched per candidate. Kept deliberately short — this is the credit
#: line item that dominates a run. Utilities carries pipeline and transmission
#: distance, which is what decides whether a candidate is reachable at all.
CANDIDATE_PRESETS: tuple[str, ...] = ("utilities",)
CANDIDATE_PROXIMITY: tuple[str, ...] = ("gas_pipeline", "transmission")


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def offset_point(lat: float, lon: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    """Destination point from (lat, lon) along a bearing. Great circle."""
    br = math.radians(bearing_deg)
    lat1, lon1 = math.radians(lat), math.radians(lon)
    d = distance_km / _EARTH_RADIUS_KM
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(br))
    lon2 = lon1 + math.atan2(
        math.sin(br) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), (math.degrees(lon2) + 540.0) % 360.0 - 180.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _compass(bearing_deg: float) -> str:
    points = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
    return points[int((bearing_deg % 360) / 22.5 + 0.5) % 16]


def ring_points(
    lat: float, lon: float, rings_km: Sequence[float], per_ring: int
) -> list[tuple[float, float, float, float]]:
    """(lat, lon, ring_km, bearing) for each candidate, inner rings first.

    Bearings are offset ring by ring so the candidates do not all sit on the
    same spokes — otherwise four rings of eight points is really eight
    directions sampled four times.
    """
    out: list[tuple[float, float, float, float]] = []
    for i, radius in enumerate(rings_km):
        step = 360.0 / max(per_ring, 1)
        skew = step * (i / max(len(rings_km), 1))
        for k in range(per_ring):
            bearing = (k * step + skew) % 360.0
            plat, plon = offset_point(lat, lon, bearing, radius)
            out.append((plat, plon, radius, bearing))
    return out


# --------------------------------------------------------------------------
# Alternate site search
# --------------------------------------------------------------------------


@dataclass
class AlternateSite:
    """One candidate parcel, screened all the way to a pathway."""

    label: str
    latitude: float
    longitude: float
    county: str
    state: str
    county_fips: str | None
    distance_km: float
    bearing_deg: float
    pathway: Pathway
    months_low: float
    months_likely: float
    months_high: float
    rank_delta: int
    months_saved: float
    hard_stops: list[str]
    triggers_cleared: list[str]
    triggers_added: list[str]
    gas_pipeline_km: float | None
    transmission_km: float | None
    confidence: float | None
    provenance: dict[str, dict]
    site: SiteContext | None = None

    @property
    def distance_miles(self) -> float:
        return self.distance_km / _KM_PER_MILE

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "county": self.county,
            "state": self.state,
            "county_fips": self.county_fips,
            "distance_km": round(self.distance_km, 1),
            "distance_miles": round(self.distance_miles, 1),
            "bearing": _compass(self.bearing_deg),
            "pathway": self.pathway.value,
            "pathway_label": self.pathway.label,
            "months_low": round(self.months_low, 1),
            "months_likely": round(self.months_likely, 1),
            "months_high": round(self.months_high, 1),
            "rank_delta": self.rank_delta,
            "months_saved": round(self.months_saved, 1),
            "hard_stops": self.hard_stops,
            "triggers_cleared": self.triggers_cleared,
            "triggers_added": self.triggers_added,
            "gas_pipeline_km": round(self.gas_pipeline_km, 1) if self.gas_pipeline_km else None,
            "transmission_km": round(self.transmission_km, 1) if self.transmission_km else None,
            "geocode_confidence": self.confidence,
            "provenance": self.provenance,
        }


@dataclass
class AlternateSiteSearchResult:
    origin_county: str
    origin_state: str
    origin_pathway: str
    origin_months_likely: float
    rings_km: list[float]
    candidates_considered: int
    candidates_resolved: int
    ranked: list[AlternateSite] = field(default_factory=list)
    best: AlternateSite | None = None
    delta_statement: str | None = None
    crossed_state_line: bool = False
    crossed_county_line: bool = False
    unresolved: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    credits_spent: int = 0

    def to_dict(self) -> dict:
        return {
            "origin": {
                "county": self.origin_county,
                "state": self.origin_state,
                "pathway": self.origin_pathway,
                "months_likely": round(self.origin_months_likely, 1),
            },
            "rings_km": self.rings_km,
            "candidates_considered": self.candidates_considered,
            "candidates_resolved": self.candidates_resolved,
            "unresolved_sample": self.unresolved[:3],
            "ranked": [c.to_dict() for c in self.ranked[:8]],
            "best": self.best.to_dict() if self.best else None,
            "delta_statement": self.delta_statement,
            "crossed_county_line": self.crossed_county_line,
            "crossed_state_line": self.crossed_state_line,
            "credits_spent": self.credits_spent,
            "notes": self.notes,
        }


def _key(lat: float, lon: float) -> tuple[float, float]:
    # ~100 m grid. Two candidates that land in the same cell are the same
    # screen, so resolve once.
    return (round(lat, 3), round(lon, 3))


def _spend(budget: Any, kind: str, units: int = 1) -> int:
    """Charge a budget object if one was supplied. Returns credits spent."""
    if budget is None:
        return 0
    spend = getattr(budget, "spend", None)
    if not callable(spend):
        return 0
    return int(spend(kind, units) or 0)


def _resolve_candidate(
    provider: PhysicalFactsProvider,
    lat: float,
    lon: float,
    presets: Sequence[str],
    targets: Sequence[str],
    budget: Any,
) -> tuple[Location, FactSet, dict[str, ProximityResult], int]:
    spent = 0
    spent += _spend(budget, "geocode")
    location = provider.geocode(f"{lat:.6f},{lon:.6f}", min_confidence=0.6)

    spent += _spend(budget, "lookup")
    facts = provider.lookup(location)

    if presets:
        spent += _spend(budget, "preset", len(presets))
        facts = facts.merge(provider.fetch(location, presets))

    proximity: dict[str, ProximityResult] = {}
    if targets:
        spent += _spend(budget, "proximity_target", len(targets))
        proximity = provider.proximity(location, targets)
    return location, facts, proximity, spent


def _site_from_candidate(
    location: Location,
    facts: FactSet,
    proximity: dict[str, ProximityResult],
    regulatory_lookup: Callable | None,
) -> SiteContext:
    county = location.county or facts.get("county") or "unknown"
    state = str(location.state or facts.get("state") or "??").upper()[:2]
    site = SiteContext(
        state=state,
        county=str(county),
        county_fips=location.county_fips or facts.get("county_fips"),
        latitude=location.latitude,
        longitude=location.longitude,
    )
    if "gas_pipeline" in proximity:
        site.gas_pipeline_km = proximity["gas_pipeline"].distance_km
    if "transmission" in proximity:
        site.transmission_km = proximity["transmission"].distance_km
        kv = proximity["transmission"].attributes.get("voltage_kv")
        if kv:
            try:
                site.transmission_kv = float(kv)
            except (TypeError, ValueError):
                pass
    relief = facts.get("terrain_relief_m")
    if relief is not None:
        try:
            site.terrain_relief_m = float(relief)
        except (TypeError, ValueError):
            pass
    site.provenance = facts.provenance()

    if regulatory_lookup is not None:
        try:
            reg = regulatory_lookup(site.county_fips, site.county, site.state)
        except Exception:
            reg = None
        if reg:
            statuses = reg.pop("_status_objects", None)
            if statuses is None:
                statuses = [
                    NonattainmentStatus(
                        pollutant=str(row.get("pollutant", "")).lower(),
                        classification=str(row.get("classification", "unclassified")).lower(),
                        area_name=str(row.get("area_name", "")),
                        source=str(row.get("source", "EPA Green Book")),
                        fetched=row.get("fetched"),
                    )
                    for row in reg.get("nonattainment", [])
                ]
            site.nonattainment = list(statuses)
            site.moratorium = bool(reg.get("moratorium", False))
            site.moratorium_note = reg.get("moratorium_note")
            site.zoning_posture = reg.get("zoning_posture")
            site.litigation = list(reg.get("litigation", []))
    return site


def search_alternate_sites(
    site: SiteContext,
    config: GenerationConfig,
    *,
    provider: PhysicalFactsProvider,
    regulatory_lookup: Callable | None = None,
    radius_km: float = 15.0,
    n_candidates: int = 24,
    baseline: PathwayResult | None = None,
    budget: Any = None,
    cache: dict | None = None,
    presets: Sequence[str] = CANDIDATE_PRESETS,
    proximity_targets: Sequence[str] = CANDIDATE_PROXIMITY,
    stop_when_minor: bool = True,
) -> AlternateSiteSearchResult:
    """Find a parcel nearby where the same plant gets a faster permit.

    `radius_km` sets the innermost ring; the loop expands outward through
    `DEFAULT_RINGS_KM` until it has spent its candidate allowance or found a
    site that is minor NSR or better with no hard stops.

    Returns candidates ranked by (pathway.rank, months_likely) — pathway first
    because a pathway change is a category change and a month change is not.
    """
    est = estimate(config)
    origin_result = baseline or determine_pathway(est, site)
    result = AlternateSiteSearchResult(
        origin_county=site.county,
        origin_state=site.state,
        origin_pathway=origin_result.pathway.value,
        origin_months_likely=origin_result.months_likely,
        rings_km=[],
        candidates_considered=0,
        candidates_resolved=0,
    )

    if site.latitude is None or site.longitude is None:
        result.notes.append(
            "No coordinate for the origin site, so there is no ring to search. "
            "This loop needs a resolved parcel."
        )
        return result

    rings = [r for r in DEFAULT_RINGS_KM if r >= radius_km] or [radius_km]
    if rings[0] > radius_km:
        rings = [radius_km] + rings
    result.rings_km = rings

    per_ring = max(1, math.ceil(n_candidates / len(rings)))
    points = ring_points(site.latitude, site.longitude, rings, per_ring)[:n_candidates]
    cache = cache if cache is not None else {}
    origin_fired = {t.name for t in origin_result.fired}

    for lat, lon, ring, bearing in points:
        result.candidates_considered += 1

        key = _key(lat, lon)
        cached = cache.get(key)
        if cached is not None:
            if isinstance(cached, dict) and cached.get("unresolved"):
                result.unresolved.append(cached)
                continue
            candidate_site = cached
            spent = 0
        else:
            try:
                location, facts, proximity, spent = _resolve_candidate(
                    provider, lat, lon, presets, proximity_targets, budget
                )
            except ResolutionError as exc:
                record = {
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "ring_km": ring,
                    "unresolved": True,
                    "reason": str(exc),
                }
                cache[key] = record
                result.unresolved.append(record)
                continue
            except Exception as exc:
                if exc.__class__.__name__ == "BudgetExhausted":
                    result.notes.append(
                        f"Stopped at candidate {result.candidates_considered}: {exc}"
                    )
                    break
                result.unresolved.append(
                    {
                        "latitude": round(lat, 5),
                        "longitude": round(lon, 5),
                        "ring_km": ring,
                        "unresolved": True,
                        "reason": f"{exc.__class__.__name__}: {exc}",
                    }
                )
                continue
            candidate_site = _site_from_candidate(location, facts, proximity, regulatory_lookup)
            candidate_site.provenance.setdefault(
                "geocode",
                {
                    "source": location.source or provider.name,
                    "fetched": location.fetched,
                    "confidence": location.confidence,
                },
            )
            cache[key] = candidate_site

        result.credits_spent += spent
        result.candidates_resolved += 1

        candidate_result = determine_pathway(est, candidate_site)
        fired = {t.name for t in candidate_result.fired}
        distance = haversine_km((site.latitude, site.longitude), (lat, lon))

        alt = AlternateSite(
            label=(
                f"{candidate_site.county} County, {candidate_site.state} "
                f"({lat:.4f}, {lon:.4f})"
            ),
            latitude=lat,
            longitude=lon,
            county=candidate_site.county,
            state=candidate_site.state,
            county_fips=candidate_site.county_fips,
            distance_km=distance,
            bearing_deg=bearing,
            pathway=candidate_result.pathway,
            months_low=candidate_result.months_low,
            months_likely=candidate_result.months_likely,
            months_high=candidate_result.months_high,
            rank_delta=origin_result.pathway.rank - candidate_result.pathway.rank,
            months_saved=origin_result.months_likely - candidate_result.months_likely,
            hard_stops=list(candidate_result.hard_stops),
            triggers_cleared=sorted(origin_fired - fired),
            triggers_added=sorted(fired - origin_fired),
            gas_pipeline_km=candidate_site.gas_pipeline_km,
            transmission_km=candidate_site.transmission_km,
            confidence=(candidate_site.provenance.get("geocode") or {}).get("confidence"),
            provenance=dict(candidate_site.provenance),
            site=candidate_site,
        )
        result.ranked.append(alt)

        if (
            stop_when_minor
            and not alt.hard_stops
            and alt.pathway.rank <= Pathway.MINOR_NSR.rank
            and alt.rank_delta > 0
        ):
            result.notes.append(
                f"Stopped early at ring {ring:.0f} km: found a {alt.pathway.label} site with no "
                f"hard stops. Searching further out costs credits for a smaller improvement."
            )
            break

    # Rank: pathway first, then timeline, then distance. A closer site only
    # wins as a tiebreak — a category change is worth more than 10 miles.
    result.ranked.sort(key=lambda c: (c.pathway.rank, len(c.hard_stops), c.months_likely, c.distance_km))

    improved = [
        c for c in result.ranked if c.rank_delta > 0 or (c.months_saved > 1 and not c.hard_stops)
    ]
    if improved:
        best = improved[0]
        result.best = best
        result.crossed_county_line = best.county.lower() != site.county.lower()
        result.crossed_state_line = best.state.upper() != site.state.upper()
        result.delta_statement = _delta_statement(best, origin_result)
    elif result.candidates_resolved == 0:
        result.notes.append(
            "No candidate parcel resolved. With NullProvider that is expected — the search "
            "refuses rather than inventing a parcel. Configure the provider to run it for real."
        )
    else:
        result.notes.append(
            f"Screened {result.candidates_resolved} parcels out to {rings[-1]:.0f} km and none "
            f"improved on {origin_result.pathway.label}. The constraint is not the parcel; it is "
            f"the config or the region."
        )
    return result


def _delta_statement(best: AlternateSite, origin: PathwayResult) -> str:
    parts = [
        f"Move {best.distance_miles:.0f} miles {_compass(best.bearing_deg)} to "
        f"{best.county} County, {best.state}."
    ]
    if best.rank_delta > 0:
        parts.append(f"{best.pathway.label} instead of {origin.pathway.label}.")
    if best.months_saved >= 1:
        parts.append(f"Save ~{best.months_saved:.0f} months.")
    if origin.hard_stops and not best.hard_stops:
        parts.append("Clears the hard stop at the announced site.")
    return " ".join(parts)


# --------------------------------------------------------------------------
# Config search
# --------------------------------------------------------------------------


@dataclass
class ConfigOption:
    label: str
    config: GenerationConfig
    pathway: Pathway
    months_low: float
    months_likely: float
    months_high: float
    rank_delta: int
    months_saved: float
    controlling_pollutant: str | None
    controlling_tpy: float | None
    availability: float
    cost_note: str
    hard_stops: list[str]
    triggers_cleared: list[str]
    warnings: list[str] = field(default_factory=list)
    estimate: EmissionsEstimate | None = None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "config": self.config.describe(),
            "pathway": self.pathway.value,
            "pathway_label": self.pathway.label,
            "months_low": round(self.months_low, 1),
            "months_likely": round(self.months_likely, 1),
            "months_high": round(self.months_high, 1),
            "rank_delta": self.rank_delta,
            "months_saved": round(self.months_saved, 1),
            "controlling_pollutant": self.controlling_pollutant,
            "controlling_tpy": round(self.controlling_tpy, 1) if self.controlling_tpy else None,
            "availability": round(self.availability, 3),
            "cost_note": self.cost_note,
            "hard_stops": self.hard_stops,
            "triggers_cleared": self.triggers_cleared,
            "warnings": self.warnings,
            "tons_per_year": {
                p: round(v, 1) for p, v in (self.estimate.tons_per_year.items() if self.estimate else [])
            },
        }


@dataclass
class ConfigSearchResult:
    baseline_pathway: str
    baseline_months_likely: float
    baseline_controlling: str | None
    options: list[ConfigOption] = field(default_factory=list)
    best: ConfigOption | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "baseline": {
                "pathway": self.baseline_pathway,
                "months_likely": round(self.baseline_months_likely, 1),
                "controlling_pollutant": self.baseline_controlling,
            },
            "options": [o.to_dict() for o in self.options],
            "best": self.best.to_dict() if self.best else None,
            "notes": self.notes,
        }


def _variant(base: GenerationConfig, **kwargs) -> GenerationConfig | None:
    fields = {
        "mw": base.mw,
        "prime_mover": base.prime_mover,
        "fuel": base.fuel,
        "controls": base.controls,
        "run_hours": base.run_hours,
        "enforceable_limit": base.enforceable_limit,
        "heat_rate_btu_kwh": base.heat_rate_btu_kwh,
        "units": base.units,
    }
    fields.update(kwargs)
    try:
        return GenerationConfig(**fields)
    except Exception:
        return None


def _with_controls(base: GenerationConfig, *add: Control) -> tuple[Control, ...]:
    out = list(base.controls)
    for control in add:
        if control not in out:
            out.append(control)
    return tuple(out)


#: Plain-English consequence notes. No invented dollar figures — a fabricated
#: capex number is worse than none, and the consequence is what the reader
#: actually needs.
_COST_NOTES = {
    "scr": (
        "SCR is the standard NOx answer and it is also the expensive one: catalyst, "
        "reactor volume in the exhaust path, and an ammonia or urea storage and handling "
        "system on site, which brings its own safety review and often its own local "
        "permit. Small heat-rate penalty from the pressure drop. It does nothing for CO."
    ),
    "oxidation_catalyst": (
        "An oxidation catalyst cuts CO by about 90% and VOC by about half. No reagent, no "
        "storage tank, small pressure drop, and it is cheap next to SCR. Worth checking "
        "first whenever CO is the pollutant sitting over the threshold — on an "
        "uncontrolled turbine that is more often the case than people expect."
    ),
    "dln": (
        "Dry low-NOx combustors are a turbine specification, not an add-on: you order the "
        "machine that way. No reagent and no aftertreatment, but the reduction is smaller "
        "than SCR and there are turndown and CO trade-offs at part load."
    ),
    "combined_cycle": (
        "Combined cycle burns roughly two thirds the fuel per MWh, so tons per year drop "
        "with no control equipment at all. The catch is legal, not thermal: the HRSG and "
        "steam turbine make the plant a 'fossil fuel-fired steam electric plant' over 250 "
        "MMBtu/hr, which drops the PSD major threshold from 250 tpy to 100 tpy. Check both "
        "directions before assuming it helps. Also adds water, a longer build, and a "
        "second machine in an order book already full."
    ),
    "run_hour_cap": (
        "A federally enforceable run-hour cap is the cheapest way to become a minor source "
        "and the most expensive way to run a data center. The cap becomes a permit "
        "condition with continuous recordkeeping and real enforcement exposure."
    ),
    "tier4": (
        "Tier 4 final engines are certified on output, so the limits do not scale with heat "
        "rate. Higher capital cost, DEF supply and storage on site, and aftertreatment that "
        "needs exhaust temperature — which conflicts with low-load standby operation."
    ),
    "fuel_cell": (
        "Solid oxide fuel cells emit almost no criteria pollutants, which usually takes the "
        "air permit off the critical path entirely. CO2 is not solved — they still burn gas. "
        "Much higher capital cost per MW, a supplier list you can count on one hand, and "
        "lead times that are themselves the constraint at data center scale."
    ),
    "split": (
        "Splitting the plant only works if the pieces are genuinely separate stationary "
        "sources. Units serving one campus, under one owner, will be aggregated. Treat this "
        "as a conversation with the agency, not a design decision."
    ),
}


def search_configs(
    site: SiteContext,
    config: GenerationConfig,
    baseline: PathwayResult | None = None,
) -> ConfigSearchResult:
    """Test design changes at the current parcel that move the pathway.

    Ranked by pathway improvement first, then months saved. The cost note is
    part of the result, not a footnote: an option that flips the pathway by
    turning a baseload plant into a peaker has not solved the problem.
    """
    base_est = estimate(config)
    base_result = baseline or determine_pathway(base_est, site)
    base_fired = {t.name for t in base_result.fired}
    base_pollutant, base_tpy = base_est.max_criteria_tpy()

    result = ConfigSearchResult(
        baseline_pathway=base_result.pathway.value,
        baseline_months_likely=base_result.months_likely,
        baseline_controlling=base_result.controlling_pollutant,
    )

    candidates: list[tuple[str, GenerationConfig | None, str, list[str]]] = []

    is_turbine = "turbine" in config.prime_mover.value
    is_engine = config.prime_mover in (
        PrimeMover.RECIP_LEAN_BURN,
        PrimeMover.RECIP_RICH_BURN,
        PrimeMover.DIESEL_RECIP,
    )

    if Control.SCR not in config.controls:
        candidates.append(
            ("Add SCR", _variant(config, controls=_with_controls(config, Control.SCR)),
             _COST_NOTES["scr"], [])
        )
    if Control.OXIDATION_CATALYST not in config.controls:
        candidates.append(
            (
                "Add oxidation catalyst",
                _variant(config, controls=_with_controls(config, Control.OXIDATION_CATALYST)),
                _COST_NOTES["oxidation_catalyst"],
                [],
            )
        )
    if Control.SCR not in config.controls or Control.OXIDATION_CATALYST not in config.controls:
        candidates.append(
            (
                "Add SCR + oxidation catalyst",
                _variant(
                    config,
                    controls=_with_controls(config, Control.SCR, Control.OXIDATION_CATALYST),
                ),
                _COST_NOTES["scr"] + " " + _COST_NOTES["oxidation_catalyst"],
                [],
            )
        )
    if is_turbine and Control.DLN not in config.controls:
        candidates.append(
            ("Add dry low-NOx combustors",
             _variant(config, controls=_with_controls(config, Control.DLN)),
             _COST_NOTES["dln"], [])
        )
    if config.prime_mover is PrimeMover.SIMPLE_CYCLE_TURBINE:
        candidates.append(
            (
                "Switch simple cycle to combined cycle",
                _variant(config, prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE),
                _COST_NOTES["combined_cycle"],
                [],
            )
        )
        candidates.append(
            (
                "Combined cycle + SCR + oxidation catalyst",
                _variant(
                    config,
                    prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
                    controls=_with_controls(config, Control.SCR, Control.OXIDATION_CATALYST),
                ),
                _COST_NOTES["combined_cycle"] + " " + _COST_NOTES["scr"],
                [],
            )
        )
    if config.prime_mover is PrimeMover.DIESEL_RECIP and Control.TIER4 not in config.controls:
        candidates.append(
            ("Tier 4 final certified engines",
             _variant(config, controls=_with_controls(config, Control.TIER4)),
             _COST_NOTES["tier4"], [])
        )
    if config.prime_mover is not PrimeMover.FUEL_CELL:
        candidates.append(
            (
                "Switch to solid oxide fuel cells",
                _variant(config, prime_mover=PrimeMover.FUEL_CELL, fuel=Fuel.NATURAL_GAS, controls=()),
                _COST_NOTES["fuel_cell"],
                [],
            )
        )

    # Synthetic minor: compute the cap the engine says is needed, on the base
    # config and on the best-controlled config, and report the availability
    # cost rather than presenting it as free.
    for cap_label, cap_base in (
        ("Accept a run-hour cap (as designed)", config),
        (
            "Accept a run-hour cap, with SCR and oxidation catalyst",
            _variant(config, controls=_with_controls(config, Control.SCR, Control.OXIDATION_CATALYST)),
        ),
    ):
        if cap_base is None:
            continue
        cap = synthetic_minor_cap(estimate(cap_base), site)
        if not cap:
            continue
        if not cap.get("feasible"):
            result.notes.append(f"{cap_label}: {cap['reason']}")
            continue
        hours = float(cap["cap_hours"])
        variant = _variant(cap_base, run_hours=hours, enforceable_limit=True)
        availability = hours / 8760.0
        note = _COST_NOTES["run_hour_cap"] + " " + (
            f"At {hours:,.0f} hr/yr the plant is available {availability:.0%} of the year. "
            + (
                "That is a peaker, not a data center plant — it cannot carry the load on its own."
                if availability < 0.55
                else "That can work as firming capacity behind a grid connection, but not as "
                "the sole source of power."
            )
        )
        candidates.append((cap_label, variant, note, []))

    if config.units == 1 and base_result.pathway.rank >= Pathway.MAJOR_PSD.rank:
        candidates.append(
            (
                "Split into two separate sources",
                _variant(config, units=2),
                _COST_NOTES["split"],
                ["Aggregation risk. EPA will almost certainly treat one campus as one source."],
            )
        )

    seen: set[str] = set()
    for label, variant, cost_note, warnings in candidates:
        if variant is None:
            continue
        signature = variant.describe()
        if signature == config.describe() or signature in seen:
            continue
        seen.add(signature)

        est = estimate(variant)
        outcome = determine_pathway(est, site)
        pollutant, tpy = est.max_criteria_tpy()
        fired = {t.name for t in outcome.fired}

        option = ConfigOption(
            label=label,
            config=variant,
            pathway=outcome.pathway,
            months_low=outcome.months_low,
            months_likely=outcome.months_likely,
            months_high=outcome.months_high,
            rank_delta=base_result.pathway.rank - outcome.pathway.rank,
            months_saved=base_result.months_likely - outcome.months_likely,
            controlling_pollutant=outcome.controlling_pollutant,
            controlling_tpy=outcome.controlling_tpy,
            availability=(variant.run_hours / 8760.0) if variant.enforceable_limit else 1.0,
            cost_note=cost_note,
            hard_stops=list(outcome.hard_stops),
            triggers_cleared=sorted(base_fired - fired),
            warnings=list(warnings),
            estimate=est,
        )
        if option.rank_delta < 0:
            option.warnings.append(
                f"This makes the pathway worse, not better: {base_result.pathway.label} -> "
                f"{outcome.pathway.label}. Kept in the list because the reason is instructive."
            )
        result.options.append(option)

    result.options.sort(key=lambda o: (-o.rank_delta, len(o.hard_stops), -o.months_saved, -o.availability))
    improving = [o for o in result.options if o.rank_delta > 0 or o.months_saved > 1]
    if improving:
        result.best = improving[0]
    else:
        result.notes.append(
            f"No design change at this parcel moves the project off {base_result.pathway.label}. "
            f"{base_pollutant} at {base_tpy:,.0f} tpy is over the threshold by too much for "
            f"controls to close. The lever is location, not equipment."
        )

    # The CO observation is worth stating explicitly, because it is the one
    # people miss on an uncontrolled combined-cycle plant.
    co_tpy = base_est.tons_per_year.get("CO", 0.0)
    if (
        Control.OXIDATION_CATALYST not in config.controls
        and base_result.controlling_pollutant == "CO"
    ):
        result.notes.append(
            f"CO at {co_tpy:,.0f} tpy is the pollutant deciding this pathway, not NOx. An "
            f"oxidation catalyst is the direct answer and is far cheaper than SCR. Check it "
            f"before pricing anything else."
        )
    return result
