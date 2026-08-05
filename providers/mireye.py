"""Mireye — the US implementation of PhysicalFactsProvider.

Mireye is the physical layer for this build: terrain, land cover, utilities,
grid, hazards, air-quality designations and Class I area distance, every value
carrying its federal source and a fetch timestamp. This module is the only place
in the codebase that knows what Mireye calls things. The planner reasons in the
intent names in `base.PRESET_INTENTS` and `base.PROXIMITY_TARGETS`; this file
owns the translation into presets, field names and curated proximity sets. That
is the whole point of the interface — when the vocabulary changes, or when a
second country needs a different provider, exactly one file moves.

Two decisions worth stating up front, because they cost credits and they are
deliberate.

`geocode()` refuses rather than guessing. Mireye already refuses centroid-grade
matches and sub-0.8 similarity server-side; we add our own floor on top of the
`confidence` that `/v1/lookup` returns. A street-interpolated coordinate can be
~2,872 m off in rural areas, which is routinely a different county — and county
is what decides the permit pathway. A refusal costs a retry. A wrong parcel
costs a land option.

Proximity defaults to straight-line, not by-road. Mireye prices `/v1/proximity`
driving calls at 12 credits each and a single `nearest` with driving mode is 60
credits; the national sweep at three targets per county would be ~565,000
credits on that alone. Geodesic mode is 2. The sweep runs geodesic and the one
filmed project screen can opt into `mode="driving"`. `ProximityResult.by_road`
carries which one you got, so nothing downstream has to guess.

Every shape and price in this file was verified against the live API on
5 Aug 2026 with a real Loudoun County, VA data center address. Raw captures are
in `docs/api-captures/`; the reconciliation is in `docs/mireye-api-notes.md`.
Nothing here is guessed from the docs any more, and the two places where their
docs contradict themselves are settled by measurement and marked VERIFIED.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Iterable

import httpx

from .base import (
    Fact,
    FactSet,
    Location,
    PhysicalFactsProvider,
    ProximityResult,
    ResolutionError,
    now_iso,
)
from .cache import ResponseCache

DEFAULT_BASE_URL = "https://api.mireye.com"

#: Mireye's per-field confidence is a bucket string, not a number, but
#: `Fact.confidence` is typed `float | None`. This is the translation table and
#: it is the only place a bucket becomes a number. `unknown` maps to None rather
#: than to a low score, because "we did not measure this" and "we measured this
#: and it is bad" are different facts. The raw bucket is preserved verbatim in
#: `Fact.note`, so nothing is lost and the mapping is reversible.
CONFIDENCE_BUCKETS: dict[str, float | None] = {
    "high": 0.9,
    "medium": 0.6,
    "low": 0.3,
    "unknown": None,
}

#: Credit prices, from the public `GET /v1/meta/plans`.
#:
#: VERIFIED live 5 Aug 2026 against `GET /v1/users/me/usage`. Nineteen calls on
#: the build plan billed 836 credits and the computed total from this table was
#: 836 — exact. Measured per call type: geocode 1, lookup without parcel 1,
#: lookup with parcel 300, fetch 1 per field (a preset bills its full expansion,
#: so data_center_siting is 106), fetch/batch 1 per field per succeeding
#: location, ask 10, proximity nearest straightline 2, proximity nearest driving
#: n=1 60. Every 4xx we triggered billed 0.
#:
#: `GET /v1/users/me/usage` is eventually consistent, not a live meter — it
#: lagged by tens of seconds and briefly read *lower* than a previous poll
#: during the run. Reconcile at the end of a sweep, not per call.
CREDIT_COSTS: dict[str, float] = {
    "ask": 10.0,
    "fetch_per_field": 1.0,
    "geocode": 1.0,
    "proximity_per_driving_calc": 12.0,
    "proximity_per_address_locator": 1.0,
    "proximity_distance_min": 2.0,
    "proximity_nearest_min": 2.0,
    "proximity_screen_min": 5.0,
    "proximity_labor_shed_min": 25.0,
}

#: `/v1/lookup` with a parcel, and any `/v1/fetch` touching a parcel-group
#: field, bills this once per location. It is per-record-licensed county data
#: (Regrid). 300 on free/build/growth, 150 on scale/market — we use the higher
#: number so a budget is never a surprise.
#:
#: VERIFIED: `{"address": ..., "fields": ["parcel_id", "parcel_area_m2"]}` billed
#: exactly 300, not 302. The group is charged once and its members are NOT also
#: billed per field — only the non-parcel fields in the same request are. So
#: `site_selection` (72 fields, 9 of them parcel-group) is 63 + 300 = 363
#: credits per location, not 72 and not 372. `data_center_siting` contains no
#: parcel-group field and bills a flat 106.
RESOLVE_CREDITS = 300.0

#: Fields that trigger RESOLVE_CREDITS. Published on GET /v1/meta/plans as
#: `parcel_field_group`.
PARCEL_FIELD_GROUP: frozenset[str] = frozenset(
    {
        "developable_acres_proxy",
        "onsite_solar_potential_mwac_high",
        "onsite_solar_potential_mwac_low",
        "parcel_address",
        "parcel_apn",
        "parcel_area_m2",
        "parcel_boundary_geojson",
        "parcel_data_source",
        "parcel_geometry_wkt",
        "parcel_id",
        "parcel_match_distance_m",
        "parcel_match_radius_m",
        "parcel_match_type",
        "parcel_owner",
        "parcel_zoning",
        "wetland_acres_on_parcel",
        "wetland_fraction_of_parcel",
    }
)

#: The fifteen real preset names accepted by `/v1/fetch`.
MIREYE_PRESETS: frozenset[str] = frozenset(
    {
        "terrain",
        "flood_risk",
        "wildfire_underwrite",
        "land_cover",
        "site_selection",
        "building_lookup",
        "points_of_interest",
        "utilities",
        "boundaries",
        "solar_siting",
        "wind_siting",
        "storage_siting",
        "data_center_siting",
        "grid_interconnect",
        "natural_hazard",
    }
)

#: The vocabulary mapping. Keys are the intent names in `base.PRESET_INTENTS`;
#: the planner never sees the right-hand side. A string value is a real Mireye
#: preset. A tuple is an explicit field list, used where Mireye has the data but
#: has no preset that isolates it — `parcel`, `demographics`, `water` and `soil`
#: all fall out of larger presets, and naming the fields directly is both
#: cheaper (1 credit per field) and honest about what we actually asked for.
PRESET_MAP: dict[str, str | tuple[str, ...]] = {
    "terrain": "terrain",
    "land_cover": "land_cover",
    "utilities": "utilities",
    "grid_interconnect": "grid_interconnect",
    "data_center_siting": "data_center_siting",
    "site_selection": "site_selection",
    "flood_risk": "flood_risk",
    "natural_hazard": "natural_hazard",
    "wildfire": "wildfire_underwrite",
    "points_of_interest": "points_of_interest",
    # Parcel geometry and tenure. Every one of these is in PARCEL_FIELD_GROUP,
    # so this intent costs RESOLVE_CREDITS on top. `/v1/lookup` with
    # include_parcel=True returns the same record for the same 300 credits plus
    # owner/land-use/sale history, so prefer `resolve(..., include_parcel=True)`
    # when you want the parcel and are already resolving.
    "parcel": (
        "parcel_id",
        "parcel_apn",
        "parcel_area_m2",
        "parcel_zoning",
        "parcel_owner",
        "parcel_boundary_geojson",
    ),
    # Receptors and the population that shows up to a public comment hearing.
    # Mireye has no environmental-justice or race/income-at-a-point layer, which
    # is a real gap for the NJ EJ-law failure mode — see the field-request list
    # in docs/mireye-api-notes.md.
    "demographics": (
        "housing_units_within_1km",
        "housing_units_density_per_km2",
        "tract_population",
        "tract_civilian_labor_force",
        "county_population",
        "county_population_growth_1yr_pct",
        "county_median_household_income",
    ),
    "water": (
        "within_water_service_area",
        "water_system_name",
        "nearest_water_service_area_distance_m",
        "surface_water_permanence_pct",
        "surface_water_supply_use_index_huc12",
        "huc12_thermoelectric_consumptive_use_m3_per_day",
        "nearest_groundwater_well_depth_to_water_m",
        "nearest_usgs_gage_distance_m",
        "nearest_usgs_gage_daily_discharge_cfs",
        "intersects_wetland",
        "nearest_wetland_distance_m",
        "nearest_wastewater_plant_distance_m",
    ),
    "soil": (
        "soil_hydrologic_group",
        "soil_drainage_class",
        "soil_shrink_swell_class",
        "soil_restrictive_layer_depth_cm",
        "soil_restrictive_layer_kind",
        "soil_erodibility_k_factor",
        "bedrock_depth_cm",
    ),
}

#: Air-permit fields that do not belong to any single intent but decide the
#: pathway. `data_center_siting` already contains all of them — this list exists
#: so a caller who only wants the regulatory read can ask for nine fields
#: (9 credits) instead of the whole 106-field preset.
AIR_PERMIT_FIELDS: tuple[str, ...] = (
    "in_air_quality_nonattainment",
    "air_quality_nonattainment_pollutants",
    "in_air_quality_maintenance",
    "air_quality_maintenance_pollutants",
    "air_quality_worst_classification",
    "air_district_name",
    "nearest_class_i_area_distance_m",
    "nearest_class_i_area_name",
    "nearest_class_i_area_agency",
)

#: How each `base.PROXIMITY_TARGETS` name is actually answered.
#:
#: `set` is one of Mireye's six curated `/v1/proximity` `nearest` sets, which are
#: the only ones that exist: @airports, @substations, @power_plants, @rail,
#: @ports, @urban_areas. `fields` is the `/v1/fetch` route — a geodesic distance
#: field plus an optional name and attribute fields.
#:
#: Note what is missing from the curated sets: transmission lines, gas
#: pipelines, schools and hospitals. Those are fetch fields only. The build brief
#: assumed /v1/proximity covered the whole power layer; it does not, and routing
#: each target to whichever surface answers it is why this table exists.
_PROXIMITY_ROUTES: dict[str, dict[str, Any]] = {
    "transmission": {
        "set": None,
        "distance_field": "nearest_transmission_line_distance_m",
        "attribute_fields": (
            "nearest_transmission_line_voltage_kv",
            "nearest_transmission_line_voltage_class",
            "nearest_transmission_line_status",
            "nearest_transmission_line_owner",
            "max_transmission_line_voltage_kv_within_radius",
        ),
    },
    "substation": {
        "set": "@substations",
        "distance_field": "nearest_substation_distance_m",
        "attribute_fields": (
            "nearest_substation_max_voltage_kv",
            "nearest_substation_status",
        ),
    },
    "gas_pipeline": {
        "set": None,
        "distance_field": "nearest_gas_pipeline_distance_m",
        "attribute_fields": ("nearest_interstate_gas_pipeline_distance_m",),
    },
    "power_plant": {
        "set": "@power_plants",
        "distance_field": "nearest_power_plant_distance_m",
        "name_field": "nearest_power_plant_name",
        "attribute_fields": (
            "nearest_power_plant_capacity_mw",
            "nearest_power_plant_primary_fuel",
            "nearest_power_plant_operator",
            "nearest_power_plant_technology",
        ),
    },
    "airport": {
        "set": "@airports",
        "distance_field": "nearest_airport_distance_m",
        "name_field": "nearest_airport_name",
        "attribute_fields": (),
        # The two surfaces disagree, and it matters for a stack-height review.
        # The @airports curated set filters FAA NASR to public-use airports
        # (facility_type == "airport", heliports excluded). The
        # nearest_airport_* fetch fields do not filter at all: at the Ashburn
        # test site the "nearest airport" came back as INOVA LOUDOUN HOSPITAL
        # at 6.2 km, which is a hospital helipad. For FAR Part 77 airspace
        # screening on a 60 m stack that is the wrong answer. Treat a
        # fetch-backed airport distance as "nearest aviation facility" and
        # confirm with the curated set before relying on it — noting that the
        # curated set was returning 503 on 5 Aug 2026.
        "note": "FAA NASR unfiltered — includes heliports, so this can be a hospital "
        "helipad rather than a public-use airport",
    },
    "urban_area": {
        "set": "@urban_areas",
        "distance_field": "nearest_urban_area_distance_m",
        "attribute_fields": (),
    },
    "school": {
        "set": None,
        "distance_field": "nearest_school_distance_m",
        "name_field": "nearest_school_name",
        "attribute_fields": (),
    },
    "hospital": {
        "set": None,
        "distance_field": "nearest_hospital_distance_m",
        "name_field": "nearest_hospital_name",
        "attribute_fields": (),
    },
    "rail": {
        "set": "@rail",
        "distance_field": "nearest_rail_line_distance_m",
        "attribute_fields": ("nearest_long_haul_rail_corridor_distance_m",),
    },
    # Mireye has no nearest-surface-water distance field — only
    # `nearest_waterbody_name`. The closest measured distance is to the nearest
    # USGS stream gage, which is a different thing and is flagged as such in the
    # result note. This is one of the gaps worth a /v1/field-requests filing.
    "water_body": {
        "set": None,
        "distance_field": "nearest_usgs_gage_distance_m",
        "name_field": "nearest_usgs_gage_name",
        "attribute_fields": ("nearest_waterbody_name", "nearest_usgs_gage_daily_discharge_cfs"),
        "note": "nearest USGS stream gage, not the nearest waterbody — Mireye has no "
        "nearest_waterbody_distance_m field",
    },
}

#: `/v1/lookup` returns no per-field provenance, so we attribute from Mireye's
#: documented source list. Per-fact confidence stays None: the one `confidence`
#: on the response describes the *resolution*, not the elevation reading, and
#: reusing it per field would be inventing a score.
_LOOKUP_SOURCES: dict[str, str] = {
    "county_fips": "US Census Geocoder",
    "county": "US Census Geocoder",
    "state": "US Census Geocoder",
    "state_fips": "US Census Geocoder",
    "tract_geoid": "US Census Geocoder (2020 vintage)",
    "block_group_geoid": "US Census Geocoder",
    "block_geoid": "US Census Geocoder",
    "congressional_district": "US Census Geocoder",
    "cbsa_name": "US Census Geocoder",
    "cbsa_code": "US Census Geocoder",
    "elevation_m": "USGS 3DEP/EPQS",
    "fema_flood_zone": "FEMA NFHL",
    "within_floodplain": "FEMA NFHL",
    "coastal_high_hazard": "FEMA NFHL",
    "in_opportunity_zone": "US Treasury Qualified Opportunity Zones",
    "opportunity_zone_tract_geoid": "US Treasury Qualified Opportunity Zones",
    "timezone": "IANA tz database",
    "county_market": "US Census PEP/BPS/ACS, FHFA, BLS QCEW",
}

#: `/v1/lookup` returns the full state name; `pathway.SiteContext.state` wants
#: two letters. Getting this wrong silently applies the wrong state overlay.
_STATE_ABBREV: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "puerto rico": "PR", "guam": "GU", "american samoa": "AS",
    "united states virgin islands": "VI", "u.s. virgin islands": "VI",
    "northern mariana islands": "MP",
}

#: Mireye's US envelope. A coordinate outside it is `400 coord_out_of_bounds`,
#: which we would rather catch before spending a call.
US_ENVELOPE = {"lat_min": 18.0, "lat_max": 72.0, "lng_min": -180.0, "lng_max": -65.0}

#: `503 geocodio_distance_budget_exhausted` is the one failure Mireye bills for
#: work it never did, and it is retryable with `Retry-After: 3600`. Retrying it
#: inside our backoff loop would burn credits an hour at a time for nothing.
_NEVER_RETRY_INLINE = frozenset({"geocodio_distance_budget_exhausted"})


class MireyeError(RuntimeError):
    """A structured Mireye API failure.

    Mireye returns `{"detail": {"error", "message", "retryable"}}` on every
    endpoint. `retryable` is the field to branch on, not the status code — a
    `502 ask_upstream_error` caused by an upstream 4xx will never succeed on a
    retry, and their docs say so explicitly.
    """

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        retryable: bool = False,
        request_id: str | None = None,
        body: Any = None,
    ):
        self.status = status
        self.code = code
        self.retryable = retryable
        self.request_id = request_id
        self.body = body
        super().__init__(f"{status} {code}: {message}" + (f" [{request_id}]" if request_id else ""))


class _RateLimiter:
    """A shared minimum-interval limiter.

    Mireye publishes requests-per-minute per plan (20 free, 60 build, 300
    growth). A ThreadPoolExecutor of 8 workers will blow through 60 rpm in about
    eight seconds and spend the rest of the sweep collecting 429s. Spacing calls
    at 60/rpm seconds means the workers queue here instead of at the API, and
    the sweep finishes in predictable time.
    """

    def __init__(self, rpm: float):
        self.min_interval = 60.0 / rpm if rpm and rpm > 0 else 0.0
        self._lock = threading.Lock()
        self._next_at = 0.0

    def acquire(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            self._next_at = max(now, self._next_at) + self.min_interval
        if wait > 0:
            time.sleep(wait)


def _bucket_to_confidence(bucket: Any) -> float | None:
    """Translate Mireye's confidence bucket to a float, or None if it has none.

    Anything unrecognised returns None rather than a guess. An absent score is
    information; a fabricated one is a liability in a permitting memo.
    """
    if isinstance(bucket, (int, float)) and not isinstance(bucket, bool):
        return float(bucket)
    if isinstance(bucket, str):
        return CONFIDENCE_BUCKETS.get(bucket.strip().lower())
    return None


def _detail_of(body: Any) -> dict:
    """Pull the structured error out of a response body, tolerating both shapes.

    Most errors are `{"detail": {"error", "message", "retryable"}}`. FastAPI
    validation errors are `{"detail": [ ... ]}` instead, which is why this
    checks the type before indexing.
    """
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict):
            return detail
        if isinstance(detail, list):
            return {"error": "validation_error", "message": json.dumps(detail)[:500]}
    return {}


class MireyeProvider(PhysicalFactsProvider):
    """Mireye Earth, wrapped so the agent only ever sees `Fact`s with sources.

    Every method goes through the response cache. Re-running the national sweep
    after a scoring change costs nothing, which is the only reason iterating on
    it is affordable.
    """

    name = "mireye"
    coverage = ("US",)

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        cache: ResponseCache | None = None,
        timeout: float = 120.0,
        max_retries: int = 4,
        rpm: float | None = None,
        proximity_mode: str = "straightline",
        min_confidence: float = 0.8,
        catalog_path: str = os.path.join("data", "mireye_catalog.json"),
    ):
        self.api_key = api_key or os.environ.get("MIREYE_API_KEY") or os.environ.get(
            "MIREYE_API_TOKEN"
        )
        self.base_url = (
            base_url or os.environ.get("MIREYE_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.cache = cache if cache is not None else ResponseCache()
        # 120 s minimum: /v1/ask is hard-bounded at 110 s server-side and a
        # shorter client timeout aborts requests that keep running and keep
        # billing. /v1/fetch/batch is worst-case ~90 s.
        self.timeout = max(timeout, 120.0)
        self.max_retries = max_retries
        self.proximity_mode = proximity_mode
        self.min_confidence = min_confidence
        self.catalog_path = catalog_path

        env_rpm = os.environ.get("MIREYE_RPM")
        self._limiter = _RateLimiter(float(rpm if rpm is not None else (env_rpm or 60)))

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "user-agent": "deliverable/0.1 (Mireye Build Challenge)",
            },
        )

        self._counter_lock = threading.Lock()
        self.calls = 0
        self.credits = 0.0
        self.cache_hits = 0
        self.errors = 0

        self._catalog: dict | None = None
        self._catalog_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()
        self.cache.close()

    def __enter__(self) -> "MireyeProvider":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise MireyeError(
                0,
                "no_api_key",
                "MIREYE_API_KEY is not set. Create a token at https://www.mireye.com/account "
                "and put it in .env. Never guess or fabricate a token.",
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            # Mireye echoes this and binds it to their log lines, which turns a
            # support thread into one grep.
            "X-Request-ID": f"deliverable-{uuid.uuid4().hex[:16]}",
        }

    def _count(self, credits: float, cached: bool) -> None:
        with self._counter_lock:
            if cached:
                self.cache_hits += 1
            else:
                self.calls += 1
                self.credits += credits

    def _post(
        self,
        path: str,
        payload: dict,
        credit_estimate: float = 0.0,
        max_age_days: float | None = None,
        cache_errors: bool = True,
    ) -> Any:
        """POST with cache, rate limit and backoff. Returns the parsed body.

        A cached non-2xx is replayed as the same `MireyeError` it was the first
        time. That matters for the sweep: `404 address_too_coarse` is a stable
        refusal, and rediscovering it on every run would cost a geocode credit
        per bad address, per run.
        """
        cached = self.cache.get(path, payload, max_age_days=max_age_days)
        if cached is not None:
            self._count(0.0, cached=True)
            if cached.ok:
                return cached.body
            detail = _detail_of(cached.body)
            raise MireyeError(
                cached.status,
                detail.get("error", "cached_error"),
                detail.get("message", ""),
                retryable=False,  # a replay is never worth retrying; purge to refetch
                body=cached.body,
            )

        last: MireyeError | None = None
        for attempt in range(self.max_retries + 1):
            self._limiter.acquire()
            headers = self._headers()
            try:
                response = self._client.post(path, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                last = MireyeError(504, "client_timeout", str(exc), retryable=True)
            except httpx.HTTPError as exc:
                last = MireyeError(0, "client_transport_error", str(exc), retryable=True)
            else:
                try:
                    body = response.json()
                except ValueError:
                    body = {"raw": response.text[:2000]}

                if response.status_code < 400:
                    credits = self._credits_for(path, payload, body, credit_estimate)
                    self.cache.set(path, payload, response.status_code, body, credits)
                    self._count(credits, cached=False)
                    return body

                detail = _detail_of(body)
                code = detail.get("error", f"http_{response.status_code}")
                retryable = detail.get("retryable")
                if retryable is None:
                    # No `retryable` key: fall back to the status code. 4xx other
                    # than 429 is a caller mistake and will not fix itself.
                    retryable = response.status_code in (429, 500, 502, 503, 504)
                last = MireyeError(
                    response.status_code,
                    code,
                    detail.get("message", response.text[:300]),
                    retryable=bool(retryable),
                    request_id=response.headers.get("x-request-id"),
                    body=body,
                )

                if not last.retryable:
                    # Stable refusals are worth caching so a re-run is free.
                    # Auth failures are not — the key gets fixed and the run
                    # repeats, and a cached 401 would survive the fix.
                    if cache_errors and not code.startswith("auth_"):
                        self.cache.set(path, payload, response.status_code, body, 0.0)
                    with self._counter_lock:
                        self.errors += 1
                        self.calls += 1
                    raise last

                if code in _NEVER_RETRY_INLINE:
                    # Billed even though no upstream call was made, and the
                    # window is an hour. Surface it; do not loop on it.
                    with self._counter_lock:
                        self.errors += 1
                        self.calls += 1
                    raise last

                retry_after = response.headers.get("retry-after")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 0.0
                delay = min(max(delay, 2.0 * (2**attempt)), 60.0)
                if attempt < self.max_retries:
                    time.sleep(delay)
                    continue

            if attempt < self.max_retries:
                time.sleep(min(2.0 * (2**attempt), 60.0))

        with self._counter_lock:
            self.errors += 1
            self.calls += 1
        raise last or MireyeError(0, "unknown", f"{path} failed with no response")

    def _get(self, path: str, credit_estimate: float = 0.0) -> Any:
        """GET for the two poll/meta routes. Not cached — status changes."""
        self._limiter.acquire()
        response = self._client.get(path, headers=self._headers())
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:2000]}
        if response.status_code >= 400:
            detail = _detail_of(body)
            raise MireyeError(
                response.status_code,
                detail.get("error", f"http_{response.status_code}"),
                detail.get("message", ""),
                retryable=bool(detail.get("retryable", False)),
                request_id=response.headers.get("x-request-id"),
                body=body,
            )
        self._count(credit_estimate, cached=False)
        return body

    def _credits_for(self, path: str, payload: dict, body: Any, estimate: float) -> float:
        """Work out what a call cost.

        Only /v1/proximity reports what it charged (`paid_driving_calcs`); for
        everything else we compute from the published price table. Where the
        response tells us how many fields came back, we use that rather than the
        request, because a preset's expansion is what actually gets billed.
        """
        if path == "/v1/proximity" and isinstance(body, dict):
            # VERIFIED: /v1/proximity is the one endpoint that reports what it
            # charged, as a top-level `credits_charged`. Measured 2 for a
            # straightline `nearest` and 60 for the same call in driving mode
            # (paid_driving_calcs 5 x 12). Read it rather than recomputing.
            charged = body.get("credits_charged")
            if isinstance(charged, (int, float)):
                return float(charged)
            calcs = body.get("paid_driving_calcs")
            if isinstance(calcs, (int, float)):
                op = payload.get("op", "distance")
                floor = CREDIT_COSTS.get(f"proximity_{op}_min", 2.0)
                addresses = _count_address_locators(payload)
                return max(floor, CREDIT_COSTS["proximity_per_driving_calc"] * calcs) + addresses

        if path in ("/v1/fetch", "/v1/fetch/batch") and isinstance(body, dict):
            names, locations = _billed_field_names(payload, body)
            # Parcel-group members are covered by the one RESOLVE_CREDITS charge
            # and are not also billed per field. Verified: two parcel fields and
            # nothing else billed 300, not 302.
            billable = names - PARCEL_FIELD_GROUP
            cost = CREDIT_COSTS["fetch_per_field"] * len(billable) * locations
            if names & PARCEL_FIELD_GROUP:
                cost += RESOLVE_CREDITS * locations
            # An address locator bills one geocode, but repeats inside the
            # 30-day geocode cache are free — a re-run of the same sweep should
            # not be charged for them. We count it and accept a small overstate
            # on a first run rather than understating a budget.
            if payload.get("address"):
                cost += CREDIT_COSTS["geocode"]
            cost += CREDIT_COSTS["geocode"] * sum(
                1
                for loc in (payload.get("locations") or [])
                if isinstance(loc, dict) and loc.get("address")
            )
            return cost

        return estimate

    # ------------------------------------------------------------------
    # Catalog — public, unauthenticated, used to validate field names
    # ------------------------------------------------------------------

    def catalog(self) -> dict:
        """The field and preset catalog from `GET /v1/meta/fields`.

        Public — no token required — so this works before the key arrives, and
        it is cached to disk so a sweep does not re-fetch 270 KB per worker.

        It exists here for one reason: `fields_unknown` is a hard `400` that
        kills the whole request. One renamed field would break a 3,140-county
        sweep. Validating names locally turns that into a dropped field and a
        warning.
        """
        with self._catalog_lock:
            if self._catalog is not None:
                return self._catalog

            if os.path.exists(self.catalog_path):
                try:
                    with open(self.catalog_path, "r", encoding="utf-8") as handle:
                        self._catalog = json.load(handle)
                        return self._catalog
                except (OSError, ValueError):
                    pass  # corrupt local copy; refetch below

            try:
                response = httpx.get(
                    f"{self.base_url}/v1/meta/fields", timeout=30.0
                )
                response.raise_for_status()
                self._catalog = response.json()
                os.makedirs(os.path.dirname(os.path.abspath(self.catalog_path)), exist_ok=True)
                with open(self.catalog_path, "w", encoding="utf-8") as handle:
                    json.dump(self._catalog, handle)
            except (httpx.HTTPError, OSError, ValueError):
                # No catalog means no local validation. Requests still go out;
                # a bad field name just surfaces as Mireye's own 400.
                self._catalog = {}
            return self._catalog

    def known_fields(self) -> frozenset[str]:
        """Every field name we are willing to send.

        The union of the published `fields` list and every preset expansion,
        because they are not the same set. `/v1/meta/fields` publishes 304
        fields but `presets.data_center_siting` names 106, ten of which are
        absent from that list — `btm_gas_candidacy_flag`,
        `residential_context_class_1km`, `estimated_annual_power_cost_usd_per_mw`
        and friends, all sourced `MIREYE_DERIVED_SITING` or
        `MIREYE_MODELED_ENERGY_COST`. Verified live: they return real values.
        Validating against the `fields` list alone would silently drop them.
        """
        catalog = self.catalog()
        names = {f["name"] for f in catalog.get("fields", []) if "name" in f}
        for expansion in (catalog.get("presets") or {}).values():
            names.update(expansion or ())
        return frozenset(names)

    def preset_expansion(self, preset: str) -> tuple[str, ...]:
        """The live field list behind a preset name, empty if unknown."""
        presets = self.catalog().get("presets") or {}
        return tuple(presets.get(preset) or ())

    # ------------------------------------------------------------------
    # geocode / resolve
    # ------------------------------------------------------------------

    def geocode(self, query: str, min_confidence: float = 0.8) -> Location:
        """Resolve an address or `"lat,lng"` string to a canonical location.

        Uses `/v1/lookup` rather than `/v1/geocode`, for two reasons. It returns
        a real `confidence` float and an explicit `disposition`, so genuine
        ambiguity ("1100 King St W, Toronto" — Ontario or Ohio) comes back as
        `clarify` with candidates instead of a silent pick. And it hands back
        county, county FIPS, state and tract in the same call, which is exactly
        what the pathway engine needs next.

        `include_parcel` is off: with a parcel this call bills 300 credits, and
        without it 1. Call `resolve(..., include_parcel=True)` when the parcel
        record is actually worth 300.

        Raises ResolutionError below `min_confidence` rather than returning a
        best guess. That is the product decision from `base.ResolutionError` and
        it stays.
        """
        coord = _parse_coordinate(query)
        if coord is not None:
            lat, lng = coord
            _check_envelope(lat, lng, query)
            # Nothing was resolved, so there is nothing to score. Confidence
            # stays None rather than being set to 1.0 — the caller supplied this
            # point and owns its correctness.
            return Location(
                latitude=lat,
                longitude=lng,
                formatted_address=None,
                confidence=None,
                source="caller-supplied coordinate",
                fetched=now_iso(),
                raw={"input": query},
            )
        return self.resolve(query, min_confidence=min_confidence)

    def resolve(
        self,
        query: str,
        min_confidence: float | None = None,
        include_parcel: bool = False,
    ) -> Location:
        """`/v1/lookup`, with the three dispositions handled explicitly."""
        floor = self.min_confidence if min_confidence is None else min_confidence
        payload: dict[str, Any] = {"input": query, "include_parcel": bool(include_parcel)}

        try:
            body = self._post(
                "/v1/lookup",
                payload,
                credit_estimate=RESOLVE_CREDITS if include_parcel else CREDIT_COSTS["geocode"],
            )
        except MireyeError as exc:
            # A geocode-quality failure arrives either as a 200 with
            # disposition "no_match" or as a 404 address_too_coarse /
            # address_not_found. Mireye's own CRM-cleanup skill says to treat
            # both the same way — and to treat every other status as a real
            # failure, not a non-match.
            if exc.code in ("address_too_coarse", "address_not_found", "location_unresolved"):
                raise ResolutionError(query, None, f"{exc.code}: {exc}") from exc
            if exc.code in ("address_form_unsupported", "resolve_invalid_input", "resolve_coord_bounds"):
                raise ResolutionError(query, None, f"{exc.code}: {exc}") from exc
            raise

        disposition = body.get("disposition")
        if disposition == "clarify":
            candidates = body.get("candidates") or []
            described = "; ".join(
                f"{c.get('resolved_address')} ({c.get('confidence')})" for c in candidates[:3]
            )
            raise ResolutionError(
                query, None, f"ambiguous, {len(candidates)} comparable matches: {described}"
            )
        if disposition == "no_match":
            raise ResolutionError(
                query,
                None,
                f"{body.get('reason', 'no_match')}"
                + (f" — {body['hint']}" if body.get("hint") else ""),
            )
        if disposition != "resolved":
            raise ResolutionError(query, None, f"unexpected disposition {disposition!r}")

        confidence = body.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else None
        if confidence is None:
            # No score means we cannot check the floor. Refuse rather than
            # accept an unverifiable match — same rule as being under it.
            raise ResolutionError(query, None, "lookup returned no confidence to check")
        if confidence < floor:
            raise ResolutionError(
                query,
                confidence,
                f"below the {floor:.2f} floor; matched "
                f"{body.get('resolved_address')!r} via {body.get('match_method')}",
            )

        parcel = body.get("parcel") or {}
        state_name = body.get("state")
        return Location(
            latitude=float(body["lat"]),
            longitude=float(body["lng"]),
            formatted_address=body.get("resolved_address"),
            county=body.get("county"),
            county_fips=body.get("county_fips"),
            state=_STATE_ABBREV.get((state_name or "").strip().lower(), state_name),
            tract=body.get("tract_geoid"),
            parcel_id=parcel.get("parcel_id"),
            confidence=confidence,
            source=f"Mireye /v1/lookup ({body.get('match_method')})",
            fetched=now_iso(),
            raw=body,
        )

    # ------------------------------------------------------------------
    # lookup
    # ------------------------------------------------------------------

    def lookup(self, location: Location, include_parcel: bool = False) -> FactSet:
        """Jurisdictional context for a resolved location.

        If we already have the `/v1/lookup` body on the Location (because
        `resolve()` produced it), this reads it rather than paying again.

        Per-fact `confidence` is None throughout, deliberately. `/v1/lookup`
        publishes one confidence for the resolution and none for the individual
        values; reusing the resolution score as if it described the elevation
        reading would be inventing a number. Source attribution comes from
        Mireye's documented source list — see `_LOOKUP_SOURCES`.
        """
        body = location.raw if location.raw.get("disposition") == "resolved" else None
        if body is None or (include_parcel and not body.get("parcel")):
            _check_envelope(location.latitude, location.longitude, str(location.coord))
            body = self._post(
                "/v1/lookup",
                {
                    "input": f"{location.latitude},{location.longitude}",
                    "include_parcel": bool(include_parcel),
                },
                credit_estimate=RESOLVE_CREDITS if include_parcel else CREDIT_COSTS["geocode"],
            )

        fetched = now_iso()
        facts = FactSet()

        def add(key: str, value: Any, unit: str | None = None, note: str | None = None) -> None:
            if value is None:
                return
            facts.add(
                Fact(
                    key=key,
                    value=value,
                    unit=unit,
                    source=_LOOKUP_SOURCES.get(key, "Mireye /v1/lookup"),
                    fetched=fetched,
                    confidence=None,
                    note=note,
                )
            )

        for key in (
            "county_fips",
            "county",
            "state",
            "state_fips",
            "tract_geoid",
            "block_group_geoid",
            "block_geoid",
            "congressional_district",
            "cbsa_name",
            "cbsa_code",
            "fema_flood_zone",
            "within_floodplain",
            "coastal_high_hazard",
            "in_opportunity_zone",
            "opportunity_zone_tract_geoid",
            "timezone",
        ):
            add(key, body.get(key))
        add("elevation_m", body.get("elevation_m"), unit="meters")

        market = body.get("county_market") or {}
        for key, value in market.items():
            add(f"county_market.{key}", value)
            facts.facts[f"county_market.{key}"] = Fact(
                key=f"county_market.{key}",
                value=value,
                unit=None,
                source=_LOOKUP_SOURCES["county_market"],
                fetched=fetched,
                confidence=None,
            )

        parcel = body.get("parcel") or {}
        for key, value in parcel.items():
            if key in ("geometry", "geometry_wkt"):
                continue  # large blobs; read them off Location.raw if needed
            if value is None:
                continue
            facts.add(
                Fact(
                    key=f"parcel.{key}",
                    value=value,
                    unit="m2" if key == "area_m2" else None,
                    source=parcel.get("source", "REGRID"),
                    fetched=fetched,
                    confidence=None,
                    note=f"match_type={parcel.get('match_type')}, "
                    f"match_distance_m={parcel.get('match_distance_m')}",
                )
            )

        if body.get("parcel_unavailable"):
            facts.add(
                Fact(
                    key="parcel.unavailable_reason",
                    value=body.get("parcel_unavailable_reason"),
                    source="Mireye /v1/lookup",
                    fetched=fetched,
                    confidence=None,
                    note="geocode succeeded; only the parcel leg did not",
                )
            )

        return facts

    # ------------------------------------------------------------------
    # fetch
    # ------------------------------------------------------------------

    def fetch(self, location: Location, presets: Iterable[str]) -> FactSet:
        """Fetch named intents for a location and return cited facts.

        Intent names come from `base.PRESET_INTENTS`. An intent maps either to a
        real Mireye preset or to an explicit field list (`PRESET_MAP`). An
        unrecognised intent that happens to be a real Mireye preset name is
        passed through, so a caller who knows the API can name one directly.

        Call shaping, because it is where the credits go:

        - Explicit field lists are unioned, validated against the public
          catalog, and chunked at 50 (the documented cap on explicit fields).
        - If every requested preset's expansion together fits in 50 fields, we
          send one explicit-field call instead. That dedupes overlap — `terrain`
          and `site_selection` share `elevation` and `slope_degrees` — and
          overlap is billed twice otherwise.
        - Otherwise one call per preset. Presets are exempt from the 50-field
          cap, so `data_center_siting` (106 fields) goes in one request.

        VERIFIED 5 Aug 2026: presets are exempt from the 50-field cap.
        `{"preset": "data_center_siting"}` returned `200` with all 106 fields.
        The errors page's "resolved field set (post-preset-expansion) exceeds
        50" is stale. The chunking fallback below stays anyway — it costs
        nothing until a `400 fields_too_many` actually happens.
        """
        _check_envelope(location.latitude, location.longitude, str(location.coord))
        preset_names, explicit_fields = self._split_intents(presets)

        calls: list[dict[str, Any]] = []
        union: set[str] = set(explicit_fields)
        expansions = {p: self.preset_expansion(p) for p in preset_names}
        if preset_names and all(expansions[p] for p in preset_names):
            for p in preset_names:
                union.update(expansions[p])
            if len(union) <= 50:
                calls.append({"fields": sorted(union)})
                preset_names = []
                explicit_fields = []

        for preset in preset_names:
            calls.append({"preset": preset})
        if explicit_fields:
            valid = self._validate_fields(explicit_fields)
            for chunk in _chunks(valid, 50):
                calls.append({"fields": chunk})

        facts = FactSet()
        for call in calls:
            payload = {"lat": location.latitude, "lng": location.longitude, **call}
            try:
                body = self._post("/v1/fetch", payload, credit_estimate=0.0)
            except MireyeError as exc:
                if exc.code == "fields_too_many" and "preset" in call:
                    # The docs disagree with themselves about whether presets are
                    # exempt. If they are not, expand locally and chunk. Same
                    # credits, one extra round trip.
                    expansion = self._validate_fields(self.preset_expansion(call["preset"]))
                    if not expansion:
                        raise
                    for chunk in _chunks(expansion, 50):
                        chunk_body = self._post(
                            "/v1/fetch",
                            {"lat": location.latitude, "lng": location.longitude, "fields": chunk},
                        )
                        facts = facts.merge(self._facts_from_fetch(chunk_body))
                    continue
                raise
            facts = facts.merge(self._facts_from_fetch(body))
        return facts

    def fetch_batch(
        self, locations: list[Location], presets: Iterable[str]
    ) -> list[FactSet | None]:
        """The same field selection over up to 25 locations, index-aligned.

        The national sweep is 3,140 counties. One at a time that is 3,140 round
        trips against a 60 rpm limit — nearly an hour of pure waiting. Batched
        it is 126 requests for the same credits. An entry that fails comes back
        as None; a failure at one location never costs the other 24.
        """
        if len(locations) > 25:
            raise ValueError("/v1/fetch/batch takes at most 25 locations per request")
        preset_names, explicit_fields = self._split_intents(presets)
        if len(preset_names) > 1:
            raise ValueError(
                "batch takes one field selection for every location; call it once per preset"
            )

        selection: dict[str, Any] = {}
        if preset_names:
            selection["preset"] = preset_names[0]
        if explicit_fields:
            selection["fields"] = self._validate_fields(explicit_fields)[:50]

        payload = {
            "locations": [{"lat": loc.latitude, "lng": loc.longitude} for loc in locations],
            **selection,
        }
        body = self._post("/v1/fetch/batch", payload)

        out: list[FactSet | None] = [None] * len(locations)
        for entry in body.get("results") or []:
            index = entry.get("index")
            if not isinstance(index, int) or not (0 <= index < len(out)):
                continue
            out[index] = self._facts_from_fetch(entry) if entry.get("ok") else None
        return out

    def _split_intents(self, presets: Iterable[str]) -> tuple[list[str], list[str]]:
        """Translate intent names into Mireye preset names and field names."""
        preset_names: list[str] = []
        fields: list[str] = []
        for intent in presets:
            mapped = PRESET_MAP.get(intent)
            if mapped is None:
                if intent in MIREYE_PRESETS:
                    mapped = intent  # caller named a real preset directly
                elif intent in self.known_fields():
                    mapped = (intent,)  # caller named a real field directly
                else:
                    raise ValueError(
                        f"unknown intent {intent!r}; expected one of "
                        f"{sorted(PRESET_MAP)} or a Mireye preset/field name"
                    )
            if isinstance(mapped, str):
                if mapped not in preset_names:
                    preset_names.append(mapped)
            else:
                fields.extend(mapped)
        return preset_names, list(dict.fromkeys(fields))

    def _validate_fields(self, names: Iterable[str]) -> list[str]:
        """Drop field names the catalog does not know about.

        `fields_unknown` is a hard 400 that kills the whole request, so one
        renamed field would break a sweep. Dropping it costs one value; sending
        it costs every value in the call.
        """
        known = self.known_fields()
        if not known:
            return list(dict.fromkeys(names))
        kept, dropped = [], []
        for name in dict.fromkeys(names):
            (kept if name in known else dropped).append(name)
        if dropped:
            print(f"[mireye] dropping {len(dropped)} field(s) not in the catalog: {dropped}")
        return kept

    def _facts_from_fetch(self, body: dict) -> FactSet:
        """Turn a `/v1/fetch` body into cited facts.

        Expected shape, per Mireye's docs:

            {"lat": .., "lng": .., "fetched_at": "...",
             "fields": {"<name>": {"value": .., "unit": .., "source": "USGS_EPQS",
                                   "source_url": "...", "confidence": "high",
                                   "fetched_at": "...", "dataset_vintage": ..,
                                   "ttl_seconds": .., "notes": .., "status": "ok"}},
             "partial_failures": [...],
             "geocode": {...},                     # address requests only
             "resolved_location": {"lat": .., "lng": .., "source": "coordinate"}}

        Every requested field appears with a tri-state `status`: `ok` (a real
        value), `absent` (valid no-data), `failed` (`value: null` plus `error`
        and `retryable`). We keep all three as Facts, with the status in the
        note — mirroring Mireye's own rule that a field we could not fetch is
        never silently dropped. Downstream code should read `Fact.value is None`
        and the note rather than assuming presence means success.
        """
        facts = FactSet()
        fields = body.get("fields")
        if not isinstance(fields, dict):
            return facts

        response_fetched = body.get("fetched_at")
        for name, record in fields.items():
            if not isinstance(record, dict):
                # Defensive: a bare value would mean the shape changed.
                facts.add(Fact(key=name, value=record, source="Mireye /v1/fetch"))
                continue

            status = record.get("status", "ok")
            bucket = record.get("confidence")
            notes = []
            if isinstance(bucket, str):
                notes.append(f"confidence={bucket}")
            if status and status != "ok":
                notes.append(f"status={status}")
            if record.get("error"):
                notes.append(f"error={record['error']} retryable={record.get('retryable')}")
            if record.get("dataset_vintage"):
                notes.append(f"vintage={record['dataset_vintage']}")
            if record.get("notes"):
                notes.append(str(record["notes"]))
            if record.get("source_url"):
                notes.append(record["source_url"])

            facts.add(
                Fact(
                    key=name,
                    value=record.get("value"),
                    unit=record.get("unit"),
                    source=record.get("source"),
                    fetched=record.get("fetched_at") or response_fetched,
                    confidence=_bucket_to_confidence(bucket),
                    note="; ".join(notes) or None,
                )
            )

        geocode = body.get("geocode")
        if isinstance(geocode, dict) and geocode.get("parcel_grade") is False:
            # Their own /v1/ask appends this caveat to the prose for the same
            # reason: a street-interpolated coordinate can describe a
            # neighbouring property, and the warning has to travel with the data.
            facts.add(
                Fact(
                    key="geocode.parcel_grade",
                    value=False,
                    source="Mireye /v1/geocode",
                    fetched=response_fetched,
                    confidence=_number_or_none(geocode.get("accuracy")),
                    note=(
                        f"accuracy_type={geocode.get('accuracy_type')}; matched "
                        f"{geocode.get('normalized_address')!r}. Not parcel grade — up to "
                        f"~2,872 m out in rural areas. Do not trust parcel-specific fields."
                    ),
                )
            )
        return facts

    # ------------------------------------------------------------------
    # proximity
    # ------------------------------------------------------------------

    def proximity(
        self,
        location: Location,
        targets: Iterable[str],
        mode: str | None = None,
    ) -> dict[str, ProximityResult]:
        """Distance from a location to the nearest thing of each named class.

        Target names come from `base.PROXIMITY_TARGETS`. Each is routed to
        whichever Mireye surface actually answers it (`_PROXIMITY_ROUTES`):

        - `/v1/proximity` `op: "nearest"` for the six curated sets — airports,
          substations, power plants, rail, ports, urban areas. This is the only
          way to get a by-road answer.
        - `/v1/fetch` catalog fields for everything else. Transmission lines,
          gas pipelines, schools and hospitals have no curated set; they are
          geodesic distance fields. All the fetch-backed targets go out in one
          call, so a five-target screen is one request and about eight credits.

        `mode` defaults to the instance setting, which is `"straightline"`.
        Driving mode is 60 credits per target (12 credits × `min(25, n×5)`
        driving calcs) against 2 for geodesic — real money at sweep scale. Set
        `mode="driving"` per call for the site screens where by-road matters.

        `ProximityResult.by_road` says which one you got. A target with nothing
        within Mireye's fixed 160 km search radius is omitted from the result
        rather than reported as a distance of zero.
        """
        mode = mode or self.proximity_mode
        _check_envelope(location.latitude, location.longitude, str(location.coord))

        wanted = list(dict.fromkeys(targets))
        unknown = [t for t in wanted if t not in _PROXIMITY_ROUTES]
        if unknown:
            raise ValueError(
                f"unknown proximity target(s) {unknown}; expected {sorted(_PROXIMITY_ROUTES)}"
            )

        via_set = [t for t in wanted if mode == "driving" and _PROXIMITY_ROUTES[t]["set"]]
        via_fetch = [t for t in wanted if t not in via_set and _PROXIMITY_ROUTES[t].get("distance_field")]
        # Straight-line targets with no fetch field left over still have a
        # curated set; use it in straightline mode (2 credits).
        via_set += [t for t in wanted if t not in via_set and t not in via_fetch]

        results: dict[str, ProximityResult] = {}
        fell_back: list[str] = []
        for target in via_set:
            try:
                found = self._proximity_via_nearest(location, target, mode)
            except MireyeError as exc:
                # A curated set can be down: on 5 Aug 2026 `@airports` returned
                # `503 proximity_data_unavailable` — "asset is missing column(s)
                # ['use'] that its default filter requires". Refusing rather
                # than returning wrong answers is the right call on their side,
                # but it must not take a site screen with it. Fall back to the
                # geodesic fetch field where the target has one.
                if exc.code != "proximity_data_unavailable" or not _PROXIMITY_ROUTES[target].get(
                    "distance_field"
                ):
                    raise
                print(f"[mireye] {target}: curated set unavailable ({exc.code}); using fetch field")
                fell_back.append(target)
                continue
            if found is not None:
                results[target] = found

        remaining = [t for t in via_fetch + fell_back if t not in results]
        if remaining:
            results.update(self._proximity_via_fetch(location, remaining))
        return results

    def _proximity_via_fetch(
        self, location: Location, targets: list[str]
    ) -> dict[str, ProximityResult]:
        """One /v1/fetch call covering every fetch-backed target."""
        names: list[str] = []
        for target in targets:
            route = _PROXIMITY_ROUTES[target]
            names.append(route["distance_field"])
            if route.get("name_field"):
                names.append(route["name_field"])
            names.extend(route.get("attribute_fields") or ())

        facts = FactSet()
        valid = self._validate_fields(names)
        for chunk in _chunks(valid, 50):
            body = self._post(
                "/v1/fetch",
                {"lat": location.latitude, "lng": location.longitude, "fields": chunk},
            )
            facts = facts.merge(self._facts_from_fetch(body))

        results: dict[str, ProximityResult] = {}
        for target in targets:
            route = _PROXIMITY_ROUTES[target]
            distance_fact = facts.fact(route["distance_field"])
            if distance_fact is None or distance_fact.value is None:
                continue
            attributes = {
                key: facts.get(key)
                for key in route.get("attribute_fields") or ()
                if facts.get(key) is not None
            }
            notes = [route["note"]] if route.get("note") else []
            if distance_fact.note:
                notes.append(distance_fact.note)
            results[target] = ProximityResult(
                target=target,
                distance_km=float(distance_fact.value) / 1000.0,
                name=facts.get(route["name_field"]) if route.get("name_field") else None,
                by_road=False,
                attributes={**attributes, "field": route["distance_field"], "notes": notes},
                source=distance_fact.source,
                fetched=distance_fact.fetched,
            )
        return results

    def _proximity_via_nearest(
        self, location: Location, target: str, mode: str
    ) -> ProximityResult | None:
        """One /v1/proximity `nearest` call against a curated set.

        Expected shape:

            {"op": "nearest",
             "origin": {"query": "..", "lat": .., "lng": .., "error": null},
             "candidates": [{"name": "JOHN F KENNEDY INTL", "lat": .., "lng": ..,
                             "attributes": {...}, "distance_miles": 13.8,
                             "distance_km": 22.2, "duration_seconds": 1650,
                             "duration_minutes": 27.5}],
             "applied_filters": null, "paid_driving_calcs": 15, "notes": [...]}
        """
        route = _PROXIMITY_ROUTES[target]
        payload = {
            "op": "nearest",
            # Always a coordinate string: a coordinate skips Mireye's accuracy
            # gate, costs no geocoding credit, and cannot resolve to a town
            # named after a street.
            "origin": f"{location.latitude},{location.longitude}",
            "set": route["set"],
            "n": 1,
            "mode": mode,
        }
        body = self._post("/v1/proximity", payload, credit_estimate=CREDIT_COSTS["proximity_nearest_min"])

        candidates = body.get("candidates") or []
        if not candidates:
            # Documented: nothing within the fixed 160 km radius comes back as
            # an empty list, not an error. Report absence by omission.
            return None

        best = candidates[0]
        distance_km = best.get("distance_km")
        if distance_km is None and best.get("distance_miles") is not None:
            # VERIFIED: straightline mode does return distance_km (measured
            # 0.5045 km to the BEAUMEADE substation) and nulls only the
            # durations. This stays as a belt-and-braces fallback.
            distance_km = float(best["distance_miles"]) * 1.609344
        if distance_km is None:
            return None

        attributes = dict(best.get("attributes") or {})
        attributes.update(
            {
                "duration_minutes": best.get("duration_minutes"),
                "flag": best.get("flag"),
                "paid_driving_calcs": body.get("paid_driving_calcs"),
                "notes": body.get("notes"),
                "set": route["set"],
            }
        )
        if best.get("flag") == "unreachable_or_snapped":
            # The snap guard fired: the routing provider snapped an unreachable
            # point to a road. The distance is not drivable and the duration is
            # already null. Say so rather than presenting it as a drive.
            attributes["unreachable"] = True

        return ProximityResult(
            target=target,
            distance_km=float(distance_km),
            name=best.get("name"),
            by_road=(mode == "driving" and best.get("flag") != "unreachable_or_snapped"),
            attributes=attributes,
            source=f"Mireye /v1/proximity nearest {route['set']}",
            fetched=now_iso(),
        )

    # ------------------------------------------------------------------
    # ask
    # ------------------------------------------------------------------

    def ask(self, location: Location, question: str, include_trace: bool = True) -> FactSet:
        """Open-ended question at a coordinate, with the plan it ran.

        `include_trace` returns `planner_reasoning`, `fields_requested` and
        `preset_expanded`, which is the replayable plan the build brief wanted —
        and the most interesting thing to put on camera.

        Two limits worth knowing. The planner is capped at 15 fields per
        question and truncates larger preset expansions to their first 15, so
        this is not a shortcut to a full site screen; use `fetch()` for anything
        the pathway engine depends on. And the endpoint is hard-bounded at 110 s
        server-side, which is why the client timeout floor is 120 s.

        Costs 10 credits regardless of how many fields the planner picks.
        """
        _check_envelope(location.latitude, location.longitude, str(location.coord))
        body = self._post(
            "/v1/ask",
            {
                "lat": location.latitude,
                "lng": location.longitude,
                "question": question,
                "include_trace": bool(include_trace),
            },
            credit_estimate=CREDIT_COSTS["ask"],
        )

        fetched = body.get("answered_at") or now_iso()
        citations = body.get("citations") or []
        sources = ", ".join(sorted({c.get("source", "?") for c in citations})) or "none cited"

        facts = FactSet()
        facts.add(
            Fact(
                key="ask.answer",
                value=body.get("answer"),
                source=f"Mireye /v1/ask over {sources}",
                fetched=fetched,
                # The answer's own bucket, auto-downgraded server-side when more
                # than 30% of planner-selected fields came back null.
                confidence=_bucket_to_confidence(body.get("confidence")),
                note=f"question: {question}",
            )
        )
        facts.add(
            Fact(
                key="ask.citations",
                value=citations,
                source="Mireye /v1/ask",
                fetched=fetched,
                confidence=None,
                note=f"{len(citations)} source(s); fields_used={body.get('fields_used')}",
            )
        )
        if body.get("data_gaps"):
            facts.add(
                Fact(
                    key="ask.data_gaps",
                    value=body["data_gaps"],
                    source="Mireye /v1/ask",
                    fetched=fetched,
                    confidence=None,
                    note="requested fields that resolved to no value, with the layer's reason",
                )
            )
        trace = body.get("trace")
        if trace:
            facts.add(
                Fact(
                    key="ask.plan",
                    value={
                        "fields_requested": trace.get("fields_requested"),
                        "preset_expanded": trace.get("preset_expanded"),
                        "planner_model": trace.get("planner_model"),
                        "synthesizer_model": trace.get("synthesizer_model"),
                    },
                    source="Mireye /v1/ask trace",
                    fetched=fetched,
                    confidence=None,
                    note=(trace.get("planner_reasoning") or "")[:600] or None,
                )
            )
        return facts

    # ------------------------------------------------------------------
    # field requests
    # ------------------------------------------------------------------

    def field_request(
        self,
        field_name: str,
        description: str,
        example_locations: list[dict] | None = None,
        use_case: str | None = None,
        decision_threshold: str | None = None,
        area_of_interest: dict | None = None,
        expected_volume: dict | None = None,
        freshness: dict | None = None,
        constraints: dict | None = None,
        known_sources: dict | None = None,
        output_preference: dict | None = None,
        idempotency_key: str | None = None,
        context_blob: str | None = None,
    ) -> dict:
        """Ask Mireye to add a field they do not have yet.

        Three outcomes, all useful: the field already exists and we get a live
        cited sample at our own location; it is a near miss and we decide
        whether the difference matters; or it is a genuine gap and a build is
        queued with a `request_id` to poll.

        Everything optional here is a question the build would otherwise stop
        and ask a human mid-run. Filling in `use_case`, `decision_threshold` and
        `known_sources` is what makes the result match what we actually needed.
        `idempotency_key` is generated from the ask if not supplied — the same
        key with the same ask replays, and with a different ask is a `409`.

        Note what is deliberately not exposed: the `callback` object. Mireye
        supports webhook and email notification and this build does not send
        anything to anyone. Poll `field_request_status()` instead. See the
        guardrails section of the build brief.
        """
        locations = example_locations or []
        if not locations:
            raise ValueError(
                "field_request needs at least one example location — it is what seeds "
                "the build's eval cases and where the field is verified on prod"
            )
        if len(locations) > 10:
            raise ValueError("/v1/field-requests takes at most 10 example locations")

        payload: dict[str, Any] = {
            "description": description[:8000],
            "example_locations": locations,
            "idempotency_key": (
                idempotency_key or f"deliverable-{_stable_key(field_name, description)}"
            )[:255],
        }
        for key, value in (
            ("use_case", use_case),
            ("decision_threshold", decision_threshold),
            ("area_of_interest", area_of_interest),
            ("expected_volume", expected_volume),
            ("freshness", freshness),
            ("constraints", constraints),
            ("known_sources", known_sources),
            ("output_preference", output_preference),
            ("context_blob", context_blob),
        ):
            if value:
                payload[key] = value

        # Not cached: filing is stateful, and a replay of the same idempotency
        # key is Mireye's own job, not ours.
        self._limiter.acquire()
        response = self._client.post(
            "/v1/field-requests", json=payload, headers=self._headers()
        )
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:2000]}
        if response.status_code >= 400:
            detail = _detail_of(body)
            raise MireyeError(
                response.status_code,
                detail.get("error", f"http_{response.status_code}"),
                detail.get("message", ""),
                retryable=bool(detail.get("retryable", False)),
                request_id=response.headers.get("x-request-id"),
                body=body,
            )
        with self._counter_lock:
            self.calls += 1  # billed against the plan's field-request allowance, not credits
        return _normalise_field_request(body, requested=field_name, http_status=response.status_code)

    def field_request_status(self, request_id: str) -> dict:
        """Poll a filed request. Terminal states: live, blocked, expired, rejected.

        Your session will be dead by the time a build goes live — store the
        `request_id` in durable state and poll it from the next run. `live`
        means prod `/v1/fetch` returned a real cited non-null value at our own
        example locations, not that a PR merged.
        """
        body = self._get(f"/v1/field-requests/{request_id}")
        return _normalise_field_request(body, requested=None, http_status=200)

    # ------------------------------------------------------------------
    # accounting
    # ------------------------------------------------------------------

    def usage(self) -> dict:
        """Calls made and credits spent this run, plus the cache's own numbers.

        `credits` is computed from the published price table, not read back —
        no data endpoint except /v1/proximity reports what it charged. Check it
        against `GET /v1/users/me/usage` after a real run.
        """
        with self._counter_lock:
            calls, credits, hits, errors = self.calls, self.credits, self.cache_hits, self.errors
        total = calls + hits
        return {
            "calls": calls,
            "cache_hits": hits,
            "cache_hit_rate": (hits / total) if total else 0.0,
            "errors": errors,
            "credits_spent": credits,
            "credits_usd": credits / 1000.0,  # $1.00 per 1,000 credits, every tier
            "cache": self.cache.stats(),
        }

    def usage_summary(self) -> str:
        u = self.usage()
        return (
            f"{u['calls']:,} calls, {u['cache_hits']:,} cache hits "
            f"({u['cache_hit_rate']:.0%}), {u['errors']:,} errors, "
            f"{u['credits_spent']:,.0f} credits (~${u['credits_usd']:,.2f})"
        )


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _stable_key(*parts: str) -> str:
    import hashlib

    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:32]


def _parse_coordinate(query: str) -> tuple[float, float] | None:
    """Recognise a `"lat,lng"` string. Returns None for anything else."""
    if "," not in query:
        return None
    left, _, right = query.partition(",")
    try:
        lat, lng = float(left.strip()), float(right.strip())
    except ValueError:
        return None
    return lat, lng


def _check_envelope(lat: float, lng: float, query: str) -> None:
    """Catch an out-of-US coordinate before spending a call on a 400.

    Also catches the transposed lat/lng, which Mireye treats as a hard error for
    the same reason we do: silently swapping them risks landing on a
    plausible-looking but wrong point.
    """
    if not (US_ENVELOPE["lat_min"] <= lat <= US_ENVELOPE["lat_max"]) or not (
        US_ENVELOPE["lng_min"] <= lng <= US_ENVELOPE["lng_max"]
    ):
        hint = ""
        if US_ENVELOPE["lat_min"] <= lng <= US_ENVELOPE["lat_max"]:
            hint = " (lat/lng look swapped)"
        raise ResolutionError(
            query,
            None,
            f"({lat}, {lng}) is outside Mireye's US envelope "
            f"lat[{US_ENVELOPE['lat_min']}, {US_ENVELOPE['lat_max']}] "
            f"lng[{US_ENVELOPE['lng_min']}, {US_ENVELOPE['lng_max']}]{hint}",
        )


def _count_address_locators(payload: dict) -> int:
    """Address-form locators on /v1/proximity cost 1 credit each, additively."""
    count = 0
    for key in ("origin", "origins", "destinations", "anchors"):
        value = payload.get(key)
        items = value if isinstance(value, list) else ([value] if value else [])
        for item in items:
            if isinstance(item, str) and _parse_coordinate(item) is None:
                count += 1
    return count


def _billed_field_names(payload: dict, body: dict) -> tuple[frozenset[str], int]:
    """What a fetch call actually billed for: field names and location count.

    Reads the response where possible — a preset's real expansion is what gets
    billed, and the request only names the preset.
    """
    if "results" in body:
        names: set[str] = set()
        locations = 0
        for entry in body.get("results") or []:
            if entry.get("ok") and isinstance(entry.get("fields"), dict):
                names.update(entry["fields"].keys())
                locations += 1
        return frozenset(names), max(locations, 1)
    fields = body.get("fields")
    if isinstance(fields, dict) and fields:
        return frozenset(fields.keys()), 1
    return frozenset(payload.get("fields") or ()), 1


def _normalise_field_request(body: dict, requested: str | None, http_status: int) -> dict:
    """Flatten a /v1/field-requests response into one shape the agent can branch on.

    Mireye decomposes a bundled ask into sub-asks and returns one disposition
    per sub-ask, rolled up into a request-level `status`. We pick the most
    actionable sub-ask and report a single `outcome`:

        exists     — matched_existing / partial: the field is live now, with a
                     cited sample at our own first example location
        near_miss  — near_miss_confirm: close, waiting on us to accept or reject
        clarify    — ambiguous ask or ambiguous location; candidates returned
        queued     — accepted_new: a build exists, poll request_id
        rejected   — a typed no with a routing hint
        screening  — the 202 path; screening did not finish inside its budget
    """
    dispositions = body.get("disposition") or []
    if isinstance(dispositions, dict):
        dispositions = [dispositions]

    rank = {
        "accepted_new": 0,
        "near_miss_confirm": 1,
        "clarify": 2,
        "matched_existing": 3,
        "partial": 3,
        "rejected": 4,
    }
    chosen: dict = {}
    if dispositions:
        chosen = sorted(dispositions, key=lambda d: rank.get(d.get("disposition"), 9))[0]

    kind = chosen.get("disposition")
    outcome = {
        "matched_existing": "exists",
        "partial": "exists",
        "near_miss_confirm": "near_miss",
        "clarify": "clarify",
        "accepted_new": "queued",
        "rejected": "rejected",
    }.get(kind or "")

    status = body.get("status")
    if outcome is None:
        # No per-sub-ask disposition: an ambiguous-location clarify (stateless,
        # no request created) or the 202 async-screening path.
        if status == "clarify" or body.get("clarify"):
            outcome = "clarify"
        elif status in ("received", "screening"):
            outcome = "screening"
        elif status in ("live", "matched"):
            outcome = "exists"
        elif status in ("queued", "claimed", "building", "in_review", "approved", "publishing"):
            outcome = "queued"
        elif status in ("rejected", "blocked", "expired"):
            outcome = "rejected"
        else:
            outcome = "screening"

    return {
        "outcome": outcome,
        "requested": requested,
        "http_status": http_status,
        "request_id": body.get("request_id"),
        "status": status,
        "waiting_on": body.get("waiting_on"),
        "field_id": chosen.get("field_id"),
        "ask": chosen.get("ask"),
        "reason": chosen.get("reason"),
        "description": chosen.get("description"),
        "units": chosen.get("units"),
        "sample": chosen.get("sample"),
        "sample_omitted_reason": chosen.get("sample_omitted_reason"),
        "resume": chosen.get("resume") or body.get("resume"),
        "confirm_required": chosen.get("confirm_required", False),
        "candidates": chosen.get("candidates") or (body.get("clarify") or {}).get("locations"),
        "rejection_code": chosen.get("rejection_code"),
        "routing_hint": chosen.get("routing_hint"),
        "queue_position": body.get("queue_position"),
        "estimated_ready_at": body.get("estimated_ready_at") or chosen.get("estimated_ready_at"),
        "resolved_locations": body.get("resolved_locations"),
        "dispositions": dispositions,
        "raw": body,
    }


# ----------------------------------------------------------------------
# Self test
# ----------------------------------------------------------------------


def main() -> None:
    """Resolve one address and print cited facts. `python -m providers.mireye`.

    Degrades to a clear message with no key set: it prints what it would do and
    exits 0, so a clean checkout can run this without a network or a token.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Mireye provider self test.")
    parser.add_argument(
        "--address",
        default="1600 Smith St, Houston, TX 77002",
        help="address or 'lat,lng' to resolve",
    )
    parser.add_argument(
        "--intents",
        default="terrain,utilities",
        help="comma-separated PRESET_INTENTS names",
    )
    parser.add_argument(
        "--targets",
        default="transmission,gas_pipeline,school",
        help="comma-separated PROXIMITY_TARGETS names",
    )
    parser.add_argument("--mode", default="straightline", choices=["straightline", "driving"])
    parser.add_argument("--ask", default=None, help="optional /v1/ask question (10 credits)")
    args = parser.parse_args()

    key = os.environ.get("MIREYE_API_KEY") or os.environ.get("MIREYE_API_TOKEN")
    if not key:
        print(
            "MIREYE_API_KEY is not set, so this is a dry run.\n"
            "\n"
            "Get a token at https://www.mireye.com/account (sign up with code BUILD),\n"
            "then put it in .env as MIREYE_API_KEY and run this again.\n"
            "\n"
            f"It would resolve {args.address!r} via POST /v1/lookup (include_parcel=false,\n"
            f"1 credit), refuse anything under confidence {0.8:.2f}, then fetch intents\n"
            f"{args.intents} and measure proximity to {args.targets} in {args.mode} mode.\n"
        )
        provider = MireyeProvider(api_key="")
        for intent in args.intents.split(","):
            mapped = PRESET_MAP.get(intent.strip())
            shape = f"preset={mapped!r}" if isinstance(mapped, str) else f"{len(mapped or ())} fields"
            print(f"  intent {intent.strip():20s} -> {shape}")
        for target in args.targets.split(","):
            route = _PROXIMITY_ROUTES.get(target.strip(), {})
            via = route.get("set") or route.get("distance_field") or "unknown"
            print(f"  target {target.strip():20s} -> {via}")
        print(f"\n{provider.cache.summary()}")
        return

    with MireyeProvider(proximity_mode=args.mode) as provider:
        try:
            location = provider.geocode(args.address)
        except ResolutionError as exc:
            print(f"REFUSED: {exc}")
            print("That is the intended behaviour — a wrong parcel is worse than a retry.")
            return

        print(f"\n{location.formatted_address or args.address}")
        print(
            f"  {location.latitude:.6f}, {location.longitude:.6f} — "
            f"{location.county}, {location.state} "
            f"(FIPS {location.county_fips}, tract {location.tract})"
        )
        print(f"  confidence {location.confidence:.2f} via {location.source}\n")

        facts = provider.lookup(location)
        facts = facts.merge(provider.fetch(location, args.intents.split(",")))

        print(f"{len(facts)} cited facts:")
        for line in facts.cited_lines():
            print(f"  {line}")

        print("\nproximity:")
        for target, result in provider.proximity(location, args.targets.split(",")).items():
            road = "by road" if result.by_road else "straight line"
            named = f" — {result.name}" if result.name else ""
            print(
                f"  {target:16s} {result.distance_km:8.2f} km ({road}){named} "
                f"[source: {result.source}]"
            )

        if args.ask:
            answer = provider.ask(location, args.ask)
            print(f"\nask: {args.ask}")
            for line in answer.cited_lines():
                print(f"  {line[:400]}")

        print(f"\n{provider.usage_summary()}")
        print(provider.cache.summary())


if __name__ == "__main__":
    main()
