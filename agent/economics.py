"""What a permit delay costs, in dollars.

Every other layer in this repo answers a regulatory question. This one answers
the question the regulatory answer implies: a 53-month delay is 53 months of
megawatts that cannot be energised, which is a fleet of accelerators that cannot
run, which at today's rate is a number.

The chain, and every link is shown in the output:

    plant MW  ->  IT load MW        divide by PUE (or take the stated IT load)
    IT load   ->  accelerator count divide by node watts per accelerator
    count     ->  GPU-hours         multiply by delayed hours
    GPU-hours ->  billable hours    multiply by utilisation
    billable  ->  dollars           multiply by $/GPU-hour

Four things about this number that have to be said every time it is quoted, and
which the output says inline rather than in a footnote:

1.  It is an OPPORTUNITY COST under an explicit counterfactual: that the whole
    blocked capacity would have been sold at spot, at the stated utilisation,
    for every month of the delay. That counterfactual is generous. An operator
    on a contracted lease earns a different and usually smaller number, and when
    a reference contract is available this module prices that scenario too.
2.  Spot rates are volatile. This is a mark at today's rate, not a forecast.
    Extrapolating a spot GPU rate four years forward is not defensible and the
    output refuses to describe the total as an expected value.
3.  It does not double count. If the campus is grid-connected and the onsite
    plant is firming rather than the sole source, the air permit is not blocking
    the whole IT load, and `plant_share_of_it_load` has to say so.
4.  It is the cost of not finding the alternative, not an inevitability. Where
    the config search or the site search found a route that clears the pathway,
    the valuation reports how much of the loss that route recovers. That is the
    part a developer can act on.

Nothing in here is a market forecast, a valuation opinion, or investment advice.
It is arithmetic over a stated counterfactual with every input exposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ingest.gpu_pricing import (
    DEFAULT_GPU_CLASS,
    MARKETPLACE_SPOT,
    PUBLISHED_LIST,
    power_for,
    spot_rates,
)

# --------------------------------------------------------------------------
# Constants and defaults
# --------------------------------------------------------------------------

#: 8760/12. Using this rather than 730.5 or 720 keeps a months figure and an
#: hours figure reconcilable with the PTE math, which is all built on 8760.
HOURS_PER_MONTH = 8760.0 / 12.0

#: Power usage effectiveness: total facility power divided by IT power. Used
#: only when the caller gives a plant size and no IT load. 1.30 is a modern
#: air-cooled-to-hybrid campus at scale; a liquid-cooled hall runs nearer 1.15
#: and an older facility nearer 1.45.
DEFAULT_PUE = 1.30
PUE_BASIS = (
    "Uptime Institute annual survey has the global large-facility average around "
    "1.5-1.6 and new hyperscale build around 1.2. 1.30 is the middle for a new "
    "campus with hybrid air and liquid cooling."
)

#: Fraction of installed accelerator-hours that are actually sold. The low case
#: is a fleet that never fills; the high case is a fleet that is effectively
#: pre-sold. Neither is 100%: ramp, node failure, reprovisioning between
#: tenants, and firmware and driver maintenance all come out of the same hours.
UTILISATION_LOW = 0.60
UTILISATION_LIKELY = 0.80
UTILISATION_HIGH = 0.92
UTILISATION_BASIS = (
    "Low 60% is a merchant fleet that has not filled. Likely 80% is a fleet with "
    "committed tenants and normal churn, maintenance and node failure. High 92% is "
    "effectively pre-sold capacity with a maintenance floor. 100% is not reachable."
)

#: Multipliers on the datasheet node power figure, applied to get an accelerator
#: count range. Designers do not fill a hall to nameplate, so the low-count case
#: carries a design margin; sustained training draw sits under datasheet maximum,
#: so the high-count case packs more in.
WATTS_MARGIN_LOW_COUNT = 1.08
WATTS_MARGIN_HIGH_COUNT = 0.88
WATTS_BASIS = (
    "Node figures are datasheet maxima. The low accelerator count applies an 8% "
    "design margin, which is how a hall is actually sized. The high count assumes "
    "sustained draw runs at 88% of datasheet maximum, which is where training "
    "workloads sit."
)


# --------------------------------------------------------------------------
# Reference contracts
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceContract:
    """A publicly reported capacity contract, used only as a sanity check.

    The point of these is to catch a valuation that has gone wrong by an order
    of magnitude. If the opportunity cost of blocking a site implies revenue per
    megawatt wildly different from what someone actually signed for that same
    capacity, the assumptions are wrong, not the market.
    """

    name: str
    counterparty: str
    total_usd: float
    years: float
    it_load_mw: float
    site: str
    source: str

    @property
    def usd_per_mw_year(self) -> float:
        return self.total_usd / self.years / self.it_load_mw


#: One entry, because one is what is publicly reported at parcel level with both
#: a contract value and an IT load. Verified in docs/evidence.md claim E12.
REFERENCE_CONTRACTS: tuple[ReferenceContract, ...] = (
    ReferenceContract(
        name="Nebius / Microsoft capacity agreement",
        counterparty="Microsoft",
        total_usd=17.4e9,
        years=5.0,
        it_load_mw=300.0,
        site="Vineland, Cumberland County, NJ",
        source="Nebius announcement, September 2025; 5-year term, $17.4B, 300 MW IT "
        "load at the Vineland campus (docs/evidence.md claim E12)",
    ),
)


def reference_contract_for(county: str | None, state: str | None) -> ReferenceContract | None:
    """The reported contract sitting over this parcel, if there is one.

    Matched on county and state rather than on developer name, because the
    contract is attached to the site's capacity and that is what a delay blocks.
    """
    if not county or not state:
        return None
    needle = f"{county.strip().lower()}"
    for contract in REFERENCE_CONTRACTS:
        site = contract.site.lower()
        if needle in site and state.strip().upper() in contract.site.upper():
            return contract
    return None


# --------------------------------------------------------------------------
# Pieces of the answer
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Assumption:
    """One input, its value, and why that value and not another."""

    name: str
    value: str
    basis: str

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "basis": self.basis}

    def line(self) -> str:
        return f"{self.name}: {self.value} — {self.basis}"


@dataclass(frozen=True)
class Scenario:
    """One valuation at one set of inputs."""

    label: str
    accelerators: int
    utilisation: float
    usd_per_gpu_hour: float
    rate_kind: str
    rate_source: str
    gpu_hours: float
    usd: float

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "accelerators": self.accelerators,
            "utilisation": round(self.utilisation, 3),
            "usd_per_gpu_hour": round(self.usd_per_gpu_hour, 4),
            "rate_kind": self.rate_kind,
            "rate_source": self.rate_source,
            "billable_gpu_hours": round(self.gpu_hours, 0),
            "usd": round(self.usd, 0),
        }


@dataclass(frozen=True)
class Mitigation:
    """A route the search already found that recovers part of the loss."""

    route: str
    label: str
    months_saved: float
    usd_recovered: float
    note: str

    def to_dict(self) -> dict:
        return {
            "route": self.route,
            "label": self.label,
            "months_saved": round(self.months_saved, 1),
            "usd_recovered": round(self.usd_recovered, 0),
            "note": self.note,
        }


@dataclass
class DelayValuation:
    """The full chain, with every assumption exposed."""

    gpu_class: str
    months_delayed: float
    it_load_mw: float
    blocked_it_load_mw: float
    accelerators_likely: int
    low: Scenario
    likely: Scenario
    high: Scenario
    chain: list[str]
    assumptions: list[Assumption]
    counterfactual: list[str]
    spread_drivers: list[str]
    rate_basis: str
    rate_fetched: str
    rate_is_stale: bool = False
    published_list_case: Scenario | None = None
    contracted_lease_case: Scenario | None = None
    cross_check: dict | None = None
    mitigations: list[Mitigation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # ---- the inverse, which is the number a developer acts on ----

    @property
    def per_month_low(self) -> float:
        return self.month_value()["low"]

    @property
    def per_month_likely(self) -> float:
        return self.month_value()["likely"]

    @property
    def per_month_high(self) -> float:
        return self.month_value()["high"]

    def headline(self) -> str:
        # "today's spot rate" is a claim about both freshness and provenance, so
        # it is only made when the rate is fresh and actually came off a market.
        # A fallback mark says which day it is from; a caller-supplied rate says
        # it was supplied.
        if self.likely.rate_kind == "caller-supplied":
            when = f"a supplied rate of ${self.likely.usd_per_gpu_hour:.2f}/GPU-hr"
        elif self.rate_is_stale:
            when = f"the {self.rate_fetched[:10]} reference rate"
        else:
            when = "today's spot rate"
        if not self.months_delayed:
            return (
                f"No delay against the announced date, so nothing to price. One month of "
                f"slip at this site would be worth {usd(self.month_value()['likely'])} at "
                f"{when}."
            )
        return (
            f"{self.months_delayed:.0f} months of delay at {self.blocked_it_load_mw:,.0f} MW "
            f"of blocked IT load is {usd(self.likely.usd)} of foregone compute revenue at "
            f"{when}, range {usd(self.low.usd)} to {usd(self.high.usd)}."
        )

    def month_value(self) -> dict:
        """What one month of permit delay is worth here.

        Computed from the scenario inputs rather than by dividing the total, so
        it is still a real number when the announced schedule has slack and the
        total is zero. Independent of how long the delay turns out to be, which
        is why it is the number a developer uses to decide whether a screen is
        worth paying for.
        """

        def per_month(scenario: Scenario) -> float:
            return (
                scenario.accelerators
                * HOURS_PER_MONTH
                * scenario.utilisation
                * scenario.usd_per_gpu_hour
            )

        return {
            "low": per_month(self.low),
            "likely": per_month(self.likely),
            "high": per_month(self.high),
        }

    def to_dict(self) -> dict:
        month = self.month_value()
        return {
            "headline": self.headline(),
            "gpu_class": self.gpu_class,
            "months_delayed": round(self.months_delayed, 1),
            "it_load_mw": round(self.it_load_mw, 1),
            "blocked_it_load_mw": round(self.blocked_it_load_mw, 1),
            "accelerators_likely": self.accelerators_likely,
            "foregone_revenue_usd": {
                "low": round(self.low.usd, 0),
                "likely": round(self.likely.usd, 0),
                "high": round(self.high.usd, 0),
            },
            "value_of_one_month_usd": {k: round(v, 0) for k, v in month.items()},
            "scenarios": {
                "low": self.low.to_dict(),
                "likely": self.likely.to_dict(),
                "high": self.high.to_dict(),
                "published_list": self.published_list_case.to_dict()
                if self.published_list_case
                else None,
                "contracted_lease": self.contracted_lease_case.to_dict()
                if self.contracted_lease_case
                else None,
            },
            "arithmetic": self.chain,
            "assumptions": [a.to_dict() for a in self.assumptions],
            "counterfactual": self.counterfactual,
            "spread_drivers": self.spread_drivers,
            "rate_basis": self.rate_basis,
            "rate_fetched": self.rate_fetched,
            "rate_is_stale": self.rate_is_stale,
            "cross_check": self.cross_check,
            "mitigations": [m.to_dict() for m in self.mitigations],
            "notes": self.notes,
        }


def usd(value: float) -> str:
    """Money at the precision the number deserves and no more.

    One decimal below $100M so a $11.6M/MW-year benchmark does not round to $12M
    and stop being comparable to the figure it is benchmarking.
    """
    magnitude = abs(value)
    if magnitude >= 1e9:
        return f"${value / 1e9:,.1f}B"
    if magnitude >= 100e6:
        return f"${value / 1e6:,.0f}M"
    if magnitude >= 1e6:
        return f"${value / 1e6:,.1f}M"
    if magnitude >= 1e3:
        return f"${value / 1e3:,.0f}k"
    return f"${value:,.0f}"


# --------------------------------------------------------------------------
# The valuation
# --------------------------------------------------------------------------


def price_the_delay(
    mw_it_load: float,
    months_delayed: float,
    gpu_class: str = DEFAULT_GPU_CLASS,
    utilisation: float | None = None,
    rate: float | None = None,
    *,
    pue: float | None = None,
    plant_mw: float | None = None,
    plant_share_of_it_load: float = 1.0,
    sole_power_source: bool = True,
    rates: dict | None = None,
    contract: ReferenceContract | None = None,
    it_load_derived: bool = False,
) -> DelayValuation:
    """Foregone compute revenue from a permit delay, low / likely / high.

    `mw_it_load` is IT load, not plant nameplate. Cooling and facility overhead
    sit between the two and PUE is how you cross that gap; pass `plant_mw` as
    well and the PUE is derived from the pair rather than assumed.

    `utilisation` and `rate` override the module defaults and the fetched rate
    respectively. Supplying either collapses that axis of the spread to a point
    and the output says so, because a range that pretends to span an input the
    caller pinned is a lie about the uncertainty.

    `plant_share_of_it_load` is the double-counting guard. It is the fraction of
    the IT load the permitted plant actually serves. Leave it at 1.0 only when
    the plant is genuinely the sole source. A grid-connected campus using the
    onsite plant for firming has a much smaller blocked load and therefore a
    much smaller number, and claiming the full load in that case is the single
    easiest way to make this analysis worthless.
    """
    if mw_it_load <= 0:
        raise ValueError("mw_it_load must be positive")
    if months_delayed < 0:
        raise ValueError("months_delayed cannot be negative")
    if not 0 < plant_share_of_it_load <= 1.0:
        raise ValueError("plant_share_of_it_load must be in (0, 1]")

    spec = power_for(gpu_class)
    table = rates if rates is not None else spot_rates([gpu_class])
    entry = (table.get("rates") or {}).get(gpu_class) or {}
    spot = entry.get(MARKETPLACE_SPOT)
    listed = entry.get(PUBLISHED_LIST)

    assumptions: list[Assumption] = []
    chain: list[str] = []
    notes: list[str] = list(table.get("notes") or [])

    # ---- 1. IT load ----
    if plant_mw and mw_it_load:
        derived_pue = plant_mw / mw_it_load
        assumptions.append(
            Assumption(
                "PUE",
                f"{derived_pue:.2f} (derived)",
                f"{plant_mw:,.0f} MW of generation stated for a {mw_it_load:,.0f} MW IT load. "
                f"Not assumed — it is the ratio the project itself implies.",
            )
        )
        chain.append(
            f"PUE = {plant_mw:,.0f} MW generation / {mw_it_load:,.0f} MW IT load = "
            f"{derived_pue:.2f}"
        )
    else:
        used_pue = pue if pue is not None else DEFAULT_PUE
        assumptions.append(
            Assumption(
                "PUE",
                f"{used_pue:.2f} ({'stated by caller' if pue is not None else 'module default'})",
                PUE_BASIS,
            )
        )
        if it_load_derived:
            chain.append(
                f"IT load = plant nameplate / PUE {used_pue:.2f} = {mw_it_load:,.0f} MW"
            )

    blocked_mw = mw_it_load * plant_share_of_it_load
    if plant_share_of_it_load < 1.0:
        assumptions.append(
            Assumption(
                "Share of IT load this plant serves",
                f"{plant_share_of_it_load:.0%}",
                "The campus has another source for the rest, so the air permit blocks only "
                "this share. Counting the whole IT load here would be double counting.",
            )
        )
        chain.append(
            f"Blocked IT load = {mw_it_load:,.0f} MW x {plant_share_of_it_load:.0%} = "
            f"{blocked_mw:,.0f} MW"
        )
    else:
        assumptions.append(
            Assumption(
                "Sole power source",
                "yes" if sole_power_source else "no, but share not supplied",
                "The permitted plant is treated as the only route to energising this load, so "
                "the full IT load is blocked. If the campus is grid-connected with the plant "
                "as firming, this is wrong and plant_share_of_it_load has to be set."
                if sole_power_source
                else "Caller says the plant is not the sole source but gave no share, so the "
                "full load is still being counted. This number is an upper bound until that "
                "share is supplied.",
            )
        )
        if not sole_power_source:
            notes.append(
                "The plant is flagged as not the sole power source but no share was supplied. "
                "The blocked load below is an upper bound."
            )

    # ---- 2. accelerator count ----
    node_kw = spec.node_watts / 1000.0
    count_likely = int(blocked_mw * 1000.0 / node_kw)
    count_low = int(blocked_mw * 1000.0 / (node_kw * WATTS_MARGIN_LOW_COUNT))
    count_high = int(blocked_mw * 1000.0 / (node_kw * WATTS_MARGIN_HIGH_COUNT))

    assumptions.append(
        Assumption(
            f"Power per {gpu_class}",
            f"{spec.node_watts:,.0f} W at the server ({spec.board_watts:,.0f} W at the board)",
            spec.node_basis
            + " The gap between board and node is host CPU, DRAM, NICs, the switch fabric and "
            "power supply losses. Cooling and facility overhead are NOT in this figure — they "
            "are on the other side of PUE, and putting them in both places is how this "
            "arithmetic goes wrong by 30%.",
        )
    )
    assumptions.append(
        Assumption("Accelerator count margin", f"x{WATTS_MARGIN_LOW_COUNT:.2f} to x{WATTS_MARGIN_HIGH_COUNT:.2f} on node watts", WATTS_BASIS)
    )
    chain.append(
        f"Accelerators = {blocked_mw:,.0f} MW x 1,000 kW/MW / {node_kw:.3f} kW per {gpu_class} "
        f"= {count_likely:,} (range {count_low:,} to {count_high:,})"
    )

    # ---- 3. hours ----
    hours = months_delayed * HOURS_PER_MONTH
    chain.append(
        f"Delayed hours = {months_delayed:.1f} months x {HOURS_PER_MONTH:,.0f} hr/month "
        f"= {hours:,.0f} hr"
    )
    assumptions.append(
        Assumption(
            "Hours per month",
            f"{HOURS_PER_MONTH:,.0f}",
            "8,760/12, so this reconciles with the potential-to-emit math, which is all "
            "computed on an 8,760 hour year.",
        )
    )

    # ---- 4. utilisation ----
    if utilisation is not None:
        util_low = util_likely = util_high = float(utilisation)
        assumptions.append(
            Assumption(
                "Utilisation",
                f"{utilisation:.0%} (supplied by caller, pinned)",
                "The caller pinned this, so utilisation contributes nothing to the spread "
                "below. The range you see is rate and accelerator count only.",
            )
        )
    else:
        util_low, util_likely, util_high = (
            UTILISATION_LOW,
            UTILISATION_LIKELY,
            UTILISATION_HIGH,
        )
        assumptions.append(
            Assumption(
                "Utilisation",
                f"{util_low:.0%} / {util_likely:.0%} / {util_high:.0%}",
                UTILISATION_BASIS,
            )
        )

    # ---- 5. rate ----
    if rate is not None:
        rate_low = rate_likely = rate_high = float(rate)
        rate_kind = "caller-supplied"
        rate_source = "supplied by caller"
        rate_basis = f"${rate:.2f}/GPU-hr supplied by the caller, not sourced by this module."
        rate_fetched = table.get("fetched", "")
        rate_stale = False
        assumptions.append(
            Assumption(
                "Rate",
                f"${rate:.2f}/GPU-hr (supplied by caller, pinned)",
                "Not a sourced rate. Whoever supplied it owns it.",
            )
        )
    elif spot:
        rate_low = float(spot["low"])
        rate_likely = float(spot["usd_per_gpu_hour"])
        rate_high = float(spot["high"])
        rate_kind = MARKETPLACE_SPOT
        rate_source = ", ".join(spot["sources"])
        stale = " — DATED FALLBACK, not a live quote" if spot.get("stale") else ""
        rate_basis = (
            f"${rate_likely:.2f}/GPU-hr marketplace spot, median across {rate_source}, "
            f"low/high {rate_low:.2f}/{rate_high:.2f}{stale}"
        )
        # The oldest quote behind the figure, not the moment we assembled it.
        # A fallback mark stamped with now() would read as fresh.
        stamps = [q.get("fetched") for q in (spot.get("quotes") or []) if q.get("fetched")]
        rate_fetched = min(stamps) if stamps else table.get("fetched", "")
        rate_stale = bool(spot.get("stale"))
        assumptions.append(
            Assumption(
                "Rate",
                f"${rate_likely:.2f}/GPU-hr marketplace spot ({rate_low:.2f}-{rate_high:.2f})",
                f"Median across {rate_source}. Marketplace spot, not a published rate card — "
                f"the two are reported separately and never averaged. "
                + (
                    f"This is the {table.get('basis')} table captured on the date in "
                    f"rate_fetched, not a live quote."
                    if table.get("basis") == "fallback"
                    else "Live or same-day cached."
                ),
            )
        )
    else:
        raise ValueError(
            f"no marketplace spot rate available for {gpu_class!r} and no rate supplied; "
            f"refusing to invent one"
        )

    def scenario(label, count, util, price, kind, source) -> Scenario:
        gpu_hours = count * hours * util
        return Scenario(label, count, util, price, kind, source, gpu_hours, gpu_hours * price)

    low = scenario("low", count_low, util_low, rate_low, rate_kind, rate_source)
    likely = scenario("likely", count_likely, util_likely, rate_likely, rate_kind, rate_source)
    high = scenario("high", count_high, util_high, rate_high, rate_kind, rate_source)

    chain.append(
        f"Foregone revenue (likely) = {count_likely:,} accelerators x {hours:,.0f} hr x "
        f"{util_likely:.0%} utilisation x ${rate_likely:.2f}/GPU-hr = {usd(likely.usd)}"
    )
    chain.append(
        f"Value of one month = {usd(likely.usd)} / {months_delayed:.1f} months = "
        f"{usd(likely.usd / months_delayed)}"
        if months_delayed
        else "No delay against the announced date, so the total is zero."
    )

    # ---- 6. the two scenarios that are not spot ----
    published: Scenario | None = None
    if listed and rate is None:
        published = scenario(
            "published list rate",
            count_likely,
            util_likely,
            float(listed["usd_per_gpu_hour"]),
            PUBLISHED_LIST,
            ", ".join(listed["sources"]),
        )

    contracted: Scenario | None = None
    if contract is not None:
        # Back out an implied $/GPU-hour from the contract so the comparison is
        # like for like: same accelerator count, same utilisation, different price.
        contract_usd_for_delay = (
            contract.usd_per_mw_year * blocked_mw * (months_delayed / 12.0)
        )
        implied_rate = (
            contract_usd_for_delay / likely.gpu_hours if likely.gpu_hours else 0.0
        )
        contracted = Scenario(
            "contracted lease",
            count_likely,
            util_likely,
            implied_rate,
            "contracted",
            contract.name,
            likely.gpu_hours,
            contract_usd_for_delay,
        )

    # ---- 7. cross-check ----
    cross_check = None
    if contract is not None and blocked_mw > 0 and months_delayed > 0:
        implied_per_mw_year = likely.usd / blocked_mw / (months_delayed / 12.0)
        ratio = implied_per_mw_year / contract.usd_per_mw_year
        high_ratio = (
            high.usd / blocked_mw / (months_delayed / 12.0)
        ) / contract.usd_per_mw_year
        if ratio > 3.0 or ratio < 0.33:
            verdict = (
                f"FAILS. The spot counterfactual implies {ratio:.1f}x what was actually "
                f"signed for this capacity. Something in the chain above is wrong — check "
                f"watts per accelerator and whether the IT load or the plant nameplate went "
                f"into the accelerator count."
            )
        else:
            verdict = (
                f"Holds. The spot counterfactual implies {ratio:.2f}x the signed rate, which "
                f"is the right direction and the right magnitude: selling into a spot market "
                f"should price above a five-year take-or-pay lease, and not by an order of "
                f"magnitude."
            )
        cross_check = {
            "contract": contract.name,
            "contract_usd": contract.total_usd,
            "contract_years": contract.years,
            "contract_it_load_mw": contract.it_load_mw,
            "contract_usd_per_mw_year": round(contract.usd_per_mw_year, 0),
            "implied_usd_per_mw_year_likely": round(implied_per_mw_year, 0),
            "ratio_likely": round(ratio, 2),
            "ratio_high": round(high_ratio, 2),
            "verdict": verdict,
            "source": contract.source,
            "high_case_note": (
                f"The high case implies {high_ratio:.1f}x the signed rate. That is not a "
                f"forecast — it is the 75th percentile of a thin retail offer book applied "
                f"to {count_high:,} accelerators, and a fleet that size would move the price "
                f"it was selling into long before it got there."
            ),
        }

    # ---- 8. framing ----
    counterfactual = [
        f"Counterfactual: the full {blocked_mw:,.0f} MW of blocked IT load would have been "
        f"energised on the announced date, filled with {gpu_class} accelerators, and sold at "
        f"spot at {util_likely:.0%} utilisation for every one of the {months_delayed:.0f} "
        f"delayed months.",
        "That counterfactual is generous. It assumes the capacity had a buyer at spot for the "
        "whole period, that the fleet was procured and installed on the same schedule as the "
        "power, and that nothing else on the critical path — turbines, transformers, "
        "interconnection, the building — would have bound first.",
        "This is an opportunity cost, not a cash loss. An operator on a contracted lease has a "
        "different and usually smaller number, because a lease trades price for certainty.",
        f"The dollar figures are a mark at today's rate. Spot GPU pricing moves daily. "
        f"Extrapolating a spot rate {months_delayed:.0f} months forward is not defensible and "
        f"nothing here should be read as an expected value.",
    ]
    if published:
        counterfactual.append(
            f"At the published list rate of ${published.usd_per_gpu_hour:.2f}/GPU-hr "
            f"({published.rate_source}) the same delay is {usd(published.usd)}. That is a "
            f"posted ask, not a clearing price, and it is shown separately for exactly that "
            f"reason."
        )
    if contracted:
        counterfactual.append(
            f"At the rate implied by the {contract.name} "
            f"({usd(contract.usd_per_mw_year)}/MW-year), the same delay is "
            f"{usd(contracted.usd)}. That is the conservative mark and it is the one to quote "
            f"to a developer."
        )

    spread_drivers = [
        f"Rate: ${rate_low:.2f} to ${rate_high:.2f}/GPU-hr. This is the widest driver. "
        f"It is the observed dispersion of the offer book today, not a forecast band."
        if rate is None
        else "Rate: pinned by the caller, contributes nothing to the spread.",
        f"Utilisation: {util_low:.0%} to {util_high:.0%}. Whether the fleet is pre-sold or "
        f"merchant."
        if utilisation is None
        else "Utilisation: pinned by the caller, contributes nothing to the spread.",
        f"Accelerator count: {count_low:,} to {count_high:,}. Design margin against sustained "
        f"draw, a ±{(count_high - count_low) / (2 * count_likely) * 100:.0f}% band.",
    ]

    return DelayValuation(
        gpu_class=gpu_class,
        months_delayed=months_delayed,
        it_load_mw=mw_it_load,
        blocked_it_load_mw=blocked_mw,
        accelerators_likely=count_likely,
        low=low,
        likely=likely,
        high=high,
        chain=chain,
        assumptions=assumptions,
        counterfactual=counterfactual,
        spread_drivers=spread_drivers,
        rate_basis=rate_basis,
        rate_fetched=rate_fetched,
        rate_is_stale=rate_stale,
        published_list_case=published,
        contracted_lease_case=contracted,
        cross_check=cross_check,
        notes=notes,
    )


def value_of_one_month(
    mw_it_load: float,
    gpu_class: str = DEFAULT_GPU_CLASS,
    utilisation: float | None = None,
    rate: float | None = None,
    **kwargs: Any,
) -> dict:
    """What one month of permit delay is worth at this site.

    The inverse of `price_the_delay`, and the more useful of the two for a
    developer. The total loss depends on how long the delay turns out to be,
    which nobody knows on day one. The monthly number does not, and it is what
    a screening budget is measured against.
    """
    valuation = price_the_delay(
        mw_it_load, 1.0, gpu_class, utilisation, rate, **kwargs
    )
    return {
        "gpu_class": gpu_class,
        "blocked_it_load_mw": round(valuation.blocked_it_load_mw, 1),
        "accelerators": valuation.accelerators_likely,
        "usd_per_month": {
            "low": round(valuation.low.usd, 0),
            "likely": round(valuation.likely.usd, 0),
            "high": round(valuation.high.usd, 0),
        },
        "usd_per_day": {
            "low": round(valuation.low.usd / 30.4, 0),
            "likely": round(valuation.likely.usd / 30.4, 0),
            "high": round(valuation.high.usd / 30.4, 0),
        },
        "rate_basis": valuation.rate_basis,
        "basis": (
            "Same counterfactual as the full valuation: blocked capacity sold at spot at the "
            "stated utilisation for the month. Opportunity cost, not cash."
        ),
    }


# --------------------------------------------------------------------------
# Cost of being wrong
# --------------------------------------------------------------------------

#: Direct capital a developer has burned by the time a permit problem surfaces
#: at month nine: land option payments, front-end engineering, legal and agency
#: pre-application work. The brief's figure is "tens of millions" and that is
#: the range carried here rather than a false precision.
SUNK_CAPITAL_USD = (10.0e6, 30.0e6, 60.0e6)
SUNK_CAPITAL_BASIS = (
    "docs/build-brief.md §4, buyer 2: one wrong site is tens of millions in options, "
    "engineering and legal, plus 18 to 36 months. The dollar range is carried as a range "
    "because the brief states it as one."
)

#: Months to re-site and restart once the problem is known. Same source.
RESTART_MONTHS = (18.0, 27.0, 36.0)


def cost_of_being_wrong(
    mw_it_load: float,
    discovery_month: float = 9.0,
    gpu_class: str = DEFAULT_GPU_CLASS,
    screen_cost_usd: float = 25_000.0,
    sunk_capital_usd: tuple[float, float, float] = SUNK_CAPITAL_USD,
    restart_months: tuple[float, float, float] = RESTART_MONTHS,
    **kwargs: Any,
) -> dict:
    """What it costs to find the permit problem at month nine instead of before
    optioning the land.

    Two components and they are not the same size. The direct capital is the one
    a developer thinks about: options, engineering, legal, all unrecoverable. The
    schedule is the one that actually matters: the months already burned plus the
    months to re-site, valued at the site's monthly opportunity cost.

    Everything here is under the same counterfactual as `price_the_delay`, so the
    same caveats apply — it is opportunity cost at today's spot rate under a
    generous assumption about who would have bought the capacity.
    """
    month = value_of_one_month(mw_it_load, gpu_class, **kwargs)
    per_month = month["usd_per_month"]

    sunk_low, sunk_likely, sunk_high = sunk_capital_usd
    restart_low, restart_likely, restart_high = restart_months

    months_low = discovery_month + restart_low
    months_likely = discovery_month + restart_likely
    months_high = discovery_month + restart_high

    schedule_low = months_low * per_month["low"]
    schedule_likely = months_likely * per_month["likely"]
    schedule_high = months_high * per_month["high"]

    total_low = sunk_low + schedule_low
    total_likely = sunk_likely + schedule_likely
    total_high = sunk_high + schedule_high

    return {
        "discovery_month": discovery_month,
        "months_lost": {
            "low": round(months_low, 1),
            "likely": round(months_likely, 1),
            "high": round(months_high, 1),
        },
        "sunk_capital_usd": {
            "low": round(sunk_low, 0),
            "likely": round(sunk_likely, 0),
            "high": round(sunk_high, 0),
        },
        "schedule_opportunity_cost_usd": {
            "low": round(schedule_low, 0),
            "likely": round(schedule_likely, 0),
            "high": round(schedule_high, 0),
        },
        "total_usd": {
            "low": round(total_low, 0),
            "likely": round(total_likely, 0),
            "high": round(total_high, 0),
        },
        "screen_cost_usd": screen_cost_usd,
        "screen_ratio": round(total_likely / screen_cost_usd, 0) if screen_cost_usd else None,
        "value_of_one_month_usd": per_month,
        "basis": {
            "sunk_capital": SUNK_CAPITAL_BASIS,
            "restart_months": f"{restart_low:.0f} to {restart_high:.0f} months to re-site and "
            f"restart, from the same brief figure.",
            "discovery_month": f"Problem surfaces at month {discovery_month:.0f}, which is when "
            f"the agency's completeness review or the first request for additional information "
            f"lands. Those months are already spent when it does.",
            "rate": month["rate_basis"],
        },
        "reading": (
            f"The sunk capital is {usd(sunk_likely)}. The schedule is "
            f"{usd(schedule_likely)}. The capital is the number a developer writes off and the "
            f"schedule is the number that decides whether the project still makes sense, and "
            f"they differ by roughly {schedule_likely / sunk_likely:,.0f}x. A screen run before "
            f"the land is optioned costs {usd(screen_cost_usd)}."
        ),
        "caveat": (
            "The sunk capital is destroyed. The schedule cost is deferred revenue, not "
            "destroyed revenue — the project still gets built somewhere, later, and this "
            "figure is undiscounted. Read it as the value of the option to start earlier, "
            "which is what the screen actually sells."
        ),
    }


# --------------------------------------------------------------------------
# Bridge to an assessment
# --------------------------------------------------------------------------


def _best_config_option(assessment: Any) -> Any | None:
    configs = getattr(assessment, "configs", None)
    options = getattr(configs, "options", None) if configs else None
    if not options:
        return None
    improving = [o for o in options if getattr(o, "months_saved", 0) > 1]
    return max(improving, key=lambda o: o.months_saved) if improving else None


def value_for_assessment(
    assessment: Any,
    it_load_mw: float | None = None,
    gpu_class: str = DEFAULT_GPU_CLASS,
    utilisation: float | None = None,
    rate: float | None = None,
    pue: float | None = None,
    plant_share_of_it_load: float = 1.0,
    months_delayed: float | None = None,
    rates: dict | None = None,
) -> DelayValuation | None:
    """Price the delay this assessment found. Returns None when there is nothing
    to price — no pathway, no announced date, or no slack figure.

    The delay defaults to the negative slack against the announced energization
    date, not the pathway duration. A project with a realistic schedule has a
    long pathway and no delay, and charging it for the whole permit timeline
    would be wrong.

    `assessment` is duck-typed on purpose: it needs `.project`, `.pathway`,
    `.probability`, and optionally `.site`, `.configs` and `.alternate`. The
    report passes a real ProjectAssessment; the tool executor passes the pieces
    it has mid-run.
    """
    probability = getattr(assessment, "probability", None)
    pathway = getattr(assessment, "pathway", None)
    if pathway is None:
        return None
    if months_delayed is None:
        if probability is None:
            return None
        slack = getattr(probability, "slack_months", None)
        if slack is None:
            return None
        months_delayed = max(0.0, -float(slack))
    months_delayed = max(0.0, float(months_delayed))

    config = assessment.project.config
    plant_mw = float(config.mw)
    used_pue = pue if pue is not None else DEFAULT_PUE
    derived = it_load_mw is None
    load = it_load_mw if it_load_mw is not None else plant_mw / used_pue

    site = getattr(assessment, "site", None)
    # The double-counting guard, read off the project rather than assumed. A
    # grid-tied campus can serve part of its load without this plant, so the air
    # permit does not block all of it, and the valuation says so instead of
    # quietly claiming the whole thing.
    sole = not bool(getattr(assessment.project, "grid_tied", False))
    try:
        valuation = price_the_delay(
            mw_it_load=load,
            months_delayed=months_delayed,
            gpu_class=gpu_class,
            utilisation=utilisation,
            rate=rate,
            pue=used_pue,
            plant_mw=plant_mw if not derived else None,
            plant_share_of_it_load=plant_share_of_it_load,
            sole_power_source=sole,
            rates=rates,
            contract=reference_contract_for(
                getattr(site, "county", None),
                getattr(site, "state", None),
            ),
            it_load_derived=derived,
        )
    except (ValueError, KeyError):
        return None

    if derived:
        valuation.notes.insert(
            0,
            f"IT load was not stated, so it is derived: {plant_mw:,.0f} MW of generation at a "
            f"PUE of {used_pue:.2f} serves {load:,.0f} MW of IT load. Pass the real IT load if "
            f"you have it — this figure scales every dollar below.",
        )

    # What the search already found. This is the part a developer can act on,
    # and it is why the loss is a cost of not looking rather than a fact.
    per_month = valuation.per_month_likely
    option = _best_config_option(assessment)
    if option is not None and per_month:
        recoverable = min(option.months_saved, months_delayed) * per_month
        valuation.mitigations.append(
            Mitigation(
                route="config",
                label=option.label,
                months_saved=float(option.months_saved),
                usd_recovered=recoverable,
                note=f"Config search at this parcel: {option.label} lands on "
                f"{option.pathway.label} and saves {option.months_saved:.0f} months. "
                f"{option.cost_note}",
            )
        )

    alternate = getattr(assessment, "alternate", None)
    best = getattr(alternate, "best", None) if alternate else None
    if best is not None and getattr(best, "months_saved", 0) > 1 and per_month:
        recoverable = min(best.months_saved, months_delayed) * per_month
        valuation.mitigations.append(
            Mitigation(
                route="site",
                label=f"{best.county} County, {best.state}",
                months_saved=float(best.months_saved),
                usd_recovered=recoverable,
                note=f"Alternate site search: {best.distance_miles:.0f} miles away, "
                f"{best.pathway.label}, saves {best.months_saved:.0f} months. Land, fiber and "
                f"interconnection at the alternate parcel are not priced here.",
            )
        )

    if valuation.mitigations:
        best_route = max(valuation.mitigations, key=lambda m: m.usd_recovered)
        valuation.notes.append(
            f"The search already found a route that recovers {usd(best_route.usd_recovered)} of "
            f"this: {best_route.label}. The loss above is the cost of not looking, not an "
            f"inevitability."
        )

    return valuation


# --------------------------------------------------------------------------


def main() -> None:  # pragma: no cover - manual check
    """`python -m agent.economics` runs the Cumberland NJ case end to end."""
    import argparse

    parser = argparse.ArgumentParser(description="Price a permit delay in dollars.")
    parser.add_argument("--it-load", type=float, default=300.0, help="MW of IT load")
    parser.add_argument("--plant-mw", type=float, default=400.0, help="MW of generation")
    parser.add_argument("--months", type=float, default=53.1, help="months of delay")
    parser.add_argument("--gpu", default=DEFAULT_GPU_CLASS)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    table = spot_rates([args.gpu], allow_network=not args.offline)
    valuation = price_the_delay(
        mw_it_load=args.it_load,
        months_delayed=args.months,
        gpu_class=args.gpu,
        plant_mw=args.plant_mw,
        rates=table,
        contract=REFERENCE_CONTRACTS[0],
    )

    print(valuation.headline())
    print()
    print("Arithmetic")
    for step in valuation.chain:
        print(f"  {step}")
    print()
    print("Assumptions")
    for assumption in valuation.assumptions:
        print(f"  {assumption.line()}")
    print()
    print("Spread")
    for driver in valuation.spread_drivers:
        print(f"  {driver}")
    print()
    print("Counterfactual")
    for line in valuation.counterfactual:
        print(f"  {line}")
    if valuation.cross_check:
        print()
        print("Cross-check")
        check = valuation.cross_check
        print(f"  {check['contract']}: {usd(check['contract_usd'])} over "
              f"{check['contract_years']:.0f} years for {check['contract_it_load_mw']:.0f} MW "
              f"= {usd(check['contract_usd_per_mw_year'])}/MW-year")
        print(f"  This valuation implies {usd(check['implied_usd_per_mw_year_likely'])}/MW-year "
              f"({check['ratio_likely']:.2f}x)")
        print(f"  {check['verdict']}")
        print(f"  {check['high_case_note']}")
    print()
    print("Cost of being wrong")
    wrong = cost_of_being_wrong(args.it_load, rates=table, plant_mw=args.plant_mw)
    print(f"  months lost: {wrong['months_lost']['low']:.0f}-{wrong['months_lost']['high']:.0f}")
    print(f"  sunk capital: {usd(wrong['sunk_capital_usd']['likely'])}")
    print(f"  schedule:     {usd(wrong['schedule_opportunity_cost_usd']['likely'])}")
    print(f"  total:        {usd(wrong['total_usd']['likely'])}")
    print(f"  {wrong['reading']}")


if __name__ == "__main__":  # pragma: no cover
    main()
