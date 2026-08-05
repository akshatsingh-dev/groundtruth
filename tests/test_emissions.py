"""Tests for the potential-to-emit estimator.

These check the arithmetic and the legal rules that the arithmetic encodes. The
one that matters most is `test_run_hours_ignored_without_enforceable_limit` — if
that regresses, the tool tells developers their plant is minor when the agency
will call it major, which is the most expensive way this product could be wrong.
"""

import pytest

from agent.emissions import (
    SIGNIFICANT_EMISSION_RATES,
    ConfigError,
    Control,
    Fuel,
    GenerationConfig,
    PrimeMover,
    estimate,
    hours_for_tpy_target,
)


def test_heat_input_is_mw_times_heat_rate():
    cfg = GenerationConfig(mw=500, prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE)
    # 500 MW * 1000 kW/MW * 6800 Btu/kWh / 1e6 = 3400 MMBtu/hr
    assert cfg.heat_input_mmbtu_hr == pytest.approx(3400.0)


def test_combined_cycle_burns_less_fuel_than_simple_cycle_for_same_mw():
    """The whole reason a config change can move a project across a threshold."""
    cc = GenerationConfig(mw=500, prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE)
    sc = GenerationConfig(mw=500, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE)
    assert cc.heat_input_mmbtu_hr < sc.heat_input_mmbtu_hr
    assert estimate(cc).tons_per_year["NOx"] < estimate(sc).tons_per_year["NOx"]


def test_run_hours_ignored_without_enforceable_limit():
    """PTE is maximum capacity to emit. Intending to run less is not a limit.

    Only a federally enforceable permit condition lowers PTE. This is the single
    most misunderstood rule in air permitting and the entire basis of synthetic
    minor status.
    """
    intended = GenerationConfig(
        mw=200, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE, run_hours=2000
    )
    full = GenerationConfig(mw=200, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE)
    assert intended.effective_run_hours == 8760.0
    assert estimate(intended).tons_per_year["NOx"] == pytest.approx(
        estimate(full).tons_per_year["NOx"]
    )


def test_enforceable_limit_lowers_pte_proportionally():
    capped = GenerationConfig(
        mw=200,
        prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
        run_hours=2190,
        enforceable_limit=True,
    )
    full = GenerationConfig(mw=200, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE)
    assert estimate(capped).tons_per_year["NOx"] == pytest.approx(
        estimate(full).tons_per_year["NOx"] * 0.25
    )


def test_scr_cuts_nox_ninety_percent():
    plain = estimate(GenerationConfig(mw=100, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE))
    scr = estimate(
        GenerationConfig(
            mw=100, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE, controls=(Control.SCR,)
        )
    )
    assert scr.tons_per_year["NOx"] == pytest.approx(plain.tons_per_year["NOx"] * 0.1)
    assert scr.tons_per_year["CO"] == pytest.approx(plain.tons_per_year["CO"])


def test_oxidation_catalyst_is_the_co_fix():
    """Uncontrolled CO is what pushes a large combined-cycle plant over a
    threshold even when NOx is handled. The config search has to be able to find
    this."""
    plain = estimate(
        GenerationConfig(
            mw=500,
            prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR),
        )
    )
    with_cat = estimate(
        GenerationConfig(
            mw=500,
            prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
        )
    )
    assert plain.tons_per_year["CO"] > 250
    assert with_cat.tons_per_year["CO"] == pytest.approx(plain.tons_per_year["CO"] * 0.1)


def test_controls_stack_multiplicatively():
    both = estimate(
        GenerationConfig(
            mw=100,
            prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR),
        )
    )
    plain = estimate(GenerationConfig(mw=100, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE))
    assert both.tons_per_year["NOx"] == pytest.approx(
        plain.tons_per_year["NOx"] * (1 - 0.69) * (1 - 0.90)
    )


def test_tier4_replaces_rather_than_discounts_factors():
    """Tier 4 is certified on engine output (g/kWh), not fuel input, so it is an
    override, not a percentage reduction."""
    plain = estimate(
        GenerationConfig(mw=50, prime_mover=PrimeMover.DIESEL_RECIP, fuel=Fuel.DIESEL)
    )
    tier4 = estimate(
        GenerationConfig(
            mw=50,
            prime_mover=PrimeMover.DIESEL_RECIP,
            fuel=Fuel.DIESEL,
            controls=(Control.TIER4,),
        )
    )
    assert tier4.tons_per_year["NOx"] < plain.tons_per_year["NOx"] * 0.1
    # 0.67 g/kWh * 50,000 kW / 453.592 g/lb = 73.9 lb/hr
    assert tier4.lb_per_hour["NOx"] == pytest.approx(73.86, rel=0.01)


def test_engines_emit_far_more_nox_per_mmbtu_than_turbines():
    engine = estimate(GenerationConfig(mw=100, prime_mover=PrimeMover.RECIP_LEAN_BURN))
    turbine = estimate(GenerationConfig(mw=100, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE))
    assert engine.tons_per_year["NOx"] > turbine.tons_per_year["NOx"] * 2


def test_fuel_cell_is_trivial_on_criteria_pollutants_but_not_on_co2():
    fc = estimate(GenerationConfig(mw=100, prime_mover=PrimeMover.FUEL_CELL))
    assert fc.tons_per_year["NOx"] < 10
    assert fc.tons_per_year["CO2e"] > 100_000


def test_significant_pollutants_use_psd_significance_thresholds():
    est = estimate(
        GenerationConfig(
            mw=500,
            prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR),
        )
    )
    significant = est.significant()
    for pollutant, tpy in significant.items():
        assert tpy >= SIGNIFICANT_EMISSION_RATES[pollutant]
    assert "NOx" in significant


def test_max_criteria_excludes_co2_and_haps():
    est = estimate(GenerationConfig(mw=500, prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE))
    pollutant, _ = est.max_criteria_tpy()
    assert pollutant not in ("CO2e", "HCHO")


def test_hours_for_tpy_target_scales_linearly():
    cfg = GenerationConfig(mw=200, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE)
    full = estimate(cfg).tons_per_year["NOx"]
    hours = hours_for_tpy_target(cfg, "NOx", full / 2)
    assert hours == pytest.approx(4380.0)


def test_hours_for_tpy_target_returns_none_when_already_under():
    cfg = GenerationConfig(mw=5, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE)
    assert hours_for_tpy_target(cfg, "NOx", 10_000) is None


def test_basis_records_the_arithmetic():
    est = estimate(GenerationConfig(mw=500, prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE))
    assert "AP-42" in est.basis["emission_factors"]
    assert "8,760" in est.basis["hours_basis"]
    assert "MMBtu/hr" in est.basis["heat_input"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mw": 0, "prime_mover": PrimeMover.SIMPLE_CYCLE_TURBINE},
        {"mw": 100, "prime_mover": PrimeMover.SIMPLE_CYCLE_TURBINE, "run_hours": 9000},
        {"mw": 100, "prime_mover": PrimeMover.RECIP_LEAN_BURN, "fuel": Fuel.DIESEL},
        {"mw": 100, "prime_mover": PrimeMover.DIESEL_RECIP, "fuel": Fuel.NATURAL_GAS},
        {
            "mw": 100,
            "prime_mover": PrimeMover.SIMPLE_CYCLE_TURBINE,
            "controls": (Control.TIER4,),
        },
        {
            "mw": 100,
            "prime_mover": PrimeMover.RECIP_LEAN_BURN,
            "controls": (Control.DLN,),
        },
    ],
)
def test_incoherent_configs_are_rejected(kwargs):
    with pytest.raises(ConfigError):
        GenerationConfig(**kwargs)
