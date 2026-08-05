"""Tests for the permit pathway decision engine.

The claim the product makes is that the same plant gets a different permit in two
different counties. `test_same_plant_different_county_different_pathway` is that
claim, as a test. If it fails, there is no product.
"""

import pytest

from agent.emissions import Control, Fuel, GenerationConfig, PrimeMover, estimate
from agent.pathway import (
    NonattainmentStatus,
    Pathway,
    SiteContext,
    classify_source_category,
    determine_pathway,
    overlay_for,
    synthetic_minor_cap,
)


def cc_500mw(**overrides):
    kwargs = dict(
        mw=500,
        prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
        controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
    )
    kwargs.update(overrides)
    return estimate(GenerationConfig(**kwargs))


def small_turbine(mw=40, **overrides):
    kwargs = dict(
        mw=mw, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE, controls=(Control.DLN, Control.SCR)
    )
    kwargs.update(overrides)
    return estimate(GenerationConfig(**kwargs))


# --------------------------------------------------------------------------
# Source category
# --------------------------------------------------------------------------


def test_large_combined_cycle_is_on_the_list_of_28_at_100_tpy():
    finding = classify_source_category(
        GenerationConfig(mw=500, prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE)
    )
    assert finding.on_list_of_28
    assert finding.threshold_tpy == 100.0
    assert "steam" in finding.category.lower()


def test_simple_cycle_is_not_listed_so_threshold_stays_at_250():
    finding = classify_source_category(
        GenerationConfig(mw=500, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE)
    )
    assert not finding.on_list_of_28
    assert finding.threshold_tpy == 250.0


def test_small_combined_cycle_under_250_mmbtu_is_not_listed():
    """The listed category has a heat input floor. A small CC plant misses it."""
    cfg = GenerationConfig(mw=30, prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE)
    assert cfg.heat_input_mmbtu_hr < 250
    finding = classify_source_category(cfg)
    assert not finding.on_list_of_28
    assert finding.threshold_tpy == 250.0


def test_engines_are_not_listed():
    finding = classify_source_category(
        GenerationConfig(mw=200, prime_mover=PrimeMover.RECIP_LEAN_BURN)
    )
    assert not finding.on_list_of_28
    assert finding.threshold_tpy == 250.0


# --------------------------------------------------------------------------
# The core claim
# --------------------------------------------------------------------------


def test_same_plant_different_county_different_pathway():
    """The product in one test. Same 500 MW plant, two counties.

    County A: attainment, clean increment, no Class I nearby.
    County B: severe ozone nonattainment.
    """
    est = cc_500mw()

    county_a = SiteContext(state="TX", county="Ector", gas_pipeline_km=2.0)
    county_b = SiteContext(
        state="TX",
        county="Harris",
        nonattainment=[NonattainmentStatus("ozone", "severe-15", "Houston-Galveston-Brazoria")],
        gas_pipeline_km=2.0,
    )

    a = determine_pathway(est, county_a)
    b = determine_pathway(est, county_b)

    assert b.pathway.rank > a.pathway.rank
    assert b.months_likely > a.months_likely
    assert b.pathway is Pathway.MAJOR_NA_NSR
    assert b.offsets_required_tons and b.offsets_required_tons > 0


def test_nonattainment_severity_lowers_the_threshold():
    """A plant that is minor in a moderate area is major in a severe one."""
    est = small_turbine(mw=90)
    moderate = determine_pathway(
        est,
        SiteContext(
            state="GA",
            county="Fulton",
            nonattainment=[NonattainmentStatus("ozone", "moderate", "Atlanta")],
        ),
    )
    severe = determine_pathway(
        est,
        SiteContext(
            state="IL",
            county="Will",
            nonattainment=[NonattainmentStatus("ozone", "severe-17", "Chicago")],
        ),
    )
    assert severe.applicable_threshold < moderate.applicable_threshold
    assert severe.pathway is Pathway.MAJOR_NA_NSR


