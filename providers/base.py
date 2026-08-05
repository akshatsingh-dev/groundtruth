"""The physical-facts provider interface.

Everything the agent knows about the ground under a project comes through this
interface. Mireye is the US implementation. The interface exists because the
thesis — announced capacity is not deliverable capacity — is global, but Mireye
is US-only today. India has the same gap (announced 6-8 GW by 2030, realistically
3.4-3.6 GW) and no equivalent API. Keeping the agent behind an interface means
going international is a data problem, not a rewrite.

Every fact carries `source`, `fetched` and `confidence` from the moment it enters
the system and keeps them all the way to the output. A permitting engineer will
not act on a number they cannot trace, so an untraceable number is worthless here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


class ResolutionError(Exception):
    """The address could not be resolved with enough confidence to act on.

    Raised rather than returning a best guess. A centroid that is actually the
    county seat, silently substituted for a parcel, produces a permit answer for
    the wrong county. A refusal costs a retry; a wrong parcel costs a land option.
    """

    def __init__(self, query: str, confidence: float | None = None, detail: str = ""):
        self.query = query
        self.confidence = confidence
        super().__init__(
            f"Could not resolve {query!r} with sufficient confidence"
            + (f" (confidence {confidence:.2f})" if confidence is not None else "")
            + (f": {detail}" if detail else "")
        )


@dataclass(frozen=True)
class Fact:
    """One physical-world value with its provenance attached.

    `confidence` is the provider's own score where it gives one, otherwise None.
    Do not invent a confidence — an absent score is information.
    """

    key: str
    value: Any
    unit: str | None = None
    source: str | None = None
    fetched: str | None = None
    confidence: float | None = None
    note: str | None = None

    def cited(self) -> str:
        bits = [f"{self.key}: {self.value}"]
        if self.unit:
            bits[0] += f" {self.unit}"
        trail = ", ".join(
            part
            for part in (
                f"source: {self.source}" if self.source else None,
                f"fetched: {self.fetched}" if self.fetched else None,
                f"confidence: {self.confidence:.2f}" if self.confidence is not None else None,
            )
            if part
        )
        return f"{bits[0]} [{trail}]" if trail else bits[0]


@dataclass
class FactSet:
    """A bag of facts about one location, with provenance preserved."""

    facts: dict[str, Fact] = field(default_factory=dict)

    def add(self, fact: Fact) -> None:
        self.facts[fact.key] = fact

    def get(self, key: str, default: Any = None) -> Any:
        fact = self.facts.get(key)
        return fact.value if fact else default

    def fact(self, key: str) -> Fact | None:
        return self.facts.get(key)

    def provenance(self) -> dict[str, dict]:
        return {
            k: {"source": f.source, "fetched": f.fetched, "confidence": f.confidence}
            for k, f in self.facts.items()
        }

    def merge(self, other: "FactSet") -> "FactSet":
        merged = FactSet(dict(self.facts))
        merged.facts.update(other.facts)
        return merged

    def __contains__(self, key: str) -> bool:
        return key in self.facts

    def __len__(self) -> int:
        return len(self.facts)

    def cited_lines(self) -> list[str]:
        return [f.cited() for f in self.facts.values()]


@dataclass(frozen=True)
class Location:
    """A resolved place. `confidence` is the geocoder's, carried forward."""

    latitude: float
    longitude: float
    formatted_address: str | None = None
    county: str | None = None
    county_fips: str | None = None
    state: str | None = None
    tract: str | None = None
    parcel_id: str | None = None
    confidence: float | None = None
    source: str | None = None
    fetched: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def coord(self) -> tuple[float, float]:
        return (self.latitude, self.longitude)


