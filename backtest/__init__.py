"""Backtest — reconstruct the pre-failure record for real projects and re-run the engine.

n = 3. Demonstration, not an out-of-sample test. Read `docs/backtest-notes.md`
before quoting any of it.

    from backtest import run_all
    run_all()
"""

from .cases import CASES, JUPITER, MEMPHIS, VINELAND, Case, Fact, run_all, run_case

__all__ = [
    "CASES",
    "Case",
    "Fact",
    "JUPITER",
    "MEMPHIS",
    "VINELAND",
    "run_all",
    "run_case",
]
