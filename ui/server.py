# This UI is a local client over the agent in agent/: it calls the agent and renders what comes back. No permitting logic lives here, nothing in agent/ was restructured to serve it, and the agent is the submission, not this page.
"""Local web UI for the Groundtruth agent.

Start it:

    .venv/bin/python -m uvicorn ui.server:app --reload --port 8000

What it does, and only what it does:

*   POSTs a project to `agent.planner.Planner.run` on a worker thread.
*   Streams every `TraceStep` the run emits over Server-Sent Events as it
    happens, so the reasoning is watchable rather than a spinner.
*   Renders the returned `ProjectAssessment` — verdict, triggers, the two
    search loops, provenance.

Three things here are client policy, not agent behaviour, and each is marked
where it happens:

1.  The alternate-site search is gated behind its own button. It is the biggest
    credit consumer in the product, so the planner's automatic call is
    intercepted and returns a "not run" result until a human asks for it.
2.  A spend ceiling wraps the provider. Every provider call checks the meter
    first and refuses past the ceiling. `run_tool` turns that into a tool error,
    which is a case the agent already handles.
3.  One run at a time, so the trace stream has exactly one publisher.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import queue
import sys
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# The provider cache, the Green Book ingest and the county file are all opened on
# paths relative to the repo root. Run from anywhere, read from there.
os.chdir(REPO_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(".env", override=False)
    _DOTENV = True
except Exception:  # pragma: no cover - python-dotenv is in requirements.txt
    _DOTENV = False

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import planner as planner_mod
from agent import search as search_mod
from agent.emissions import Control, Fuel, GenerationConfig, PrimeMover
from agent.planner import (
    AUTH_AGENT_SDK,
    AUTH_MESSAGES_API,
    AUTH_NONE,
    Planner,
    Project,
    ProjectAssessment,
    load_provider,
    resolve_auth,
)
from agent.search import (
    DEFAULT_RINGS_KM,
    AlternateSiteSearchResult,
    ring_points,
    search_alternate_sites,
)
from agent.tools import load_regulatory_context
from providers.base import NullProvider

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEMO_DIR = REPO_ROOT / "outputs" / "demo"

#: Measured, not guessed: one alternate-site candidate is a lookup (1 credit), the
#: utilities preset (27) and the proximity field fallback (8). Read straight off
#: the rows the last real search left in data/cache.sqlite.
CREDITS_PER_CANDIDATE = 36

#: Provider calls per candidate: geocode, lookup, fetch, proximity.
CALLS_PER_CANDIDATE = 4

#: Anything over this in a single run gets a confirmation first.
EXPENSIVE_CREDITS = 200


# --------------------------------------------------------------------------
# Trace streaming
# --------------------------------------------------------------------------
#
# `Trace.add` is wrapped once, here, so every step the agent emits is published
# the moment it is created. The agent is untouched — it does not know a browser
# is watching. Runs are serialised behind `_RUN_LOCK`, so a module-level channel
# is safe and is the only thing that survives the Agent SDK path hopping
# threads inside `asyncio.to_thread`.

_RUN_LOCK = threading.Lock()
_CHANNEL: "queue.Queue | None" = None
_METER: dict[str, float] = {}


def _publish(event: str, data: dict) -> None:
    channel = _CHANNEL
    if channel is not None:
        channel.put((event, data))


_ORIGINAL_TRACE_ADD = planner_mod.Trace.add


def _traced_add(self, *args, **kwargs):
    step = _ORIGINAL_TRACE_ADD(self, *args, **kwargs)
    if _CHANNEL is not None:
        _publish("step", _step_event(step))
    return step


planner_mod.Trace.add = _traced_add  # type: ignore[method-assign]


def _meter_now() -> tuple[float, int, int]:
    """(credits, cache hits, calls) off the live provider, or zeros."""
    provider = _PROVIDER
    usage = getattr(provider, "usage", None)
    if not callable(usage):
        return (0.0, 0, 0)
    try:
        u = usage()
    except Exception:
        return (0.0, 0, 0)
    return (float(u.get("credits_spent", 0)), int(u.get("cache_hits", 0)), int(u.get("calls", 0)))


def _step_event(step: Any) -> dict:
    """A trace step plus what it cost, measured across the provider's own meter.

    The delta is taken between consecutive steps, so it lands on the RESULT step
    that follows the tool call — which is where the call actually happened.
    """
    credits, hits, calls = _meter_now()
    payload = step.to_dict()
    payload["mireye_credits"] = round(credits - _METER.get("credits", credits), 1)
    payload["cache_hits"] = hits - int(_METER.get("cache_hits", hits))
    payload["provider_calls"] = calls - int(_METER.get("calls", calls))
    payload["run_credits"] = round(credits - _METER.get("run_start", credits), 1)
    payload["account_credits"] = round(credits, 1)
    _METER["credits"] = credits
    _METER["cache_hits"] = hits
    _METER["calls"] = calls
    return payload


def _synthetic_step(index: int, stage: str, kind: str, title: str, **kw) -> dict:
    """A step the UI itself emits — the gate notice, the alternate-search
    progress. Same shape as a real one so the log renders it identically."""
    credits, hits, calls = _meter_now()
    step = {
        "index": index,
        "stage": stage,
        "kind": kind,
        "title": title,
        "why": kw.get("why"),
        "tool": kw.get("tool"),
        "tool_input": kw.get("tool_input"),
        "result": kw.get("result"),
        "conclusion": kw.get("conclusion"),
        "citation": kw.get("citation"),
        "credits": 0,
        "elapsed_s": round(time.monotonic() - _METER.get("t0", time.monotonic()), 2),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mireye_credits": round(credits - _METER.get("credits", credits), 1),
        "cache_hits": hits - int(_METER.get("cache_hits", hits)),
        "provider_calls": calls - int(_METER.get("calls", calls)),
        "run_credits": round(credits - _METER.get("run_start", credits), 1),
        "account_credits": round(credits, 1),
        "source": "ui",
    }
    _METER["credits"] = credits
    _METER["cache_hits"] = hits
    _METER["calls"] = calls
    return step


# --------------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------------


class SpendCeiling(RuntimeError):
    """The run hit the credit ceiling the operator set for it."""


class GuardedProvider:
    """Delegates everything to the real provider, refusing past a credit ceiling.

    Client policy. The agent has its own tool-call and credit budget; this is the
    operator's, set in the browser before the run, because these are real credits
    and a mistyped candidate count is expensive. `run_tool` already turns any
    provider exception into a tool error the model can adapt to.
    """

    def __init__(self, inner: Any, ceiling: float | None, stream_calls: bool = False):
        self._inner = inner
        self._ceiling = ceiling
        self._stream_calls = stream_calls
        self._start = float(inner.usage()["credits_spent"]) if hasattr(inner, "usage") else 0.0
        self._seq = 0

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    def _check(self, what: str) -> None:
        if self._ceiling is None:
            return
        spent = float(self._inner.usage()["credits_spent"]) - self._start
        if spent >= self._ceiling:
            raise SpendCeiling(
                f"Credit ceiling reached: {spent:,.0f} of {self._ceiling:,.0f} credits spent "
                f"before {what}. Nothing further was bought."
            )

    def _wrap(self, what: str, fn, *args, **kwargs):
        self._check(what)
        before = float(self._inner.usage()["credits_spent"]) if hasattr(self._inner, "usage") else 0.0
        hits_before = int(self._inner.usage()["cache_hits"]) if hasattr(self._inner, "usage") else 0
        try:
            return fn(*args, **kwargs)
        finally:
            if self._stream_calls:
                self._seq += 1
                after = float(self._inner.usage()["credits_spent"])
                hits_after = int(self._inner.usage()["cache_hits"])
                cost = after - before
                _publish(
                    "step",
                    _synthetic_step(
                        0,
                        "stage 6 — act",
                        "observation" if cost == 0 else "tool",
                        what,
                        why=None,
                        tool=what,
                        result={
                            "credits": round(cost, 1),
                            "cached": hits_after > hits_before,
                        },
                    ),
                )

    # -- the PhysicalFactsProvider surface --------------------------------

    def geocode(self, query: str, min_confidence: float = 0.8):
        return self._wrap(f"geocode {query}", self._inner.geocode, query, min_confidence=min_confidence)

    def lookup(self, location):
        return self._wrap("lookup", self._inner.lookup, location)

    def fetch(self, location, presets):
        presets = list(presets)
        return self._wrap(f"fetch {', '.join(presets)}", self._inner.fetch, location, presets)

    def proximity(self, location, targets):
        targets = list(targets)
        return self._wrap(f"proximity {', '.join(targets)}", self._inner.proximity, location, targets)

    def ask(self, location, question: str):
        return self._wrap("ask", self._inner.ask, location, question)

    def field_request(self, *args, **kwargs):
        return self._inner.field_request(*args, **kwargs)


_PROVIDER: Any = None
_PROVIDER_NOTE = ""


def get_provider() -> tuple[Any, str]:
    """One provider for the life of the process, so the SQLite cache stays hot
    and a re-run of the same parcel costs nothing."""
    global _PROVIDER, _PROVIDER_NOTE
    if _PROVIDER is None:
        _PROVIDER, _PROVIDER_NOTE = load_provider()
    return _PROVIDER, _PROVIDER_NOTE


# --------------------------------------------------------------------------
# Gate on the alternate-site search
# --------------------------------------------------------------------------

_ALLOW_ALTERNATE = threading.Event()

_GATE_NOTE = (
    "Not run. This UI gates the alternate-site search behind its own button because it is "
    "the biggest credit consumer in the product — it resolves a fresh parcel on every ring. "
    "Use “Search for a better parcel” below."
)


def _gated_search_alternate_sites(site, config, **kwargs) -> AlternateSiteSearchResult:
    if _ALLOW_ALTERNATE.is_set():
        return search_alternate_sites(site, config, **kwargs)
    baseline = kwargs.get("baseline")
    _publish(
        "step",
        _synthetic_step(
            0,
            "stage 6 — act",
            "note",
            "Alternate-site search held at the gate",
            why=_GATE_NOTE,
        ),
    )
    return AlternateSiteSearchResult(
        origin_county=site.county,
        origin_state=site.state,
        origin_pathway=baseline.pathway.value if baseline else "unknown",
        origin_months_likely=baseline.months_likely if baseline else 0.0,
        rings_km=[],
        candidates_considered=0,
        candidates_resolved=0,
        delta_statement="Alternate-site search not run — it is behind its own button in this UI.",
        notes=[_GATE_NOTE],
    )


search_mod.search_alternate_sites = _gated_search_alternate_sites  # type: ignore[assignment]


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------

PRESETS = [
    {
        "id": "ashburn",
        "name": "Ashburn, VA",
        "subtitle": "Excellent site. Still 57 months.",
        "address": "39.0176,-77.4899",
        "county": "Loudoun",
        "state": "VA",
        "mw": 500,
        "prime_mover": PrimeMover.COMBINED_CYCLE_TURBINE.value,
        "fuel": Fuel.NATURAL_GAS.value,
        "controls": [Control.DLN.value, Control.SCR.value, Control.OXIDATION_CATALYST.value],
        "target": "2028-06-01",
    },
    {
        "id": "vineland",
        "name": "Vineland, NJ",
        "subtitle": "The Nebius parcel.",
        "address": "39.4862,-75.0257",
        "county": "Cumberland",
        "state": "NJ",
        "mw": 400,
        "prime_mover": PrimeMover.SIMPLE_CYCLE_TURBINE.value,
        "fuel": Fuel.NATURAL_GAS.value,
        "controls": [],
        "target": "2027-12-01",
    },
    {
        # The counterexample the README runs on. Ellis County was the old one and
        # it is wrong — Ellis sits in the Dallas-Fort Worth severe-15 ozone area,
        # so the same plant lands on major nonattainment NSR with an offset hard
        # stop. Anderson County is the Texas parcel that is actually fast.
        "id": "anderson",
        "name": "Anderson County, TX",
        "subtitle": "Same machine, Texas dirt.",
        "address": "31.8413,-95.6617",
        "county": "Anderson",
        "state": "TX",
        "mw": 500,
        "prime_mover": PrimeMover.COMBINED_CYCLE_TURBINE.value,
        "fuel": Fuel.NATURAL_GAS.value,
        "controls": [Control.DLN.value, Control.SCR.value, Control.OXIDATION_CATALYST.value],
        "target": "2028-06-01",
    },
]

PRIME_MOVER_LABELS = {
    PrimeMover.COMBINED_CYCLE_TURBINE.value: "Combined cycle turbine",
    PrimeMover.SIMPLE_CYCLE_TURBINE.value: "Simple cycle turbine",
    PrimeMover.RECIP_LEAN_BURN.value: "Recip, lean burn gas",
    PrimeMover.RECIP_RICH_BURN.value: "Recip, rich burn gas",
    PrimeMover.DIESEL_RECIP.value: "Diesel recip",
    PrimeMover.FUEL_CELL.value: "Solid oxide fuel cell",
}

FUEL_LABELS = {
    Fuel.NATURAL_GAS.value: "Natural gas",
    Fuel.DIESEL.value: "Diesel, ULSD",
}

CONTROL_LABELS = {
    Control.DLN.value: "Dry low-NOx combustors",
    Control.WATER_INJECTION.value: "Water injection",
    Control.SCR.value: "Selective catalytic reduction",
    Control.OXIDATION_CATALYST.value: "Oxidation catalyst",
    Control.TIER4.value: "EPA Tier 4 final",
}

#: What each key buys. Shown when one is missing, so the gap is specific.
KEYS = [
    (
        "MIREYE_API_KEY",
        "Physical facts: geocode, parcel, terrain, pipeline and transmission distance, "
        "receptors. Without it the run uses NullProvider, which refuses every lookup "
        "rather than returning a plausible default.",
    ),
    (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "The tool-calling loop through the Claude Agent SDK. Without it the run falls "
        "through to ANTHROPIC_API_KEY, and then to the deterministic no-LLM path, which "
        "walks the same functions in the same order.",
    ),
    (
        "ANTHROPIC_API_KEY",
        "The tool-calling loop through the Messages API. Second choice after the OAuth "
        "token.",
    ),
    (
        "COURTLISTENER_TOKEN",
        "Live docket search for suits against the developer or the county. Without it the "
        "litigation trigger is reported as unread, not as clear.",
    ),
]


class RunRequest(BaseModel):
    address: str
    mw: float = 400
    prime_mover: str = PrimeMover.SIMPLE_CYCLE_TURBINE.value
    fuel: str = Fuel.NATURAL_GAS.value
    controls: list[str] = []
    target: str | None = None
    county: str | None = None
    state: str | None = None
    name: str | None = None
    no_llm: bool = False
    ceiling: float | None = 400


class AlternateRequest(BaseModel):
    radius_km: float = 30
    n: int = 16
    ceiling: float | None = 600


def _parse_coordinate(text: str) -> tuple[float, float] | None:
    parts = [p.strip() for p in text.replace(" ", ",").split(",") if p.strip()]
    if len(parts) != 2:
        return None
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return (lat, lon)
    return None


def _project_from(req: RunRequest) -> Project:
    controls = tuple(Control(c) for c in req.controls if c and c != Control.NONE.value)
    config = GenerationConfig(
        mw=float(req.mw),
        prime_mover=PrimeMover(req.prime_mover),
        fuel=Fuel(req.fuel),
        controls=controls,
    )
    coord = _parse_coordinate(req.address)
    return Project(
        address=req.address.strip(),
        config=config,
        target_energization=date.fromisoformat(req.target) if req.target else None,
        name=req.name or f"Screen — {req.address.strip()}",
        declared_county=req.county or None,
        declared_state=req.state or None,
        declared_latitude=coord[0] if coord else None,
        declared_longitude=coord[1] if coord else None,
    )


# --------------------------------------------------------------------------
# Assessment payload
# --------------------------------------------------------------------------

#: Akshat's call: the product does not describe what it declines to do, anywhere.
#: This is the one engine-generated caveat that is about that rather than about
#: the analysis, and it is dropped from the page rather than reworded.
_DROPPED_CAVEAT = "does not contact agencies, file anything, or send anything"


def _provenance_rows(assessment: ProjectAssessment) -> list[dict]:
    """Field, value, source, fetched, confidence. The value lives on the Fact and
    not in `assessment.to_dict()['provenance']`, so it is read off the FactSet."""
    rows: list[dict] = []
    for key, fact in assessment.facts.facts.items():
        rows.append(
            {
                "field": key,
                "value": f"{fact.value}" + (f" {fact.unit}" if fact.unit else ""),
                "source": fact.source or "—",
                "fetched": fact.fetched or "—",
                "confidence": fact.confidence,
                "note": fact.note,
            }
        )
    if assessment.site:
        for status in assessment.site.nonattainment:
            rows.append(
                {
                    "field": f"nonattainment.{status.pollutant}",
                    "value": f"{status.classification} — {status.area_name}",
                    "source": status.source,
                    "fetched": status.fetched or "—",
                    "confidence": None,
                    "note": None,
                }
            )
    return sorted(rows, key=lambda r: r["field"])


def _payload(assessment: ProjectAssessment) -> dict:
    data = assessment.to_dict()
    data.pop("trace", None)  # the browser already has it, step by step
    data["caveats"] = [c for c in data.get("caveats", []) if _DROPPED_CAVEAT not in c]
    data["provenance_rows"] = _provenance_rows(assessment)
    data["emissions_full"] = (
        {
            "tons_per_year": assessment.estimate.tons_per_year,
            "lb_per_hour": assessment.estimate.lb_per_hour,
            "basis": assessment.estimate.basis,
        }
        if assessment.estimate
        else None
    )
    data["alternate_gated"] = bool(
        assessment.alternate is not None and _GATE_NOTE in (assessment.alternate.notes or [])
    )
    return data


def _alternate_payload(result: AlternateSiteSearchResult) -> dict:
    return result.to_dict()


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------

app = FastAPI(title="Groundtruth — local client")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_LAST: dict[str, Any] = {}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/context")
def context() -> dict:
    provider, note = get_provider()
    keys = [
        {"name": name, "present": bool(os.environ.get(name)), "enables": enables}
        for name, enables in KEYS
    ]
    auth = resolve_auth()
    usage = getattr(provider, "usage", None)
    account = usage() if callable(usage) else {}
    return {
        "presets": PRESETS,
        "prime_movers": [{"value": k, "label": v} for k, v in PRIME_MOVER_LABELS.items()],
        "fuels": [{"value": k, "label": v} for k, v in FUEL_LABELS.items()],
        "controls": [{"value": k, "label": v} for k, v in CONTROL_LABELS.items()],
        "keys": keys,
        "dotenv": _DOTENV,
        "auth": auth,
        "auth_label": {
            AUTH_AGENT_SDK: "Claude Agent SDK",
            AUTH_MESSAGES_API: "Anthropic Messages API",
            AUTH_NONE: "deterministic, no LLM",
        }[auth],
        "auth_detail": planner_mod.AUTH_DESCRIPTION[auth],
        "model": planner_mod.DEFAULT_MODEL if auth != AUTH_NONE else None,
        "provider": provider.name,
        "provider_note": note,
        "account": {
            "credits_spent": round(float(account.get("credits_spent", 0)), 1),
            "calls": account.get("calls", 0),
            "cache_hits": account.get("cache_hits", 0),
            "cache_hit_rate": account.get("cache_hit_rate", 0),
        },
        "expensive_credits": EXPENSIVE_CREDITS,
        "demo_available": (DEMO_DIR / "report.json").exists(),
    }


@app.get("/api/alternate-estimate")
def alternate_estimate(radius_km: float = 30, n: int = 16) -> dict:
    """What the expensive loop will cost before it fires.

    The candidate count is computed with the same ring geometry the search uses,
    so this is the real number of parcels, not a guess.
    """
    rings = [r for r in DEFAULT_RINGS_KM if r >= radius_km] or [radius_km]
    if rings[0] > radius_km:
        rings = [radius_km] + rings
    per_ring = max(1, math.ceil(n / len(rings)))
    points = ring_points(0.0, 0.0, rings, per_ring)[:n]
    candidates = len(points)
    return {
        "candidates": candidates,
        "rings_km": rings,
        "provider_calls": candidates * CALLS_PER_CANDIDATE,
        "credits_if_uncached": candidates * CREDITS_PER_CANDIDATE,
        "credits_per_candidate": CREDITS_PER_CANDIDATE,
        "note": (
            f"{candidates} candidate parcels across {len(rings)} rings, "
            f"{CALLS_PER_CANDIDATE} provider calls each. A candidate already in the cache "
            f"bills 0 and is marked CACHED in the trace."
        ),
    }


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode("utf-8")


async def _drain(channel: "queue.Queue", done: threading.Event):
    """Pump the worker thread's queue out as SSE without blocking the loop."""
    last_beat = time.monotonic()
    while True:
        drained = False
        while True:
            try:
                event, data = channel.get_nowait()
            except queue.Empty:
                break
            drained = True
            yield _sse(event, data)
            if event == "done":
                return
        if done.is_set() and not drained:
            # The worker exited without a done frame. Say so rather than hanging.
            yield _sse("done", {"ok": False, "reason": "run ended without a result"})
            return
        if time.monotonic() - last_beat > 10:
            last_beat = time.monotonic()
            yield b": keepalive\n\n"
        await asyncio.sleep(0.05)


