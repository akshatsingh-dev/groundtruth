"""Tests for the local news opposition signal.

One rule carries this module: a source we could not read must never render as a
county with nothing happening. `test_unreachable_is_not_quiet` is that rule.
"""

import pytest

from ingest.localnews import Posture


def test_unreachable_is_not_quiet():
    """"We could not look" and "nobody is opposing" are different facts.

    The failure path used to return QUIET with the reason in a prose field.
    Every consumer downstream reads the enum, not the prose, so a county whose
    news source timed out looked identical to a county with no opposition. On a
    product whose whole job is telling people which projects are real, that is
    the wrong direction to be wrong in.
    """
    assert Posture.UNKNOWN is not Posture.QUIET
    assert Posture.UNKNOWN.value == "unknown"
    assert "unreachable" in Posture.UNKNOWN.label


def test_unknown_sits_off_the_scale():
    """UNKNOWN must not sort into the permissive end of the ordering, or a
    county nobody could read would look like the most attractive one."""
    assert Posture.UNKNOWN.rank == -1
    for posture in (Posture.QUIET, Posture.ACTIVE_INTEREST,
                    Posture.ORGANISED_OPPOSITION, Posture.FORMAL_ACTION):
        assert posture.rank >= 0
        assert Posture.UNKNOWN.rank < posture.rank


def test_the_real_scale_is_ordered_least_to_most_constrained():
    ranks = [
        Posture.QUIET.rank,
        Posture.ACTIVE_INTEREST.rank,
        Posture.ORGANISED_OPPOSITION.rank,
        Posture.FORMAL_ACTION.rank,
    ]
    assert ranks == sorted(ranks)
    assert ranks == [0, 1, 2, 3]


def test_every_posture_has_a_label():
    for posture in Posture:
        assert posture.label
        assert posture.label != posture.value


def test_module_imports_without_network_or_keys():
    """The agent has to keep running when this source is down, which it was for
    the whole of the build window."""
    from ingest import localnews

    assert localnews.authenticated() in (True, False)
    status = localnews.status()
    assert hasattr(status, "ok")
    assert hasattr(status, "reason")
