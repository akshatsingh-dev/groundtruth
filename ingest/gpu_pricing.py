"""Spot and list pricing for rented GPU compute, $/GPU-hour.

This is the price side of the compute-economics layer. `agent/economics.py`
turns megawatts into accelerators; this module says what an accelerator-hour is
worth today, and where that number came from.

Two kinds of price, and they are not the same number:

  marketplace_spot   What renters are actually paying right now on a market
                     where supply competes. Moves daily. Thin at the top of the
                     book for the newest silicon.
  published_list     A cloud's advertised on-demand rate card. Sticky for weeks,
                     usually 30-80% above the marketplace clearing price, and it
                     is a posted ask rather than a transaction.

They are kept separate everywhere in this module and never averaged into one
figure. A valuation quoted at a list rate is quoting an ask nobody had to accept.

Sources, all checked on 5 Aug 2026, all answering without an account:

  Vast.ai       GET https://console.vast.ai/api/v0/bundles/?q=<json>
                No auth. Returns the live offer book. `dph_total` is dollars per
                hour for the whole bundle, so per-GPU is dph_total/num_gpus. The
                endpoint pages at 64 offers, so a class with more listings than
                that comes back truncated and we say so rather than quietly
                reporting a biased median.
  SF Compute    GET https://sfcompute.com/prices
                No auth. The page embeds a 30-day daily series of cleared
                cluster prices per hardware type. This is the best single number
                in here: it is a traded average across a real order book for
                contiguous clusters, which is the thing a 300 MW campus would
                actually be selling. Series entries of 0 mean no trades, not
                free compute, and are dropped.
  RunPod        POST https://api.runpod.io/graphql
                No auth for the `gpuTypes` query. Returns `securePrice` and
                `communityPrice` per GPU type. Both are published rate card,
                not a clearing price.
  Lambda        GET https://lambda.ai/pricing
                No auth. HTML, so the parse is the fragile part; it is wrapped
                and a failure degrades to "source unavailable" rather than
                taking the run down. Published on-demand rate card.

Checked and rejected:

  Lambda API    https://cloud.lambdalabs.com/api/v1/instance-types returns 401.
                Needs a paid account, so the published web rate card is the only
                keyless route to their numbers.
  Together      Rate card is per-token for inference endpoints. Different unit,
                not comparable to a GPU-hour, so it is not in here.
  Fireworks     Same. Per-token.

Everything goes through `providers.cache.ResponseCache` at a one-day TTL. Spot
rates move day to day, not minute to minute, and re-running the screen five
times in an afternoon should not produce five different valuations.

With no network the module falls back to a dated table captured from these same
endpoints on 5 Aug 2026. Every fallback figure carries that capture date and is
flagged `basis="fallback"` so nothing downstream can present it as live.
"""

from __future__ import annotations

import json
import os
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from providers.cache import ResponseCache

# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

#: A price derived from transactions or live competing offers.
MARKETPLACE_SPOT = "marketplace_spot"
#: A price a vendor advertises. A posted ask, not a clearing price.
PUBLISHED_LIST = "published_list"

#: Cache TTL. Rates move daily, so a screen re-run this afternoon reads the same
#: book it read this morning. Anything shorter buys noise; anything longer buys
#: a stale mark on a market that has moved 11% in the last month.
CACHE_TTL_DAYS = 1.0

_VAST_URL = "https://console.vast.ai/api/v0/bundles/"
_SFC_URL = "https://sfcompute.com/prices"
_RUNPOD_URL = "https://api.runpod.io/graphql"
_LAMBDA_URL = "https://lambda.ai/pricing"

#: The public Vast endpoint returns at most this many offers per query. A class
#: that hits the cap is a truncated sample and its median is biased toward the
#: sort order, which is ascending price. Flagged, not hidden.
_VAST_PAGE_CAP = 64

_TIMEOUT = httpx.Timeout(connect=6.0, read=15.0, write=10.0, pool=6.0)
_UA = "deliverable/1.0 (air permit screening; gpu price reference)"


# --------------------------------------------------------------------------
# GPU classes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GpuClass:
    """One accelerator class and how each vendor spells it.

    `board_watts` is the accelerator's own TDP. `node_watts` is the honest
    number for economics: total IT-side draw attributable to one accelerator
    inside a real server, so host CPU, DRAM, NICs, NVSwitch and power supply
    losses are already in it. It excludes cooling and facility overhead, which
    is what PUE covers, and double counting the two is the easiest way to get
    this arithmetic wrong.
    """

    name: str
    board_watts: float
    node_watts: float
    node_basis: str
    vast_name: str | None = None
    vast_min_gpu_ram_mb: int | None = None
    runpod_display: str | None = None
    lambda_label: str | None = None
    sfc_key: str | None = None


