"""Potential-to-emit estimator.

Pure math. No network, no external data. Given a generation config
(MW, prime mover, fuel, controls, annual run hours) this returns tons per year
of each regulated NSR pollutant, which is the number the whole permit pathway
turns on.

Emission factors are AP-42 (EPA's compilation of air pollutant emission factors).
Every factor below carries its table reference in `EmissionFactorSet.citation`
so the output can show its work the same way Mireye's does.

Two things people get wrong and this module gets right:

1.  Potential to emit is the *maximum* the source could emit at its physical
    design capacity, 8760 hours a year, unless there is a
    **federally enforceable** limit in the permit. Running the plant less does
    not lower your PTE. Accepting a permit condition that caps your run hours
    does. That is the entire synthetic-minor mechanism, so `run_hours` here is
    only allowed below 8760 when `enforceable_limit=True`.

2.  Emissions scale with **heat input** (MMBtu/hr), not with megawatts. A
    combined-cycle plant burns roughly two thirds the fuel of a simple-cycle
    plant for the same MW, so it emits proportionally less per MW even before
    controls. Heat rate is the bridge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

# --------------------------------------------------------------------------
# Pollutants
# --------------------------------------------------------------------------

#: The regulated NSR pollutants that decide a permit pathway. HAPs (formaldehyde
#: here) do not trigger PSD but do trigger Title V and NESHAP, so we track it.
POLLUTANTS = ("NOx", "CO", "PM10", "PM2.5", "SO2", "VOC", "CO2e", "HCHO")

#: PSD "significant emission rate" thresholds, tons per year.
#: 40 CFR 52.21(b)(23)(i). At a major source, any pollutant emitted above its
#: SER needs BACT. Below it, the pollutant rides along without review.
SIGNIFICANT_EMISSION_RATES = {
    "NOx": 40.0,
    "SO2": 40.0,
    "CO": 100.0,
    "PM10": 15.0,
    "PM2.5": 10.0,
    "VOC": 40.0,
    "CO2e": 75_000.0,  # GHG, only relevant if the source is major for another pollutant
}


class Fuel(str, Enum):
    NATURAL_GAS = "natural_gas"
    DIESEL = "diesel"  # ultra-low sulfur, 15 ppm


class PrimeMover(str, Enum):
    """What actually burns the fuel. This drives both the emission factors and,
    critically, whether the source lands in a List-of-28 category."""

    SIMPLE_CYCLE_TURBINE = "simple_cycle_turbine"
    COMBINED_CYCLE_TURBINE = "combined_cycle_turbine"
    RECIP_LEAN_BURN = "recip_lean_burn"  # 4-stroke lean burn gas engine
    RECIP_RICH_BURN = "recip_rich_burn"  # 4-stroke rich burn gas engine
    DIESEL_RECIP = "diesel_recip"  # large stationary compression ignition
    FUEL_CELL = "fuel_cell"  # Bloom-style, near-zero criteria pollutants


class Control(str, Enum):
    NONE = "none"
    DLN = "dry_low_nox"  # dry low-NOx combustors, turbines only
    WATER_INJECTION = "water_injection"  # turbines only
    SCR = "scr"  # selective catalytic reduction
    OXIDATION_CATALYST = "oxidation_catalyst"
    TIER4 = "tier4_final"  # EPA Tier 4 final certified engine, diesel only


@dataclass(frozen=True)
class EmissionFactorSet:
    """lb of pollutant per MMBtu of heat input, plus where the number came from."""

    factors: dict[str, float]
    citation: str


# --------------------------------------------------------------------------
# Uncontrolled emission factors, lb/MMBtu of heat input (HHV)
# --------------------------------------------------------------------------

_EF: dict[tuple[PrimeMover, Fuel], EmissionFactorSet] = {
    (PrimeMover.SIMPLE_CYCLE_TURBINE, Fuel.NATURAL_GAS): EmissionFactorSet(
        {
            "NOx": 0.32,
            "CO": 0.082,
            "PM10": 0.0066,
            "PM2.5": 0.0066,  # essentially all turbine PM is < 2.5 micron
            "SO2": 0.0034,
            "VOC": 0.0021,
            "CO2e": 110.0,
            "HCHO": 0.00071,
        },
        "AP-42 Table 3.1-1 / 3.1-2a / 3.1-3, uncontrolled natural gas turbine > 3 MW",
    ),
    (PrimeMover.COMBINED_CYCLE_TURBINE, Fuel.NATURAL_GAS): EmissionFactorSet(
        {
            "NOx": 0.32,
            "CO": 0.082,
            "PM10": 0.0066,
            "PM2.5": 0.0066,
            "SO2": 0.0034,
            "VOC": 0.0021,
            "CO2e": 110.0,
            "HCHO": 0.00071,
        },
        "AP-42 Table 3.1-1 (same combustor factors; the CC advantage shows up in heat rate, "
        "and duct firing is modelled separately)",
    ),
    (PrimeMover.SIMPLE_CYCLE_TURBINE, Fuel.DIESEL): EmissionFactorSet(
        {
            "NOx": 0.88,
            "CO": 0.085,
            "PM10": 0.012,
            "PM2.5": 0.012,
            "SO2": 0.0011,  # 15 ppm ULSD
            "VOC": 0.0041,
            "CO2e": 161.0,
            "HCHO": 0.00028,
        },
        "AP-42 Table 3.1-1/3.1-4, distillate oil fired turbine, ULSD sulfur basis",
    ),
    (PrimeMover.RECIP_LEAN_BURN, Fuel.NATURAL_GAS): EmissionFactorSet(
        {
            "NOx": 0.847,
            "CO": 0.557,
            "PM10": 0.0000771 * 10,  # AP-42 3.2-2 filterable + condensable
            "PM2.5": 0.0000771 * 10,
            "SO2": 0.000588,
            "VOC": 0.118,
            "CO2e": 110.0,
            "HCHO": 0.0528,
        },
        "AP-42 Table 3.2-1/3.2-2, 4-stroke lean burn natural gas engine, uncontrolled",
    ),
    (PrimeMover.RECIP_RICH_BURN, Fuel.NATURAL_GAS): EmissionFactorSet(
        {
            "NOx": 2.21,
            "CO": 3.72,
            "PM10": 0.0095,
            "PM2.5": 0.0095,
            "SO2": 0.000588,
            "VOC": 0.0296,
            "CO2e": 110.0,
            "HCHO": 0.0021,
        },
        "AP-42 Table 3.2-1/3.2-3, 4-stroke rich burn natural gas engine, uncontrolled",
    ),
    (PrimeMover.DIESEL_RECIP, Fuel.DIESEL): EmissionFactorSet(
        {
            # AP-42 3.4 gives lb/hp-hr against a 7000 Btu/hp-hr basis; converted here.
            "NOx": 0.024 / 0.007,  # 3.43
            "CO": 0.0055 / 0.007,  # 0.786
            "PM10": 0.0007 / 0.007,  # 0.10
            "PM2.5": 0.0007 / 0.007,
            "SO2": 0.0011,  # ULSD
            "VOC": 0.0007 / 0.007,  # 0.10
            "CO2e": 161.0,
            "HCHO": 0.000118,
        },
        "AP-42 Table 3.4-1, large uncontrolled stationary diesel > 600 hp, "
        "converted from lb/hp-hr at 7,000 Btu/hp-hr",
    ),
    (PrimeMover.FUEL_CELL, Fuel.NATURAL_GAS): EmissionFactorSet(
        {
            "NOx": 0.00025,
            "CO": 0.0007,
            "PM10": 0.00002,
            "PM2.5": 0.00002,
            "SO2": 0.0000,
            "VOC": 0.00002,
            "CO2e": 110.0,
            "HCHO": 0.0,
        },
        "Vendor-certified solid oxide fuel cell rates (CARB 2007 distributed generation "
        "certification basis). Non-combustion, so criteria pollutants are trivial; CO2 is not.",
    ),
}

#: Default heat rates, Btu/kWh HHV. Heat rate is the whole reason a config change
#: can move a project across a permit threshold without changing its MW.
_HEAT_RATE: dict[PrimeMover, float] = {
    PrimeMover.SIMPLE_CYCLE_TURBINE: 10_500.0,
    PrimeMover.COMBINED_CYCLE_TURBINE: 6_800.0,
    PrimeMover.RECIP_LEAN_BURN: 8_500.0,
    PrimeMover.RECIP_RICH_BURN: 9_200.0,
    PrimeMover.DIESEL_RECIP: 7_500.0,
    PrimeMover.FUEL_CELL: 7_400.0,
}

#: Fractional reduction by control, per pollutant.
_CONTROL_EFFICIENCY: dict[Control, dict[str, float]] = {
    Control.DLN: {"NOx": 0.69},  # 0.32 -> ~0.099 lb/MMBtu, AP-42 3.1
    Control.WATER_INJECTION: {"NOx": 0.60},
    Control.SCR: {"NOx": 0.90},
    Control.OXIDATION_CATALYST: {"CO": 0.90, "VOC": 0.50, "HCHO": 0.70},
    # Tier 4 is handled as an output-based override, not a percentage.
    Control.TIER4: {},
}

#: EPA Tier 4 final, g/kWh of engine output, > 900 kW gensets.
#: 40 CFR 1039.101 Table 7. Output-based, so it does not scale with heat rate.
_TIER4_OUTPUT_BASED = {"NOx": 0.67, "PM10": 0.03, "PM2.5": 0.03, "CO": 3.5, "VOC": 0.19}

_G_PER_LB = 453.592


class ConfigError(ValueError):
    """The generation config is not physically or legally coherent."""


@dataclass(frozen=True)
class GenerationConfig:
    """A proposed onsite generation plant.

    `run_hours` below 8760 only counts toward PTE if `enforceable_limit` is True,
    meaning the developer accepts a federally enforceable permit condition capping
    operation. Without that condition the agency computes PTE at 8760 regardless of
    what the developer says they intend to run.
    """

    mw: float
    prime_mover: PrimeMover
    fuel: Fuel = Fuel.NATURAL_GAS
    controls: tuple[Control, ...] = ()
    run_hours: float = 8760.0
    enforceable_limit: bool = False
    heat_rate_btu_kwh: float | None = None
    #: Split into N independent plants on separate parcels under separate ownership.
    #: Only defensible when the units are genuinely not a single "stationary source"
    #: (contiguous, common control, same SIC). See `pathway.aggregation_warning`.
    units: int = 1

    def __post_init__(self) -> None:
        if self.mw <= 0:
            raise ConfigError("mw must be positive")
        if not 0 < self.run_hours <= 8760:
            raise ConfigError("run_hours must be in (0, 8760]")
        if self.fuel is Fuel.DIESEL and self.prime_mover in (
            PrimeMover.RECIP_LEAN_BURN,
            PrimeMover.RECIP_RICH_BURN,
            PrimeMover.FUEL_CELL,
        ):
            raise ConfigError(f"{self.prime_mover.value} does not burn diesel")
        if self.fuel is Fuel.NATURAL_GAS and self.prime_mover is PrimeMover.DIESEL_RECIP:
            raise ConfigError("diesel_recip requires diesel fuel")
        if Control.TIER4 in self.controls and self.prime_mover is not PrimeMover.DIESEL_RECIP:
            raise ConfigError("Tier 4 certification applies to compression ignition engines")
        for turbine_only in (Control.DLN, Control.WATER_INJECTION):
            if turbine_only in self.controls and "turbine" not in self.prime_mover.value:
                raise ConfigError(f"{turbine_only.value} applies to turbines only")

    @property
    def effective_run_hours(self) -> float:
        """The hours an agency will use to compute PTE."""
        return self.run_hours if self.enforceable_limit else 8760.0

    @property
    def heat_rate(self) -> float:
        return self.heat_rate_btu_kwh or _HEAT_RATE[self.prime_mover]

    @property
    def heat_input_mmbtu_hr(self) -> float:
        """Total site heat input at full load. This is the number the List of 28
        'more than 250 million Btu/hr' test is run against."""
        return self.mw * 1000.0 * self.heat_rate / 1e6

    @property
    def heat_input_per_unit_mmbtu_hr(self) -> float:
        return self.heat_input_mmbtu_hr / self.units

    def describe(self) -> str:
        controls = ", ".join(c.value for c in self.controls) or "uncontrolled"
        cap = (
            f", {self.run_hours:.0f} hr/yr federally enforceable cap"
            if self.enforceable_limit
            else ", no enforceable hour cap (PTE at 8760)"
        )
        split = f", split into {self.units} units" if self.units > 1 else ""
        return (
            f"{self.mw:.0f} MW {self.prime_mover.value} on {self.fuel.value} "
            f"({controls}){cap}{split}"
        )


@dataclass(frozen=True)
class EmissionsEstimate:
    """Potential to emit, tons per year, with the arithmetic left visible."""

    config: GenerationConfig
    tons_per_year: dict[str, float]
    lb_per_hour: dict[str, float]
    heat_input_mmbtu_hr: float
    basis: dict[str, str]

    def significant(self) -> dict[str, float]:
        """Pollutants above their PSD significant emission rate. At a major source
        these are the ones that need BACT."""
        return {
            p: t
            for p, t in self.tons_per_year.items()
            if p in SIGNIFICANT_EMISSION_RATES and t >= SIGNIFICANT_EMISSION_RATES[p]
        }

    def max_criteria_tpy(self) -> tuple[str, float]:
        """The single largest criteria pollutant. Usually NOx, and usually the one
        that decides the pathway."""
        criteria = {p: t for p, t in self.tons_per_year.items() if p not in ("CO2e", "HCHO")}
        pollutant = max(criteria, key=lambda p: criteria[p])
        return pollutant, criteria[pollutant]

    def total_hap_tpy(self) -> float:
        return self.tons_per_year.get("HCHO", 0.0)


def _apply_controls(
    factors: dict[str, float], controls: Iterable[Control]
) -> tuple[dict[str, float], list[str]]:
    out = dict(factors)
    notes: list[str] = []
    for control in controls:
        for pollutant, efficiency in _CONTROL_EFFICIENCY[control].items():
            if pollutant in out:
                before = out[pollutant]
                out[pollutant] = before * (1.0 - efficiency)
                notes.append(
                    f"{control.value}: {pollutant} {before:.4f} -> {out[pollutant]:.4f} lb/MMBtu "
                    f"({efficiency:.0%} reduction)"
                )
    return out, notes


def estimate(config: GenerationConfig) -> EmissionsEstimate:
    """Potential to emit for a generation config."""
    key = (config.prime_mover, config.fuel)
    if key not in _EF:
        raise ConfigError(f"no emission factors for {config.prime_mover.value} on {config.fuel.value}")
    ef_set = _EF[key]

    factors, control_notes = _apply_controls(ef_set.factors, config.controls)

    heat_input = config.heat_input_mmbtu_hr
    hours = config.effective_run_hours

    lb_hr: dict[str, float] = {}
    tpy: dict[str, float] = {}
    for pollutant in POLLUTANTS:
        if pollutant not in factors:
            continue
        lb_hr[pollutant] = factors[pollutant] * heat_input
        tpy[pollutant] = lb_hr[pollutant] * hours / 2000.0

    basis = {
        "emission_factors": ef_set.citation,
        "heat_rate": (
            f"{config.heat_rate:,.0f} Btu/kWh HHV"
            + ("" if config.heat_rate_btu_kwh else " (module default for this prime mover)")
        ),
        "heat_input": f"{config.mw:.0f} MW x 1000 kW/MW x {config.heat_rate:,.0f} Btu/kWh "
        f"/ 1e6 = {heat_input:,.0f} MMBtu/hr",
        "hours_basis": (
            f"{hours:,.0f} hr/yr from a federally enforceable permit condition"
            if config.enforceable_limit
            else f"{hours:,.0f} hr/yr — no enforceable cap, so PTE is computed at full-time "
            "operation regardless of intended dispatch"
        ),
        "controls": "; ".join(control_notes) or "none",
        "method": "PTE (tpy) = EF (lb/MMBtu) x heat input (MMBtu/hr) x hours (hr/yr) / 2000",
    }

    # Tier 4 final is certified on engine output, not fuel input, so it replaces the
    # AP-42 factors outright rather than discounting them.
    if Control.TIER4 in config.controls:
        for pollutant, g_per_kwh in _TIER4_OUTPUT_BASED.items():
            lb_hr[pollutant] = g_per_kwh * config.mw * 1000.0 / _G_PER_LB
            tpy[pollutant] = lb_hr[pollutant] * hours / 2000.0
        basis["controls"] = (
            "Tier 4 final certified engine — output-based limits from 40 CFR 1039.101 "
            "Table 7 (g/kWh) replace the AP-42 input-based factors"
        )

    return EmissionsEstimate(
        config=config,
        tons_per_year=tpy,
        lb_per_hour=lb_hr,
        heat_input_mmbtu_hr=heat_input,
        basis=basis,
    )


def hours_for_tpy_target(config: GenerationConfig, pollutant: str, target_tpy: float) -> float | None:
    """Annual run hours that would hold `pollutant` at or under `target_tpy`.

    This is the synthetic-minor calculation: how hard would you have to cap the
    plant to stay under a major source threshold. Returns None if the plant is
    already under the target at 8760, or if no cap can get there.
    """
    uncapped = estimate(
        GenerationConfig(
            mw=config.mw,
            prime_mover=config.prime_mover,
            fuel=config.fuel,
            controls=config.controls,
            run_hours=8760.0,
            enforceable_limit=True,
            heat_rate_btu_kwh=config.heat_rate_btu_kwh,
            units=config.units,
        )
    )
    full_year = uncapped.tons_per_year.get(pollutant)
    if not full_year:
        return None
    if full_year <= target_tpy:
        return None
    hours = 8760.0 * target_tpy / full_year
    return hours if hours >= 1 else None