def test_offsets_scale_with_classification():
    est = cc_500mw()
    moderate = determine_pathway(
        est,
        SiteContext(
            state="OH",
            county="Cuyahoga",
            nonattainment=[NonattainmentStatus("ozone", "moderate", "Cleveland")],
        ),
    )
    extreme = determine_pathway(
        est,
        SiteContext(
            state="CA",
            county="San Bernardino",
            nonattainment=[NonattainmentStatus("ozone", "extreme", "South Coast")],
        ),
    )
    assert extreme.offsets_required_tons > moderate.offsets_required_tons
    assert extreme.hard_stops, "extreme-area offsets should be flagged as a hard stop"


def test_pm25_nonattainment_counts_nox_and_so2_as_precursors():
    est = cc_500mw()
    result = determine_pathway(
        est,
        SiteContext(
            state="PA",
            county="Allegheny",
            nonattainment=[NonattainmentStatus("pm25", "moderate", "Pittsburgh")],
        ),
    )
    assert result.pathway is Pathway.MAJOR_NA_NSR
    assert result.controlling_pollutant in ("NOx", "SO2", "PM2.5")


def test_small_clean_plant_in_a_clean_county_is_minor():
    est = small_turbine(mw=25)
    result = determine_pathway(est, SiteContext(state="GA", county="Bulloch", gas_pipeline_km=3))
    assert result.pathway in (Pathway.MINOR_NSR, Pathway.PERMIT_BY_RULE)
    assert result.months_likely < 12
    assert not result.hard_stops


def test_texas_permit_by_rule_is_available_for_small_sources():
    est = estimate(
        GenerationConfig(
            mw=5,
            prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
        )
    )
    tx = determine_pathway(est, SiteContext(state="TX", county="Ector", gas_pipeline_km=2))
    ga = determine_pathway(est, SiteContext(state="GA", county="Bulloch", gas_pipeline_km=2))
    assert tx.pathway is Pathway.PERMIT_BY_RULE
    assert ga.pathway is Pathway.MINOR_NSR
    assert tx.months_likely < ga.months_likely


def test_co_not_nox_is_the_binding_pollutant_on_uncontrolled_turbines():
    """A 15 MW turbine with DLN and SCR still emits ~57 tpy of CO, because
    neither control touches CO. Anyone screening on NOx alone misses this, and it
    is the first thing the config search should find."""
    est = small_turbine(mw=15)
    pollutant, tpy = est.max_criteria_tpy()
    assert pollutant == "CO"
    assert tpy > 50
    with_catalyst = estimate(
        GenerationConfig(
            mw=15,
            prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
        )
    )
    assert with_catalyst.max_criteria_tpy()[1] < 10


# --------------------------------------------------------------------------
# Overlays
# --------------------------------------------------------------------------


def test_class_i_area_within_100km_adds_time_to_a_major_source():
    est = cc_500mw()
    near = determine_pathway(
        est, SiteContext(state="VA", county="Page", class_i_areas=[("Shenandoah NP", 40)])
    )
    far = determine_pathway(
        est, SiteContext(state="VA", county="Mecklenburg", class_i_areas=[("Shenandoah NP", 400)])
    )
    assert near.months_likely > far.months_likely
    fired = {t.name for t in near.fired}
    assert "class_i_aqrv" in fired


def test_class_i_does_not_penalise_a_minor_source():
    est = small_turbine(mw=20)
    result = determine_pathway(
        est, SiteContext(state="GA", county="Rabun", class_i_areas=[("Cohutta Wilderness", 30)])
    )
    class_i = next(t for t in result.triggers if t.name == "class_i_aqrv")
    assert class_i.months_added == 0.0


def test_consumed_increment_is_a_hard_stop_at_95_percent():
    est = cc_500mw()
    result = determine_pathway(
        est, SiteContext(state="OH", county="Lake", increment_consumed={"NOx": 0.97})
    )
    assert any("increment" in stop.lower() for stop in result.hard_stops)