GPU_CLASSES: tuple[GpuClass, ...] = (
    GpuClass(
        name="H100 SXM",
        board_watts=700.0,
        node_watts=1275.0,
        node_basis="NVIDIA DGX H100 datasheet: 10.2 kW maximum system power for 8 GPUs "
        "= 1,275 W per accelerator, host and NVSwitch included.",
        vast_name="H100 SXM",
        runpod_display="H100 SXM",
        lambda_label="NVIDIA H100 SXM",
        sfc_key="H100",
    ),
    GpuClass(
        name="H200 SXM",
        board_watts=700.0,
        node_watts=1275.0,
        node_basis="HGX H200 uses the same 8-GPU baseboard and 700 W per-module envelope "
        "as H100, so the per-accelerator node figure is carried across.",
        vast_name="H200",
        runpod_display="H200 SXM",
        sfc_key="H200",
    ),
    GpuClass(
        name="A100 SXM 80GB",
        board_watts=400.0,
        node_watts=812.0,
        node_basis="NVIDIA DGX A100 datasheet: 6.5 kW maximum system power for 8 GPUs "
        "= 812 W per accelerator.",
        vast_name="A100 SXM4",
        vast_min_gpu_ram_mb=70000,
        runpod_display="A100 SXM",
        lambda_label="NVIDIA A100 SXM",
    ),
    GpuClass(
        name="B200",
        board_watts=1000.0,
        node_watts=1790.0,
        node_basis="NVIDIA DGX B200: ~14.3 kW system power for 8 GPUs = 1,790 W per "
        "accelerator.",
        vast_name="B200",
        runpod_display="B200",
        lambda_label="NVIDIA B200 SXM6",
        sfc_key="B200",
    ),
    GpuClass(
        name="H100 NVL",
        board_watts=400.0,
        node_watts=700.0,
        node_basis="PCIe card pair at 350-400 W each in a standard 2U/4U host; host share "
        "is larger per accelerator than on an SXM baseboard.",
        vast_name="H100 NVL",
        runpod_display="H100 NVL",
    ),
    GpuClass(
        name="L40S",
        board_watts=350.0,
        node_watts=600.0,
        node_basis="350 W PCIe card, 4-8 to a 2U host; host and PSU share allocated per card.",
        vast_name="L40S",
        runpod_display="L40S",
    ),
)

CLASS_BY_NAME: dict[str, GpuClass] = {c.name: c for c in GPU_CLASSES}

#: The unit of account. Everything the market quotes, it quotes relative to this.
DEFAULT_GPU_CLASS = "H100 SXM"


# --------------------------------------------------------------------------
# Quotes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RateQuote:
    """One price for one GPU class from one source, with its derivation attached.

    `low` and `high` are the dispersion the source itself reports — the 25th and
    75th percentile of an offer book, or the day's low and high on a traded
    index. They are not a forecast band.
    """

    gpu_class: str
    usd_per_gpu_hour: float
    kind: str
    source: str
    url: str
    fetched: str
    derivation: str
    sample_size: int | None = None
    low: float | None = None
    high: float | None = None
    truncated: bool = False
    stale: bool = False
    captured: str | None = None

    def cited(self) -> str:
        band = (
            f" ({self.low:.2f}-{self.high:.2f})"
            if self.low is not None and self.high is not None
            else ""
        )
        age = f", captured {self.captured}" if self.stale else f", fetched {self.fetched}"
        return (
            f"{self.gpu_class} ${self.usd_per_gpu_hour:.2f}/GPU-hr{band} "
            f"[{self.kind}, {self.source}{age}; {self.derivation}]"
        )

    def to_dict(self) -> dict:
        return {
            "gpu_class": self.gpu_class,
            "usd_per_gpu_hour": round(self.usd_per_gpu_hour, 4),
            "kind": self.kind,
            "source": self.source,
            "url": self.url,
            "fetched": self.fetched,
            "derivation": self.derivation,
            "sample_size": self.sample_size,
            "low": round(self.low, 4) if self.low is not None else None,
            "high": round(self.high, 4) if self.high is not None else None,
            "sample_truncated": self.truncated,
            "stale": self.stale,
            "captured": self.captured,
        }


@dataclass
class SourceStatus:
    """Whether a source answered, and whether it needed an account to do it."""

    name: str
    url: str
    auth_required: bool
    ok: bool
    note: str
    quotes: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "auth_required": self.auth_required,
            "ok": self.ok,
            "note": self.note,
            "quotes": self.quotes,
        }


# --------------------------------------------------------------------------
# Fallback table
# --------------------------------------------------------------------------

#: Captured 5 Aug 2026 from the endpoints named in the module docstring, by
#: running this module. Used only when the network is unavailable. Every entry
#: comes back flagged stale with this date attached, so a keyless run reads as
#: obviously dated rather than quietly wrong.
FALLBACK_CAPTURED = "2026-08-05"