def _start_channel(ceiling: float | None) -> tuple["queue.Queue", Any]:
    """Open the stream, snapshot the meter, wrap the provider in the ceiling."""
    global _CHANNEL
    provider, _ = get_provider()
    credits, hits, calls = 0.0, 0, 0
    usage = getattr(provider, "usage", None)
    if callable(usage):
        u = usage()
        credits, hits, calls = float(u["credits_spent"]), int(u["cache_hits"]), int(u["calls"])
    _METER.clear()
    _METER.update(
        {
            "credits": credits,
            "cache_hits": hits,
            "calls": calls,
            "run_start": credits,
            "run_hits": hits,
            "t0": time.monotonic(),
        }
    )
    channel: "queue.Queue" = queue.Queue()
    _CHANNEL = channel
    guarded = provider if isinstance(provider, NullProvider) else GuardedProvider(provider, ceiling)
    return channel, guarded


def _close_channel() -> None:
    global _CHANNEL
    _CHANNEL = None


@app.post("/api/run")
async def run(req: RunRequest):
    if not _RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A run is already in flight.")
    try:
        project = _project_from(req)
    except Exception as exc:
        _RUN_LOCK.release()
        raise HTTPException(status_code=400, detail=f"{exc.__class__.__name__}: {exc}")

    channel, guarded = _start_channel(req.ceiling)
    _ALLOW_ALTERNATE.clear()
    provider, provider_note = get_provider()
    done = threading.Event()

    def worker() -> None:
        try:
            planner = Planner(
                provider=guarded,
                auth=AUTH_NONE if req.no_llm else None,
                max_tool_calls=24,
                max_credits=400,
            )
            channel.put(
                (
                    "start",
                    {
                        "mode": planner.auth,
                        "provider": provider.name,
                        "provider_note": provider_note,
                        "project": project.describe(),
                        "ceiling": req.ceiling,
                        "account_credits": _METER.get("run_start", 0),
                    },
                )
            )
            assessment = planner.run(project)
            _LAST["assessment"] = assessment
            channel.put(("report", _payload(assessment)))
            credits, hits, calls = _meter_now()
            channel.put(
                (
                    "done",
                    {
                        "ok": True,
                        "run_credits": round(credits - _METER.get("run_start", credits), 1),
                        "account_credits": round(credits, 1),
                        "cache_hits": hits - int(_METER.get("run_hits", hits)),
                        "tool_calls": assessment.tool_calls,
                    },
                )
            )
        except Exception as exc:  # the browser gets the reason, not a dead socket
            channel.put(("error", {"message": f"{exc.__class__.__name__}: {exc}"}))
            channel.put(("done", {"ok": False}))
        finally:
            done.set()

    threading.Thread(target=worker, name="groundtruth-run", daemon=True).start()

    async def stream():
        try:
            async for chunk in _drain(channel, done):
                yield chunk
        finally:
            _close_channel()
            _RUN_LOCK.release()

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/alternate-search")
async def alternate(req: AlternateRequest):
    """The expensive loop, on purpose, by hand.

    Runs against the site the last run resolved. Every provider call it makes is
    streamed with what it cost, so a cached ring is visibly free.
    """
    assessment: ProjectAssessment | None = _LAST.get("assessment")
    if assessment is None or assessment.site is None or assessment.pathway is None:
        raise HTTPException(status_code=400, detail="Run a screen first — there is no site to search around.")
    if assessment.site.latitude is None or assessment.site.longitude is None:
        raise HTTPException(
            status_code=400,
            detail="The last run has no resolved coordinate, so there is no ring to search around.",
        )
    if not _RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A run is already in flight.")

    channel, _ = _start_channel(req.ceiling)
    provider, _note = get_provider()
    guarded = provider if isinstance(provider, NullProvider) else GuardedProvider(
        provider, req.ceiling, stream_calls=True
    )
    done = threading.Event()
    site = assessment.site
    config = assessment.project.config
    baseline = assessment.pathway

    def worker() -> None:
        _ALLOW_ALTERNATE.set()
        try:
            estimate = alternate_estimate(req.radius_km, req.n)
            channel.put(
                (
                    "start",
                    {
                        "mode": "alternate-site search",
                        "provider": provider.name,
                        "project": f"{site.county} County, {site.state}",
                        "ceiling": req.ceiling,
                        "estimate": estimate,
                        "account_credits": _METER.get("run_start", 0),
                    },
                )
            )
            _publish(
                "step",
                _synthetic_step(
                    0,
                    "stage 6 — act",
                    "plan",
                    "Alternate-site search, requested by hand",
                    why=(
                        f"{baseline.pathway.label} at the announced parcel. Searching outward "
                        f"across county and state lines for ground where the same plant gets a "
                        f"faster answer. {estimate['note']} Ceiling {req.ceiling:,.0f} credits."
                    ),
                ),
            )
            result = search_alternate_sites(
                site,
                config,
                provider=guarded,
                regulatory_lookup=load_regulatory_context,
                radius_km=req.radius_km,
                n_candidates=req.n,
                baseline=baseline,
            )
            _publish(
                "step",
                _synthetic_step(
                    0,
                    "stage 6 — act",
                    "conclusion" if result.best else "note",
                    result.delta_statement or "No better parcel found",
                    why="; ".join(result.notes) or None,
                    result={
                        "candidates_resolved": result.candidates_resolved,
                        "candidates_considered": result.candidates_considered,
                        "rings_km": result.rings_km,
                    },
                ),
            )
            assessment.alternate = result
            _LAST["assessment"] = assessment
            channel.put(("alternate", _alternate_payload(result)))
            credits, hits, _calls = _meter_now()
            channel.put(
                (
                    "done",
                    {
                        "ok": True,
                        "run_credits": round(credits - _METER.get("run_start", credits), 1),
                        "account_credits": round(credits, 1),
                    },
                )
            )
        except Exception as exc:
            channel.put(("error", {"message": f"{exc.__class__.__name__}: {exc}"}))
            channel.put(("done", {"ok": False}))
        finally:
            _ALLOW_ALTERNATE.clear()
            done.set()

    threading.Thread(target=worker, name="groundtruth-alt", daemon=True).start()

    async def stream():
        try:
            async for chunk in _drain(channel, done):
                yield chunk
        finally:
            _close_channel()
            _RUN_LOCK.release()

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/replay")
async def replay():
    """Replay `outputs/demo/*.json` at reading speed. No model, no provider, no
    credits — the fixture the UI was built against, and the safe demo."""
    trace_path = DEMO_DIR / "trace.json"
    report_path = DEMO_DIR / "report.json"
    if not trace_path.exists() or not report_path.exists():
        raise HTTPException(status_code=404, detail="outputs/demo/ has no report.json and trace.json.")
    trace = json.loads(trace_path.read_text())
    report = json.loads(report_path.read_text())
    report.pop("trace", None)
    report["caveats"] = [c for c in report.get("caveats", []) if _DROPPED_CAVEAT not in c]
    report["replay"] = True

    async def stream():
        yield _sse(
            "start",
            {
                "mode": "replay",
                "provider": report.get("provider", "recorded"),
                "project": report["project"]["config"],
                "replay": True,
                "note": f"Replaying {trace_path.relative_to(REPO_ROOT)}. Recorded {report['generated_at']}.",
            },
        )
        for step in trace["steps"]:
            step = dict(step)
            step["replay"] = True
            yield _sse("step", step)
            await asyncio.sleep(0.09)
        yield _sse("report", report)
        yield _sse("done", {"ok": True, "replay": True, "run_credits": 0})

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.get("/api/last")
def last() -> JSONResponse:
    assessment = _LAST.get("assessment")
    if assessment is None:
        raise HTTPException(status_code=404, detail="No run yet.")
    return JSONResponse(_payload(assessment))


_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    # nginx and friends buffer text/event-stream by default, which kills the point.
    "X-Accel-Buffering": "no",
}


def main() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "ui.server:app",
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