def test_new_jersey_stacks_otr_ej_and_toxics():
    """The Nebius failure mode. NJ is not slow for one reason, it is slow for
    three overlapping ones."""
    est = cc_500mw()
    nj = determine_pathway(
        est, SiteContext(state="NJ", county="Middlesex", residential_within_1km=2000)
    )
    tx = determine_pathway(est, SiteContext(state="TX", county="Ector"))
    fired = {t.name for t in nj.fired}
    assert {"ozone_transport_region", "ej_denial_authority", "state_toxics"} <= fired
    assert nj.months_likely > tx.months_likely * 1.5
    assert any("EJ" in stop for stop in nj.hard_stops)


def test_otr_threshold_is_applied_not_just_announced():
    """New Jersey has no Green Book ozone listing at many parcels, but CAA 184
    makes the whole state behave like a moderate nonattainment area for NOx.

    The trigger text used to claim a 50 tpy threshold that the engine never
    applied, so a clean-on-paper NJ parcel scored major PSD at 100 tpy instead of
    nonattainment NSR at 50. That is the Vineland failure mode, and getting it
    wrong tells a developer the easier of two answers.
    """
    est = estimate(
        GenerationConfig(
            mw=150,
            prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
        )
    )
    nox = est.tons_per_year["NOx"]
    assert 50 < nox < 100, "config must sit between the OTR and PSD thresholds to test this"

    nj = determine_pathway(est, SiteContext(state="NJ", county="Cumberland"))
    ga = determine_pathway(est, SiteContext(state="GA", county="Bulloch"))

    assert nj.pathway is Pathway.MAJOR_NA_NSR
    assert nj.applicable_threshold == 50.0
    assert ga.pathway is not Pathway.MAJOR_NA_NSR


def test_consumed_increment_costs_time_in_nonattainment_too():
    """Increment is consumed regardless of which review programme applies. The
    months were only being added under PSD, so a nonattainment site with a full
    increment looked cheaper than an attainment one."""
    est = cc_500mw()
    na = [NonattainmentStatus("ozone", "moderate", "Some Area")]
    clean = determine_pathway(est, SiteContext(state="OH", county="Lake", nonattainment=na))
    consumed = determine_pathway(
        est,
        SiteContext(
            state="OH", county="Lake", nonattainment=na, increment_consumed={"NOx": 0.85}
        ),
    )
    assert consumed.months_likely > clean.months_likely


def test_permit_by_rule_is_not_available_to_a_large_plant():
    """A tons-only gate handed a 75 MW combined-cycle plant a permit by rule in
    Texas. Real PBRs carry equipment and heat-input limits."""
    big = estimate(
        GenerationConfig(
            mw=75,
            prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
        )
    )
    assert big.heat_input_mmbtu_hr > 100
    result = determine_pathway(big, SiteContext(state="TX", county="Ector", gas_pipeline_km=2))
    assert result.pathway is not Pathway.PERMIT_BY_RULE


def test_distant_gas_pipeline_is_a_hard_stop():
    """New Mexico. The plant was permittable. The pipeline was not."""
    est = cc_500mw()
    result = determine_pathway(est, SiteContext(state="NM", county="Dona Ana", gas_pipeline_km=60))
    assert any("pipeline" in stop.lower() for stop in result.hard_stops)
    trigger = next(t for t in result.fired if t.name == "gas_reachability")
    assert trigger.months_added >= 12


def test_moratorium_is_a_hard_stop_regardless_of_air_pathway():
    est = small_turbine(mw=10)
    result = determine_pathway(
        est,
        SiteContext(
            state="VA",
            county="Prince William",
            moratorium=True,
            moratorium_note="Board paused new data center rezonings pending an ordinance rewrite.",
        ),
    )
    assert result.pathway in (Pathway.MINOR_NSR, Pathway.PERMIT_BY_RULE)
    assert result.hard_stops, "a clean air pathway does not clear a county moratorium"