_FALLBACK: tuple[dict, ...] = (
    # marketplace spot
    dict(gpu_class="H100 SXM", usd=2.27, kind=MARKETPLACE_SPOT, source="SF Compute",
         url=_SFC_URL, low=2.19, high=2.33, n=None,
         derivation="cleared cluster price index, daily average for 2026-08-05"),
    dict(gpu_class="H100 SXM", usd=2.52, kind=MARKETPLACE_SPOT, source="Vast.ai",
         url=_VAST_URL, low=1.73, high=3.07, n=31,
         derivation="median of 31 rentable on-demand offers, dph_total/num_gpus"),
    dict(gpu_class="H200 SXM", usd=4.08, kind=MARKETPLACE_SPOT, source="Vast.ai",
         url=_VAST_URL, low=3.94, high=4.34, n=10,
         derivation="median of 10 rentable on-demand offers, dph_total/num_gpus"),
    dict(gpu_class="A100 SXM 80GB", usd=0.83, kind=MARKETPLACE_SPOT, source="Vast.ai",
         url=_VAST_URL, low=0.67, high=1.07, n=56,
         derivation="median of 56 rentable on-demand offers, dph_total/num_gpus"),
    dict(gpu_class="B200", usd=5.94, kind=MARKETPLACE_SPOT, source="Vast.ai",
         url=_VAST_URL, low=5.63, high=6.25, n=27,
         derivation="median of 27 rentable on-demand offers, dph_total/num_gpus"),
    dict(gpu_class="H100 NVL", usd=2.54, kind=MARKETPLACE_SPOT, source="Vast.ai",
         url=_VAST_URL, low=2.00, high=2.80, n=8,
         derivation="median of 8 rentable on-demand offers, dph_total/num_gpus"),
    dict(gpu_class="L40S", usd=0.60, kind=MARKETPLACE_SPOT, source="Vast.ai",
         url=_VAST_URL, low=0.47, high=0.80, n=27,
         derivation="median of 27 rentable on-demand offers, dph_total/num_gpus"),
    # published list
    dict(gpu_class="H100 SXM", usd=3.29, kind=PUBLISHED_LIST, source="RunPod Secure Cloud",
         url=_RUNPOD_URL, low=2.69, high=3.29, n=None,
         derivation="published rate card; secure 3.29, community 2.69"),
    dict(gpu_class="H100 SXM", usd=3.99, kind=PUBLISHED_LIST, source="Lambda on-demand",
         url=_LAMBDA_URL, low=3.99, high=4.29, n=None,
         derivation="published rate card, 8x H100 SXM instance, per GPU per hour"),
    dict(gpu_class="H200 SXM", usd=4.59, kind=PUBLISHED_LIST, source="RunPod Secure Cloud",
         url=_RUNPOD_URL, low=3.59, high=4.59, n=None,
         derivation="published rate card; secure 4.59, community 3.59"),
    dict(gpu_class="A100 SXM 80GB", usd=1.59, kind=PUBLISHED_LIST, source="RunPod Secure Cloud",
         url=_RUNPOD_URL, low=1.39, high=1.59, n=None,
         derivation="published rate card; secure 1.59, community 1.39"),
    dict(gpu_class="A100 SXM 80GB", usd=2.79, kind=PUBLISHED_LIST, source="Lambda on-demand",
         url=_LAMBDA_URL, low=2.79, high=2.79, n=None,
         derivation="published rate card, 8x A100 SXM 80GB instance, per GPU per hour"),
    dict(gpu_class="B200", usd=6.79, kind=PUBLISHED_LIST, source="RunPod Secure Cloud",
         url=_RUNPOD_URL, low=5.98, high=6.79, n=None,
         derivation="published rate card; secure 6.79, community 5.98"),
    dict(gpu_class="H100 NVL", usd=3.19, kind=PUBLISHED_LIST, source="RunPod Secure Cloud",
         url=_RUNPOD_URL, low=2.59, high=3.19, n=None,
         derivation="published rate card; secure 3.19, community 2.59"),
    dict(gpu_class="L40S", usd=0.99, kind=PUBLISHED_LIST, source="RunPod Secure Cloud",
         url=_RUNPOD_URL, low=0.79, high=0.99, n=None,
         derivation="published rate card; secure 0.99, community 0.79"),
)

#: What the traded H100 index did over the 30 days ending on the capture date.
#: Kept so the offline path can still say something true about volatility instead
#: of implying today's mark is a constant.
FALLBACK_TREND = {
    "gpu_class": "H100 SXM",
    "source": "SF Compute cleared price index",
    "window_days": 30,
    "start_usd": 2.04,
    "end_usd": 2.27,
    "captured": FALLBACK_CAPTURED,
}


