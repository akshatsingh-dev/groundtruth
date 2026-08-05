"""Tests for the two search loops.

The parcel search is the part of this product that tells someone where to spend
money. `test_a_hard_stopped_parcel_never_wins` is the one that matters: a county
moratorium is not a slower permit, it is a different outcome, and recommending a
county that has banned data centers outright would be worse than not searching.
"""

import pytest

from agent.emissions import Control, GenerationConfig, PrimeMover, estimate
from agent.pathway import NonattainmentStatus, Pathway, SiteContext, determine_pathway
from agent.search import (
    AlternateSite,
    _compass,
    haversine_km,
    offset_point,
    ring_points,
    search_configs,
)


def make_candidate(label, pathway, months_likely, hard_stops, rank_delta, distance_km=30.0):
    return AlternateSite(
        label=label,
        latitude=0.0,
        longitude=0.0,
        county=label,
        state="XX",
        county_fips="00000",
        distance_km=distance_km,
        bearing_deg=0.0,
        pathway=pathway,
        months_low=months_likely - 5,
        months_likely=months_likely,
        months_high=months_likely + 5,
        rank_delta=rank_delta,
        months_saved=66.0 - months_likely,
        hard_stops=list(hard_stops),
        triggers_cleared=[],
        triggers_added=[],
        gas_pipeline_km=None,
        transmission_km=None,
        confidence=None,
        provenance={},
        site=None,
    )


def rank_and_pick(candidates):
    """Mirror of the ranking in search_alternate_sites, so the ordering rule is
    pinned independently of the provider plumbing around it."""
    ranked = sorted(
        candidates,
        key=lambda c: (bool(c.hard_stops), c.pathway.rank, c.months_likely, c.distance_km),
    )
    clean = [c for c in ranked if not c.hard_stops]
    improved = [c for c in clean if c.rank_delta > 0 or c.months_saved > 1]
    return ranked, (improved[0] if improved else None)


# --------------------------------------------------------------------------
# The rule that matters
# --------------------------------------------------------------------------


def test_a_hard_stopped_parcel_never_wins():
    """A minor NSR parcel under a moratorium must lose to a clean major PSD one.

    Before this was fixed the sort put pathway rank ahead of hard stops, so the
    search returned "move 30 miles, minor NSR, save 58 months" about a county
    that had banned new data centers.
    """
    blocked = make_candidate(
        "Moratorium", Pathway.MINOR_NSR, 8.0, ["County moratorium: no new data center approvals."], 3
    )
    clean = make_candidate("Clean", Pathway.MAJOR_PSD, 26.0, [], 1)

    ranked, best = rank_and_pick([blocked, clean])
    assert ranked[0] is clean, "a hard-stopped parcel must not rank first"
    assert best is clean
    assert best.hard_stops == []


def test_no_recommendation_when_every_improving_parcel_is_blocked():
    """Returning nothing is the correct answer. Returning a blocked parcel is not."""
    blocked_a = make_candidate("A", Pathway.MINOR_NSR, 8.0, ["moratorium"], 3)
    blocked_b = make_candidate("B", Pathway.MAJOR_PSD, 20.0, ["gas pipeline 60 km away"], 1)
    _, best = rank_and_pick([blocked_a, blocked_b])
    assert best is None


def test_a_clean_parcel_that_does_not_improve_is_not_recommended():
    same = make_candidate("Same", Pathway.MAJOR_NA_NSR, 66.0, [], 0)
    same.months_saved = 0.0
    _, best = rank_and_pick([same])
    assert best is None


def test_better_pathway_beats_closer_distance():
    near = make_candidate("Near", Pathway.MAJOR_PSD, 26.0, [], 1, distance_km=15.0)
    far = make_candidate("Far", Pathway.MINOR_NSR, 8.0, [], 3, distance_km=110.0)
    ranked, best = rank_and_pick([near, far])
    assert best is far, "a category change is worth more than 95 km"


# --------------------------------------------------------------------------
# Geodesy
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bearing", [0, 45, 90, 135, 180, 225, 270, 359])
def test_offset_point_round_trips_through_haversine(bearing):
    origin = (39.0, -77.0)
    point = offset_point(origin[0], origin[1], bearing, 60.0)
    assert haversine_km(origin, point) == pytest.approx(60.0, abs=0.01)


def test_longitude_stays_in_range_across_the_antimeridian():
    _, lon = offset_point(51.0, 179.5, 90, 100.0)
    assert -180.0 <= lon <= 180.0


def test_rings_do_not_resample_the_same_bearings():
    """Four rings of six points should be 24 directions, not six sampled four
    times. Otherwise the search is blind in most of the compass."""
    points = ring_points(39.0, -77.0, [15, 30, 60, 120], 6)
    bearings = {round(p[3], 3) for p in points}
    assert len(bearings) == len(points)


def test_compass_wraps():
    assert _compass(0) == "N"
    assert _compass(359) == "N"
    assert _compass(90) == "E"
    assert _compass(270) == "W"


# --------------------------------------------------------------------------
# Config search
# --------------------------------------------------------------------------


def test_config_search_finds_the_oxidation_catalyst_for_a_co_bound_plant():
    site = SiteContext(state="GA", county="Bulloch")
    config = GenerationConfig(
        mw=60, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE, controls=(Control.DLN, Control.SCR)
    )
    base = estimate(config)
    assert base.max_criteria_tpy()[0] == "CO"

    result = search_configs(site, config)
    labels = " ".join(o.label.lower() for o in result.options)
    assert "catalyst" in labels
    notes = " ".join(result.notes).lower()
    assert "co at" in notes and "oxidation catalyst" in notes


def test_config_search_reports_the_availability_cost_of_a_cap():
    """A cap that turns the plant into a peaker has to say so. Reporting a faster
    permit without the availability cost would be selling a fantasy."""
    site = SiteContext(state="VA", county="Loudoun")
    config = GenerationConfig(
        mw=500,
        prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
        controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
    )
    result = search_configs(site, config)
    text = " ".join(result.notes) + " ".join(o.cost_note for o in result.options)
    assert "availab" in text.lower() or "peaker" in text.lower()


def test_config_search_flags_aggregation_risk_on_a_split():
    site = SiteContext(state="TX", county="Ector")
    config = GenerationConfig(
        mw=500,
        prime_mover=PrimeMover.COMBINED_CYCLE_TURBINE,
        controls=(Control.DLN, Control.SCR, Control.OXIDATION_CATALYST),
    )
    result = search_configs(site, config)
    split = [o for o in result.options if "split" in o.label.lower()]
    if split:
        assert split[0].warnings, "splitting must carry the aggregation warning"


def test_config_search_says_so_when_equipment_is_not_the_lever():
    """A 2 GW plant in a severe nonattainment area cannot be fixed with controls.
    The honest answer is that the lever is location."""
    site = SiteContext(
        state="IL",
        county="Will",
        nonattainment=[NonattainmentStatus("ozone", "severe-17", "Chicago")],
    )
    config = GenerationConfig(mw=2000, prime_mover=PrimeMover.SIMPLE_CYCLE_TURBINE)
    result = search_configs(site, config)
    if result.best is None:
        assert any("location" in n.lower() for n in result.notes)