def test_january_2026_turbine_rule_always_fires_for_turbines():
    """The trailer-mounted path is unsettled, not closed.

    Most coverage of the 15 January 2026 rule says it shut the nonroad-engine
    reading. It did the opposite in direction: it finalised a conditional
    exclusion that is not yet operative. The tool must not tell anyone a fast
    path is available, and must not tell them it is definitively gone either.
    Both errors are expensive in different directions.
    """
    result = determine_pathway(small_turbine(mw=30), SiteContext(state="TN", county="Shelby"))
    nsps = next(t for t in result.fired if t.name == "nsps_turbine")
    assert "91 Fed. Reg. 1910" in nsps.citation
    assert "KKKKa" in nsps.citation
    detail = nsps.detail.lower()
    assert "not operative" in detail
    assert "open legal question" in detail
    assert "closed" not in detail, "the rule did not close the nonroad reading"


def test_complex_terrain_adds_modeling_time():
    est = cc_500mw()
    flat = determine_pathway(est, SiteContext(state="TX", county="Ector", terrain_relief_m=10))
    hilly = determine_pathway(est, SiteContext(state="TX", county="Ector", terrain_relief_m=400))
    assert hilly.months_likely > flat.months_likely


def test_split_units_flag_aggregation_risk():
    est = cc_500mw(units=4)
    result = determine_pathway(est, SiteContext(state="TX", county="Ector"))
    assert "source_aggregation_risk" in {t.name for t in result.fired}


# --------------------------------------------------------------------------
# Synthetic minor
# --------------------------------------------------------------------------


def test_synthetic_minor_cap_is_honest_about_availability():
    """A cap that turns the plant into a peaker is not a solution, and the tool
    has to say so rather than reporting a faster permit."""
    est = cc_500mw()
    result = synthetic_minor_cap(est, SiteContext(state="VA", county="Loudoun"))
    assert result is not None
    if result["feasible"]:
        assert result["availability"] > 0.11
    else:
        assert "peaker" in result["reason"]


def test_synthetic_minor_cap_returns_none_when_already_minor():
    est = small_turbine(mw=10)
    assert synthetic_minor_cap(est, SiteContext(state="GA", county="Bulloch")) is None


def test_enforceable_cap_produces_synthetic_minor_pathway():
    est = estimate(
        GenerationConfig(
            mw=120,
            prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE,
            controls=(Control.DLN, Control.SCR),
            run_hours=3000,
            enforceable_limit=True,
        )
    )
    result = determine_pathway(est, SiteContext(state="GA", county="Bulloch"))
    assert result.pathway is Pathway.SYNTHETIC_MINOR
    assert "3,000 hr/yr" in " ".join(result.narrative) or "3000" in " ".join(result.narrative)


# --------------------------------------------------------------------------
# Housekeeping
# --------------------------------------------------------------------------


def test_pathway_rank_orders_easiest_to_hardest():
    ranks = [p.rank for p in Pathway]
    assert ranks == sorted(ranks)
    assert Pathway.PERMIT_BY_RULE.rank < Pathway.MINOR_NSR.rank < Pathway.MAJOR_PSD.rank
    assert Pathway.MAJOR_PSD.rank < Pathway.MAJOR_NA_NSR.rank


def test_unmodelled_state_falls_back_to_federal_default_and_says_so():
    overlay = overlay_for("WY")
    assert overlay["multiplier"] == 1.0
    assert "not one of the eight modelled" in overlay["notes"]


def test_every_fired_trigger_carries_a_citation():
    est = cc_500mw()
    result = determine_pathway(
        est,
        SiteContext(
            state="NJ",
            county="Middlesex",
            nonattainment=[NonattainmentStatus("ozone", "moderate", "NY-NJ-CT")],
            class_i_areas=[("Brigantine Wilderness", 80)],
            increment_consumed={"NOx": 0.9},
            gas_pipeline_km=30,
            residential_within_1km=3000,
            terrain_relief_m=20,
            litigation=["Some v. Someone, D.N.J. 2026"],
        ),
    )
    for trigger in result.triggers:
        assert trigger.citation, f"{trigger.name} has no citation"
        assert trigger.detail, f"{trigger.name} has no detail"
    assert result.months_likely > 30