def _fallback_quotes() -> list[RateQuote]:
    return [
        RateQuote(
            gpu_class=row["gpu_class"],
            usd_per_gpu_hour=row["usd"],
            kind=row["kind"],
            source=row["source"],
            url=row["url"],
            fetched=FALLBACK_CAPTURED,
            derivation=row["derivation"],
            sample_size=row["n"],
            low=row["low"],
            high=row["high"],
            stale=True,
            captured=FALLBACK_CAPTURED,
        )
        for row in _FALLBACK
    ]


# --------------------------------------------------------------------------
# HTTP with cache
# --------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def offline() -> bool:
    """True when the caller has asked us not to touch the network."""
    return os.getenv("GPU_PRICING_OFFLINE", "").strip().lower() in ("1", "true", "yes")


class _Fetcher:
    """GET/POST through the shared response cache, one day TTL, never raises.

    A pricing source that is down is a missing quote and a note in the output,
    not an exception. The rest of the screen does not depend on it.
    """

    def __init__(self, cache: ResponseCache | None, ttl_days: float, allow_network: bool):
        self.cache = cache
        self.ttl_days = ttl_days
        self.allow_network = allow_network
        self.errors: dict[str, str] = {}
        #: endpoint -> when the bytes behind it were actually retrieved. A cache
        #: hit keeps the original fetch time. Stamping a replay with now() would
        #: make a day-old mark look like a fresh one.
        self.fetched_at: dict[str, str] = {}
        self.from_cache: dict[str, bool] = {}
        #: Transport failures so far. On a machine with no network every request
        #: would otherwise burn the full connect timeout, and a screen would sit
        #: there for half a minute to learn something the first failure already
        #: proved. Two strikes and we stop dialling.
        self._transport_failures = 0

    @property
    def dialling(self) -> bool:
        return self.allow_network and self._transport_failures < 2

    def _record(self, endpoint: str, exc: Exception) -> None:
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            self._transport_failures += 1
        self.errors[endpoint] = f"{exc.__class__.__name__}: {exc}"

    def _offline_reason(self) -> str:
        if not self.allow_network:
            return "network disabled"
        return "no network — stopped dialling after two transport failures"

    def stamp(self, endpoint: str) -> str:
        return self.fetched_at.get(endpoint, _now())

    def _cached(self, endpoint: str, params: Any) -> Any | None:
        if self.cache is None:
            return None
        hit = self.cache.get(endpoint, params, max_age_days=self.ttl_days)
        if hit is None or not hit.ok:
            return None
        self.fetched_at[endpoint] = hit.fetched
        self.from_cache[endpoint] = True
        return hit.body

    def _store(self, endpoint: str, params: Any, status: int, body: Any) -> None:
        self.fetched_at[endpoint] = _now()
        self.from_cache[endpoint] = False
        if self.cache is not None:
            self.cache.set(endpoint, params, status, body, credits=0.0)

    def get_json(self, endpoint: str, url: str, params: dict) -> Any | None:
        body = self._cached(endpoint, params)
        if body is not None:
            return body
        if not self.dialling:
            self.errors[endpoint] = self._offline_reason()
            return None
        try:
            response = httpx.get(
                url, params=params, timeout=_TIMEOUT, headers={"User-Agent": _UA},
                follow_redirects=True,
            )
            if response.status_code >= 400:
                self.errors[endpoint] = f"HTTP {response.status_code}"
                return None
            body = response.json()
        except Exception as exc:
            self._record(endpoint, exc)
            return None
        self._store(endpoint, params, 200, body)
        return body

    def get_text(self, endpoint: str, url: str) -> str | None:
        body = self._cached(endpoint, {"url": url})
        if body is not None:
            return body.get("text") if isinstance(body, dict) else None
        if not self.dialling:
            self.errors[endpoint] = self._offline_reason()
            return None
        try:
            response = httpx.get(
                url, timeout=_TIMEOUT, headers={"User-Agent": _UA}, follow_redirects=True
            )
            if response.status_code >= 400:
                self.errors[endpoint] = f"HTTP {response.status_code}"
                return None
            text = response.text
        except Exception as exc:
            self._record(endpoint, exc)
            return None
        self._store(endpoint, {"url": url}, 200, {"text": text})
        return text

    def post_json(self, endpoint: str, url: str, payload: dict) -> Any | None:
        body = self._cached(endpoint, payload)
        if body is not None:
            return body
        if not self.dialling:
            self.errors[endpoint] = self._offline_reason()
            return None
        try:
            response = httpx.post(
                url, json=payload, timeout=_TIMEOUT,
                headers={"User-Agent": _UA, "Content-Type": "application/json"},
            )
            if response.status_code >= 400:
                self.errors[endpoint] = f"HTTP {response.status_code}"
                return None
            body = response.json()
        except Exception as exc:
            self._record(endpoint, exc)
            return None
        self._store(endpoint, payload, 200, body)
        return body


# --------------------------------------------------------------------------
# Vast.ai — marketplace spot
# --------------------------------------------------------------------------


