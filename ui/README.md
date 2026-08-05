# ui/ — local client

A browser front end for driving the agent by hand instead of by CLI. It is a client over
the agent that already exists: it calls `agent.planner.Planner.run`, streams the trace the
run emits, and renders the `ProjectAssessment` that comes back. No permitting logic lives
here and nothing in `agent/` was restructured to serve it. The agent is the submission.

## Start it

```bash
.venv/bin/python -m uvicorn ui.server:app --port 8000
```

Then open http://127.0.0.1:8000. Run it from the repo root — `ui/server.py` chdirs there
itself, because the provider cache (`data/cache.sqlite`), the Green Book ingest and the
county file are all opened on paths relative to the root.

Keys come from `.env` via python-dotenv. If one is missing the page names it and says what
it buys, and the run still goes through the deterministic no-LLM path.

## What it does

**Streams the reasoning.** A run is a POST that returns Server-Sent Events. Every
`TraceStep` the agent emits is published the moment it is created — the model stating its
plan, each tool call with its payload, each result, each conclusion, the pathway chain
working through source category, threshold, attainment status, increment and the overlays.
The log follows the tail and stops following the moment you scroll up.

**Counts credits.** Each step carries what it billed, read off `MireyeProvider.usage()`.
A step served from the SQLite cache is marked `cached · 0 cr`. The rail carries the run
total and the session total.

**Gates the expensive loop.** The planner calls `search_alternate_sites` automatically
when a site fails. In the browser that call is intercepted and held: the trace says so, and
the search runs only when you press the button, which shows the candidate count, the
provider call count and the worst-case credit cost before it fires. There is also a per-run
credit ceiling; provider calls past it are refused, which the agent handles as a tool error.

**Refuses out loud.** A low-confidence geocode raises `ResolutionError`, and the page shows
that as a decision with its reason rather than as a failure. If a county was declared, the
screen continues against it and every conclusion is labelled unverified.

**Replays without spending.** "Replay the recorded run" streams `outputs/demo/trace.json`
and `outputs/demo/report.json` at reading speed. No model, no provider, no credits. It is
the fixture the page was built against and the safe way to demo it.

## Layout

```
server.py          FastAPI. SSE endpoints, the spend ceiling, the alternate-site gate.
static/index.html  Page shell.
static/app.js      Stream parsing and rendering. Vanilla, no build step.
static/style.css   Dark by default, light via prefers-color-scheme.
```

Three things in `server.py` are client policy rather than agent behaviour, and each is
commented where it happens: the alternate-site gate, the spend ceiling around the provider,
and one run at a time so the trace stream has a single publisher. The trace itself is
captured by wrapping `Trace.add` once at import; the agent does not know a browser is
watching.

## Endpoints

| | |
|---|---|
| `GET /api/context` | presets, enum options, key status, auth path, account credits |
| `POST /api/run` | SSE: `start`, `step`…, `report`, `done` |
| `POST /api/alternate-search` | SSE: the expensive loop, against the last run's site |
| `GET /api/alternate-estimate` | candidates, provider calls and worst-case credits |
| `POST /api/replay` | SSE: `outputs/demo/*.json` |
| `GET /api/last` | the last assessment as JSON |