@dataclass(frozen=True)
class ProximityResult:
    """Distance from a location to the nearest thing of some kind."""

    target: str
    distance_km: float
    name: str | None = None
    by_road: bool = False
    attributes: dict = field(default_factory=dict)
    source: str | None = None
    fetched: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PhysicalFactsProvider(ABC):
    """What the agent needs from the ground, independent of who supplies it.

    Implementations must never silently substitute a lower-confidence answer.
    Raise `ResolutionError` instead.
    """

    #: Human-readable name used in citations.
    name: str = "provider"
    #: Two-letter country codes this provider covers.
    coverage: tuple[str, ...] = ()

    @abstractmethod
    def geocode(self, query: str, min_confidence: float = 0.8) -> Location:
        """Address or coordinate string to a canonical location.

        Raises ResolutionError below `min_confidence` rather than guessing.
        """

    @abstractmethod
    def lookup(self, location: Location) -> FactSet:
        """Jurisdictional context: county, state, tract, timezone, elevation,
        flood status. One call rather than four."""

    @abstractmethod
    def fetch(self, location: Location, presets: Iterable[str]) -> FactSet:
        """Named field presets for a location.

        Preset names are provider-specific. The agent asks for what it needs by
        name and the provider maps it; see `PRESET_INTENTS` for the vocabulary
        the planner reasons in.
        """

    @abstractmethod
    def proximity(self, location: Location, targets: Iterable[str]) -> dict[str, ProximityResult]:
        """Nearest-by-road (or great circle, flagged) distance to named target
        classes: transmission, substation, gas_pipeline, airport, urban_area."""

    @abstractmethod
    def ask(self, location: Location, question: str) -> FactSet:
        """Open-ended query for the edges we have not scripted. Providers that
        support it should return the plan they ran so it can be replayed."""

    def field_request(
        self,
        field_name: str,
        description: str,
        example_locations: list[Any] | None = None,
        default_location: "Location | None" = None,
        **kwargs: Any,
    ) -> dict:
        """Ask the provider to add a field it does not have yet.

        Optional. Providers without this should leave it unimplemented — the
        agent treats it as "genuine gap, go find it elsewhere."

        `example_locations` is part of the interface rather than a Mireye
        detail: a request for a physical-world fact with no place attached is
        not answerable, and it is what the provider verifies the new field
        against. Callers that have a resolved site and no particular opinion
        should pass it as `default_location` and let the provider shape it.
        """
        raise NotImplementedError(f"{self.name} does not support field requests")

    def supports(self, capability: str) -> bool:
        return hasattr(self, capability) and callable(getattr(self, capability))


#: The vocabulary the planner reasons in. Each intent maps to whatever the
#: provider calls it. The planner picks intents based on what the *pathway
#: question* needs, not from a fixed list — a combined-cycle plant near complex
#: terrain needs terrain and dispersion inputs that a fuel cell config does not.
PRESET_INTENTS: dict[str, str] = {
    "parcel": "Parcel boundary, acreage, land use, assessed value",
    "terrain": "Elevation, slope, aspect, relief — drives dispersion modeling",
    "land_cover": "Land cover, canopy, NDVI — surface roughness for AERMOD",
    "utilities": "Transmission, substation, power plant, gas pipeline, utility territory",
    "grid_interconnect": "Interconnection queue, substation capacity, ISO/RTO",
    "data_center_siting": "Full data center site screen",
    "site_selection": "Broad site suitability",
    "flood_risk": "FEMA flood zone, floodway, BFE",
    "natural_hazard": "Seismic, wind, hail, tornado, subsidence",
    "wildfire": "Wildfire hazard potential",
    "points_of_interest": "Schools, hospitals, residential POI — opposition and receptor inputs",
    "demographics": "Population, density, EJ indicators within radius",
    "water": "Surface water, groundwater, wetlands",
    "soil": "Soil bearing, shrink-swell, depth to bedrock",
}

#: Proximity targets the agent asks for by name.
PROXIMITY_TARGETS: dict[str, str] = {
    "transmission": "Nearest transmission line, with voltage",
    "substation": "Nearest substation",
    "gas_pipeline": "Nearest gas transmission pipeline — the New Mexico failure mode",
    "power_plant": "Nearest operating generation",
    "airport": "Nearest airport — stack height and airspace review",
    "urban_area": "Nearest urban area — receptors and opposition",
    "school": "Nearest school — receptor and political sensitivity",
    "hospital": "Nearest hospital — sensitive receptor",
    "rail": "Nearest rail — construction logistics",
    "water_body": "Nearest surface water — cooling and discharge",
}


class NullProvider(PhysicalFactsProvider):
    """A provider that has no data. Used so the pathway engine, the search loops
    and the tests can run with no API key and no network.

    It refuses rather than fabricating: every call raises or returns empty. Any
    code path that quietly produces a plausible-looking answer against this
    provider is a code path that would fabricate against a real one.
    """

    name = "null"
    coverage = ()

    def geocode(self, query: str, min_confidence: float = 0.8) -> Location:
        raise ResolutionError(query, None, "NullProvider has no data; configure MIREYE_API_KEY")

    def lookup(self, location: Location) -> FactSet:
        return FactSet()

    def fetch(self, location: Location, presets: Iterable[str]) -> FactSet:
        return FactSet()

    def proximity(self, location: Location, targets: Iterable[str]) -> dict[str, ProximityResult]:
        return {}

    def ask(self, location: Location, question: str) -> FactSet:
        return FactSet()