def _percentiles(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0], ordered[0], ordered[0]
    p25 = ordered[max(0, len(ordered) // 4)]
    p75 = ordered[min(len(ordered) - 1, (3 * len(ordered)) // 4)]
    return p25, statistics.median(ordered), p75


def _vast_quotes(fetch: _Fetcher, classes: Iterable[GpuClass]) -> list[RateQuote]:
    """Median per-GPU ask across the live on-demand offer book, per class.

    On-demand only. Vast also runs an interruptible bid market that clears
    lower, but a data center campus sells uninterrupted capacity, so the bid
    book is the wrong comparison and is excluded rather than blended in.
    """
    out: list[RateQuote] = []
    for spec in classes:
        if not spec.vast_name:
            continue
        query = {
            "gpu_name": {"eq": spec.vast_name},
            "rentable": {"eq": True},
            "type": "on-demand",
            "order": [["dph_total", "asc"]],
            "limit": 500,
        }
        endpoint = f"gpu_pricing:vast:{spec.name}"
        body = fetch.get_json(endpoint, _VAST_URL, {"q": json.dumps(query)})
        if not isinstance(body, dict):
            continue
        offers = body.get("offers") or []
        prices: list[float] = []
        for offer in offers:
            try:
                num = float(offer.get("num_gpus") or 0)
                total = float(offer.get("dph_total"))
            except (TypeError, ValueError):
                continue
            if num < 1 or total <= 0:
                continue
            if spec.vast_min_gpu_ram_mb and float(offer.get("gpu_ram") or 0) < spec.vast_min_gpu_ram_mb:
                continue
            prices.append(total / num)
        if not prices:
            continue
        p25, median, p75 = _percentiles(prices)
        truncated = len(offers) >= _VAST_PAGE_CAP
        derivation = (
            f"median of {len(prices)} rentable on-demand offers, dph_total/num_gpus"
            + (
                "; the endpoint paged out at 64 offers sorted cheapest-first, so this "
                "sample is the low end of the book and the median is biased down"
                if truncated
                else ""
            )
            + (
                f"; filtered to offers with >= {spec.vast_min_gpu_ram_mb / 1000:.0f} GB "
                f"of GPU memory to separate this class from its smaller sibling"
                if spec.vast_min_gpu_ram_mb
                else ""
            )
        )
        out.append(
            RateQuote(
                gpu_class=spec.name,
                usd_per_gpu_hour=median,
                kind=MARKETPLACE_SPOT,
                source="Vast.ai",
                url=_VAST_URL,
                fetched=fetch.stamp(endpoint),
                derivation=derivation,
                sample_size=len(prices),
                low=p25,
                high=p75,
                truncated=truncated,
            )
        )
    return out


# --------------------------------------------------------------------------
# SF Compute — traded cluster index
# --------------------------------------------------------------------------

_SFC_BLOCK = re.compile(r'"pricesByHardwareType"\s*:\s*\{')


def _sfc_payload(text: str) -> dict | None:
    """Pull the embedded price series out of the page.

    The page is a React server-component payload with the JSON escaped inside a
    string literal, so this unescapes first and then brace-matches from the key.
    Brace matching rather than a regex for the whole object because the series
    is nested and a greedy match would swallow the rest of the document.
    """
    unescaped = text.replace('\\"', '"').replace("\\\\", "\\")
    match = _SFC_BLOCK.search(unescaped)
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    for i in range(start, len(unescaped)):
        ch = unescaped[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = unescaped[start : i + 1]
                # Dates arrive as "$D2026-08-05T..." markers; they are strings
                # already, so nothing to strip for json.loads.
                try:
                    return json.loads(blob)
                except ValueError:
                    return None
    return None


def _sfc_quotes(fetch: _Fetcher, classes: Iterable[GpuClass]) -> tuple[list[RateQuote], dict | None]:
    text = fetch.get_text("gpu_pricing:sfcompute", _SFC_URL)
    if not text:
        return [], None
    payload = _sfc_payload(text)
    if not payload:
        fetch.errors["gpu_pricing:sfcompute"] = "price series not found in page"
        return [], None

    out: list[RateQuote] = []
    trend: dict | None = None
    for spec in classes:
        series = payload.get(spec.sfc_key or "") or []
        # avg == 0 means the book did not trade that day. It is not a price.
        traded = [row for row in series if isinstance(row, dict) and (row.get("avg") or 0) > 0]
        if not traded:
            continue
        latest = traded[0]
        date_label = str(latest.get("date", "")).lstrip("$D")[:10]
        out.append(
            RateQuote(
                gpu_class=spec.name,
                usd_per_gpu_hour=float(latest["avg"]),
                kind=MARKETPLACE_SPOT,
                source="SF Compute",
                url=_SFC_URL,
                fetched=fetch.stamp("gpu_pricing:sfcompute"),
                derivation=f"cleared cluster price index, daily average for {date_label}",
                sample_size=None,
                low=float(latest.get("bottom") or latest["avg"]),
                high=float(latest.get("top") or latest["avg"]),
            )
        )
        if spec.name == DEFAULT_GPU_CLASS and len(traded) > 1:
            oldest = traded[-1]
            trend = {
                "gpu_class": spec.name,
                "source": "SF Compute cleared price index",
                "window_days": len(traded),
                "start_usd": float(oldest["avg"]),
                "end_usd": float(latest["avg"]),
                "captured": date_label,
            }
    return out, trend


# --------------------------------------------------------------------------
# RunPod — published rate card
# --------------------------------------------------------------------------

_RUNPOD_QUERY = {
    "query": "query GpuTypes { gpuTypes { id displayName memoryInGb securePrice communityPrice } }"
}


def _runpod_quotes(fetch: _Fetcher, classes: Iterable[GpuClass]) -> list[RateQuote]:
    body = fetch.post_json("gpu_pricing:runpod", _RUNPOD_URL, _RUNPOD_QUERY)
    if not isinstance(body, dict):
        return []
    types = ((body.get("data") or {}).get("gpuTypes")) or []
    by_display = {str(t.get("displayName")): t for t in types if isinstance(t, dict)}

    out: list[RateQuote] = []
    for spec in classes:
        row = by_display.get(spec.runpod_display or "")
        if not row:
            continue
        secure = float(row.get("securePrice") or 0)
        community = float(row.get("communityPrice") or 0)
        if secure <= 0 and community <= 0:
            continue
        # Secure is the headline rate card: dedicated hosts in vetted data
        # centers, which is the like-for-like against a campus selling capacity.
        # Community is third-party hardware and reads closer to a marketplace,
        # but it is still a posted rate rather than a clearing price, so it
        # stays on the list side of the wall.
        headline = secure if secure > 0 else community
        out.append(
            RateQuote(
                gpu_class=spec.name,
                usd_per_gpu_hour=headline,
                kind=PUBLISHED_LIST,
                source="RunPod Secure Cloud",
                url=_RUNPOD_URL,
                fetched=fetch.stamp("gpu_pricing:runpod"),
                derivation=(
                    f"published rate card; secure {secure:.2f}, community {community:.2f}"
                    if secure > 0 and community > 0
                    else "published rate card"
                ),
                low=min(x for x in (secure, community) if x > 0),
                high=max(secure, community),
            )
        )
    return out


# --------------------------------------------------------------------------
# Lambda — published rate card, HTML
# --------------------------------------------------------------------------

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S)
_TAG = re.compile(r"<[^>]+>")
_PRICE = re.compile(r"\$(\d+\.\d{2})")


def _lambda_quotes(fetch: _Fetcher, classes: Iterable[GpuClass]) -> list[RateQuote]:
    """Parse the published on-demand table.

    HTML, so this is the brittle source in here. Lambda quotes per GPU per hour
    and the same accelerator appears once per instance size, cheapest on the
    largest instance. We take the cheapest row for a class, which is the 8-GPU
    instance, because that is the configuration a campus would be selling.
    """
    text = fetch.get_text("gpu_pricing:lambda", _LAMBDA_URL)
    if not text:
        return []
    flat = (
        text.replace("\\u003C", "<")
        .replace("\\u003E", ">")
        .replace("\\u0026", "&")
        .replace("\\u002F", "/")
        .replace('\\"', '"')
    )

    seen: dict[str, list[float]] = {}
    for raw_row in _ROW.findall(flat):
        cells = [_TAG.sub("", c).strip() for c in _CELL.findall(raw_row)]
        cells = [c for c in cells if c]
        if len(cells) < 2:
            continue
        label = cells[0]
        prices = [float(m) for cell in cells[1:] for m in _PRICE.findall(cell)]
        if not prices:
            continue
        for spec in classes:
            if not spec.lambda_label or label != spec.lambda_label:
                continue
            # A100 SXM is listed at both 40 GB and 80 GB under one label; the
            # memory column disambiguates and the 40 GB rows are a different
            # class we do not price.
            if spec.vast_min_gpu_ram_mb and len(cells) > 1:
                memory = _first_int(cells[1])
                if memory is not None and memory * 1000 < spec.vast_min_gpu_ram_mb:
                    continue
            seen.setdefault(spec.name, []).extend(prices)

    out: list[RateQuote] = []
    for name, prices in seen.items():
        cheapest = min(prices)
        out.append(
            RateQuote(
                gpu_class=name,
                usd_per_gpu_hour=cheapest,
                kind=PUBLISHED_LIST,
                source="Lambda on-demand",
                url=_LAMBDA_URL,
                fetched=fetch.stamp("gpu_pricing:lambda"),
                derivation="published rate card, per GPU per hour, cheapest listed instance "
                "size for this accelerator (the 8-GPU node)",
                low=cheapest,
                high=max(prices),
            )
        )
    return out


def _first_int(text: str) -> int | None:
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------


def _consolidate(quotes: list[RateQuote], kind: str) -> dict | None:
    """Collapse several sources of the same kind into one figure.

    Median across sources, and the sources are listed. Averaging *within* a kind
    is defensible because the quotes are measuring the same thing; averaging
    across kinds is not, and this function is never called with both.
    """
    subset = [q for q in quotes if q.kind == kind]
    if not subset:
        return None
    values = [q.usd_per_gpu_hour for q in subset]
    lows = [q.low for q in subset if q.low is not None] or values
    highs = [q.high for q in subset if q.high is not None] or values
    return {
        "usd_per_gpu_hour": round(statistics.median(values), 4),
        "low": round(min(lows), 4),
        "high": round(max(highs), 4),
        "kind": kind,
        "sources": [q.source for q in subset],
        "quotes": [q.to_dict() for q in subset],
        "stale": all(q.stale for q in subset),
    }


def spot_rates(
    classes: Iterable[str] | None = None,
    cache: ResponseCache | None = None,
    ttl_days: float = CACHE_TTL_DAYS,
    allow_network: bool = True,
) -> dict:
    """Current $/GPU-hour by class, marketplace spot and published list kept apart.

    Returns a dict shaped for the report and for `agent.economics`:

        {
          "fetched": iso timestamp,
          "basis": "live" | "partial" | "fallback",
          "sources": [ {name, url, auth_required, ok, note, quotes} ],
          "trend": {gpu_class, window_days, start_usd, end_usd} | None,
          "rates": {
              "H100 SXM": {
                  "marketplace_spot": {usd_per_gpu_hour, low, high, sources, quotes},
                  "published_list":   {usd_per_gpu_hour, low, high, sources, quotes},
                  "power": {board_watts, node_watts, node_basis},
              },
              ...
          },
          "notes": [...]
        }

    `basis` is the honesty flag. "live" means every quote came off a live or
    same-day cached fetch. "fallback" means the network was unavailable and
    every number in here is the dated table at the top of this module. "partial"
    means some classes are live and some are not, and the per-quote `stale` flag
    says which.
    """
    wanted = (
        [CLASS_BY_NAME[c] for c in classes if c in CLASS_BY_NAME]
        if classes is not None
        else list(GPU_CLASSES)
    )
    if not wanted:
        wanted = list(GPU_CLASSES)

    allow = allow_network and not offline()
    if cache is None:
        try:
            cache = ResponseCache()
        except Exception:
            cache = None

    fetch = _Fetcher(cache, ttl_days, allow)

    def status(name: str, url: str, got: list, endpoint: str, ok_note: str, fail_note: str) -> SourceStatus:
        note = ok_note if got else fetch.errors.get(endpoint, fail_note)
        if got and fetch.from_cache.get(endpoint):
            note += f"; served from the response cache, fetched {fetch.stamp(endpoint)}"
        return SourceStatus(name, url, False, bool(got), note, len(got))

    quotes: list[RateQuote] = []
    statuses: list[SourceStatus] = []

    vast = _vast_quotes(fetch, wanted)
    quotes.extend(vast)
    statuses.append(
        status(
            "Vast.ai offer book", _VAST_URL, vast, f"gpu_pricing:vast:{wanted[0].name}",
            "live marketplace asks, on-demand only, no account needed",
            "no offers returned",
        )
    )

    sfc, trend = _sfc_quotes(fetch, wanted)
    quotes.extend(sfc)
    statuses.append(
        status(
            "SF Compute price index", _SFC_URL, sfc, "gpu_pricing:sfcompute",
            "cleared cluster prices, 30-day daily series, no account needed",
            "no traded series",
        )
    )

    runpod = _runpod_quotes(fetch, wanted)
    quotes.extend(runpod)
    statuses.append(
        status(
            "RunPod rate card", _RUNPOD_URL, runpod, "gpu_pricing:runpod",
            "published on-demand rate card via the public GraphQL endpoint, no account needed",
            "no gpuTypes returned",
        )
    )

    lam = _lambda_quotes(fetch, wanted)
    quotes.extend(lam)
    statuses.append(
        status(
            "Lambda rate card", _LAMBDA_URL, lam, "gpu_pricing:lambda",
            "published on-demand rate card, scraped from the pricing page; their API "
            "returns 401 without a paid account",
            "pricing table not parsed",
        )
    )

    notes: list[str] = []
    live_quotes = list(quotes)
    if not live_quotes:
        quotes = _fallback_quotes()
        basis = "fallback"
        trend = dict(FALLBACK_TREND)
        notes.append(
            f"No pricing source answered. Every rate below is the dated reference table "
            f"captured {FALLBACK_CAPTURED}, not a live quote. Treat the dollar figures as "
            f"illustrative of that date and re-run with a network connection before using "
            f"them for anything."
        )
    else:
        # Backfill classes no live source covered, so a partial outage does not
        # silently drop a GPU class out of the valuation.
        covered = {(q.gpu_class, q.kind) for q in quotes}
        added = [q for q in _fallback_quotes() if (q.gpu_class, q.kind) not in covered]
        wanted_names = {c.name for c in wanted}
        added = [q for q in added if q.gpu_class in wanted_names]
        if added:
            quotes.extend(added)
            notes.append(
                f"{len(added)} rate(s) came from the {FALLBACK_CAPTURED} reference table "
                f"because no live source covered that class and kind today. Those carry "
                f"stale=true."
            )
        basis = "partial" if added else "live"

    rates: dict[str, dict] = {}
    for spec in wanted:
        mine = [q for q in quotes if q.gpu_class == spec.name]
        if not mine:
            continue
        rates[spec.name] = {
            "marketplace_spot": _consolidate(mine, MARKETPLACE_SPOT),
            "published_list": _consolidate(mine, PUBLISHED_LIST),
            "power": {
                "board_watts": spec.board_watts,
                "node_watts": spec.node_watts,
                "node_basis": spec.node_basis,
            },
        }

    notes.append(
        "Marketplace spot and published list are reported separately and are never "
        "averaged together. Spot is what capacity clears at; list is a posted ask."
    )
    if trend:
        direction = "up" if trend["end_usd"] > trend["start_usd"] else "down"
        change = (
            (trend["end_usd"] - trend["start_usd"]) / trend["start_usd"] * 100.0
            if trend["start_usd"]
            else 0.0
        )
        notes.append(
            f"{trend['gpu_class']} traded {trend['start_usd']:.2f} -> {trend['end_usd']:.2f} "
            f"over the last {trend['window_days']} days on the {trend['source']}, "
            f"{direction} {abs(change):.0f}%. A rate that moves that much in a month is not "
            f"a rate you extrapolate for years."
        )

    return {
        "fetched": _now(),
        "basis": basis,
        "sources": [s.to_dict() for s in statuses],
        "trend": trend,
        "rates": rates,
        "notes": notes,
        "cache_ttl_days": ttl_days,
    }


def rate_for(
    gpu_class: str = DEFAULT_GPU_CLASS,
    kind: str = MARKETPLACE_SPOT,
    rates: dict | None = None,
) -> dict | None:
    """One consolidated figure for one class and one kind, or None."""
    table = rates if rates is not None else spot_rates([gpu_class])
    entry = (table.get("rates") or {}).get(gpu_class)
    return entry.get(kind) if entry else None


def power_for(gpu_class: str = DEFAULT_GPU_CLASS) -> GpuClass:
    """The accelerator's power figures. Raises on an unknown class rather than
    substituting a default, because a wrong watts-per-GPU silently rescales
    every dollar figure downstream."""
    try:
        return CLASS_BY_NAME[gpu_class]
    except KeyError as exc:
        raise KeyError(
            f"unknown GPU class {gpu_class!r}; known: {', '.join(CLASS_BY_NAME)}"
        ) from exc


def main() -> None:  # pragma: no cover - manual check
    """`python -m ingest.gpu_pricing`. Prints the book and where it came from."""
    import argparse

    parser = argparse.ArgumentParser(description="Current GPU rental rates, $/GPU-hour.")
    parser.add_argument("--offline", action="store_true", help="skip the network entirely")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    table = spot_rates(allow_network=not args.offline)
    if args.json:
        print(json.dumps(table, indent=2))
        return

    print(f"basis: {table['basis']}   fetched: {table['fetched']}")
    print()
    for source in table["sources"]:
        mark = "ok " if source["ok"] else "-- "
        auth = "auth required" if source["auth_required"] else "no auth"
        print(f"  {mark}{source['name']:26s} {auth:14s} {source['quotes']:>2} quotes  {source['note']}")
    print()
    print(f"  {'class':16s} {'spot $/hr':>10s} {'spot range':>16s} {'list $/hr':>10s}  power/GPU")
    for name, entry in table["rates"].items():
        spot = entry["marketplace_spot"]
        listed = entry["published_list"]
        spot_value = f"{spot['usd_per_gpu_hour']:.2f}" if spot else "-"
        spot_band = f"{spot['low']:.2f}-{spot['high']:.2f}" if spot else "-"
        list_value = f"{listed['usd_per_gpu_hour']:.2f}" if listed else "-"
        power = entry["power"]
        print(
            f"  {name:16s} {spot_value:>10s} {spot_band:>16s} {list_value:>10s}  "
            f"{power['node_watts']:.0f} W node / {power['board_watts']:.0f} W board"
        )
    print()
    for note in table["notes"]:
        print(f"  {note}")


if __name__ == "__main__":  # pragma: no cover
    main()
