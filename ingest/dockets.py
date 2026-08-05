"""Federal court dockets from CourtListener / RECAP.

Litigation is the blocker that does not show up in any permit database. A county
can be attainment, the zoning can be by-right, the pipeline can be next door, and
the project still stops because someone filed a Clean Air Act citizen suit. That
is not hypothetical: it is what happened to xAI's Colossus 2 gas plant, and the
case is in here (see docs/ingest-notes.md for the verification run).

Two things the agent actually wants to know:

  for_developer(name)     Has this developer been sued, and over what
  for_county(county, st)  Has this county been sued over a data center, a permit
                          or a zoning decision

Both run through the v4 search endpoint at
https://www.courtlistener.com/api/rest/v4/search/ with type=r (RECAP: federal
dockets plus the documents filed in them).

Notes on the API, verified 5 Aug 2026:

  * The search endpoint answers without a token. The dockets endpoint returns 401
    without one. We use search only, so COURTLISTENER_TOKEN is an upgrade rather
    than a requirement — it raises the rate limit and is what CourtListener asks
    you to do before running anything in production.
  * `party_name` filters on the actual parties to the case. `q` is full text over
    the docket and every filed document. For "has this developer been sued" the
    party filter is the honest query — a brief that happens to name Google is not
    Google being sued.
  * `court` takes space-separated court IDs. An unknown ID returns zero results
    rather than an error, so a typo looks like an answer. STATE_DISTRICT_COURTS
    below is generated from the API's own court list to avoid that.
  * A docket appears once per matching document, so results need dedup by
    docket_id.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

API_ROOT = "https://www.courtlistener.com/api/rest/v4"
SEARCH_URL = f"{API_ROOT}/search/"
WEB_ROOT = "https://www.courtlistener.com"

_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = _ROOT / "data" / "dockets_cache.json"
CACHE_TTL = timedelta(days=7)

#: Federal district courts by state, generated 5 Aug 2026 from
#: /api/rest/v4/courts/?jurisdiction=FD with defunct courts dropped. Hardcoded
#: rather than fetched because it changes roughly never and a live fetch would
#: spend a rate-limited request on a constant.
STATE_DISTRICT_COURTS: dict[str, tuple[str, ...]] = {
    "AK": ("akd",),
    "AL": ("almd", "alnd", "alsd"),
    "AR": ("ared", "arwd"),
    "AZ": ("azd",),
    "CA": ("cacd", "caed", "cand", "casd"),
    "CO": ("cod",),
    "CT": ("ctd",),
    "DC": ("dcd",),
    "DE": ("ded",),
    "FL": ("flmd", "flnd", "flsd"),
    "GA": ("gamd", "gand", "gasd"),
    "HI": ("hid",),
    "IA": ("iand", "iasd"),
    "ID": ("idd",),
    "IL": ("ilcd", "ilnd", "ilsd"),
    "IN": ("innd", "insd"),
    "KS": ("ksd",),
    "KY": ("kyed", "kywd"),
    "LA": ("laed", "lamd", "lawd"),
    "MA": ("mad",),
    "MD": ("mdd",),
    "ME": ("med",),
    "MI": ("mied", "miwd"),
    "MN": ("mnd",),
    "MO": ("moed", "mowd"),
    "MS": ("msnd", "mssd"),
    "MT": ("mtd",),
    "NC": ("nced", "ncmd", "ncwd"),
    "ND": ("ndd",),
    "NE": ("ned",),
    "NH": ("nhd",),
    "NJ": ("njd",),
    "NM": ("nmd",),
    "NV": ("nvd",),
    "NY": ("nyed", "nynd", "nysd", "nywd"),
    "OH": ("ohnd", "ohsd"),
    "OK": ("oked", "oknd", "okwd"),
    "OR": ("ord",),
    "PA": ("paed", "pamd", "pawd"),
    "PR": ("prd",),
    "RI": ("rid",),
    "SC": ("scd",),
    "SD": ("sdd",),
    "TN": ("tned", "tnmd", "tnwd"),
    "TX": ("txed", "txnd", "txsd", "txwd"),
    "UT": ("utd",),
    "VA": ("vaed", "vawd"),
    "VT": ("vtd",),
    "WA": ("waed", "wawd"),
    "WI": ("wied", "wiwd"),
    "WV": ("wvnd", "wvsd"),
    "WY": ("wyd",),
}

#: What a data center fight looks like in a federal filing. Two sets, because the
#: two passes in for_county() tolerate different amounts of noise.
#:
#: The party pass already knows the county is a defendant, so it can afford broad
#: land-use language. The venue pass matches on any document in the district that
#: mentions the county, so anything generic — "comprehensive plan", "moratorium",
#: "ordinance" — drags in school board and civil rights cases by the dozen.
_LAND_USE_TERMS = (
    '"data center"',
    '"data centre"',
    "rezoning",
    '"special exception"',
    '"conditional use"',
    '"comprehensive plan"',
    "moratorium",
    '"zoning ordinance"',
    '"Clean Air Act"',
    '"air permit"',
)
_SITING_TERMS = (
    '"data center"',
    '"data centre"',
    '"special exception"',
    '"conditional use permit"',
    '"Clean Air Act"',
    '"air permit"',
)


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Docket:
    """One federal case.

    `cause` and `parties` are here because without them you cannot tell a Clean
    Air Act citizen suit from a contract dispute, and "12 cases touching this
    developer" is a useless number if eleven of them are trademark.
    """

    case_name: str
    docket_number: str
    court: str
    date_filed: str | None
    url: str
    snippet: str = ""
    cause: str | None = None
    parties: tuple[str, ...] = ()

    def summary(self) -> str:
        parts = [self.case_name]
        if self.docket_number:
            parts.append(self.docket_number)
        if self.court:
            parts.append(self.court)
        if self.date_filed:
            parts.append(f"filed {self.date_filed}")
        if self.cause:
            parts.append(self.cause)
        return " — ".join(parts)


@dataclass
class SearchStatus:
    """Why the last search returned what it returned.

    The agent must not crash because a free API is rate limited, and it must not
    quietly report "no litigation" when what actually happened is "no token, no
    network, or a 429". Every failure path sets `reason` and returns an empty
    list, and callers that care can check status().ok.
    """

    ok: bool = True
    authenticated: bool = False
    reason: str = ""
    results: int = 0
    from_cache: bool = False


_status = SearchStatus()

NO_TOKEN_REASON = (
    "COURTLISTENER_TOKEN is not set. The v4 search endpoint still answers "
    "unauthenticated, so results below are real, but the anonymous rate limit is "
    "low and CourtListener asks that production code authenticate. Free token: "
    "https://www.courtlistener.com/help/api/rest/"
)


def status() -> SearchStatus:
    return _status


def authenticated() -> bool:
    return bool(os.environ.get("COURTLISTENER_TOKEN"))


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1, sort_keys=True))


def _cache_key(params: dict) -> str:
    return "|".join(f"{k}={params[k]}" for k in sorted(params))


def _fresh(entry: dict) -> bool:
    try:
        fetched = datetime.fromisoformat(entry["fetched"])
    except (KeyError, ValueError):
        return False
    return datetime.now(timezone.utc) - fetched < CACHE_TTL


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


def _parse(result: dict) -> Docket:
    documents = result.get("recap_documents") or []
    snippet = ""
    for document in documents:
        text = (document.get("snippet") or "").strip()
        if text:
            snippet = " ".join(text.split())[:400]
            break
    if not snippet:
        snippet = (result.get("cause") or "").strip()

    path = result.get("docket_absolute_url") or ""
    return Docket(
        case_name=result.get("caseName") or result.get("case_name_full") or "",
        docket_number=result.get("docketNumber") or "",
        court=result.get("court_citation_string") or result.get("court_id") or "",
        date_filed=result.get("dateFiled"),
        url=f"{WEB_ROOT}{path}" if path.startswith("/") else path,
        snippet=snippet,
        cause=result.get("cause") or None,
        parties=tuple(result.get("party") or ()),
    )


def _request(params: dict, use_cache: bool, timeout: float) -> list[Docket]:
    """One search call. Never raises; failures are recorded on _status."""
    global _status
    key = _cache_key(params)
    cache = _load_cache()

    if use_cache and key in cache and _fresh(cache[key]):
        entry = cache[key]
        _status = SearchStatus(
            ok=True,
            authenticated=authenticated(),
            reason=f"cached {entry['fetched']}",
            results=len(entry["results"]),
            from_cache=True,
        )
        return [Docket(**{**row, "parties": tuple(row.get("parties", ()))}) for row in entry["results"]]

    token = os.environ.get("COURTLISTENER_TOKEN")
    headers = {"User-Agent": "deliverable/0.1 (permit pathway screen)"}
    if token:
        headers["Authorization"] = f"Token {token}"

    try:
        response = httpx.get(SEARCH_URL, params=params, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        _status = SearchStatus(False, bool(token), f"CourtListener unreachable: {exc}")
        return []

    if response.status_code == 429:
        _status = SearchStatus(
            False,
            bool(token),
            "CourtListener rate limit hit"
            + ("" if token else f". {NO_TOKEN_REASON}"),
        )
        return []
    if response.status_code in (401, 403):
        _status = SearchStatus(
            False, bool(token), f"CourtListener rejected the request ({response.status_code}). {NO_TOKEN_REASON}"
        )
        return []
    if response.status_code != 200:
        _status = SearchStatus(False, bool(token), f"CourtListener returned HTTP {response.status_code}")
        return []

    try:
        payload = response.json()
    except json.JSONDecodeError:
        _status = SearchStatus(False, bool(token), "CourtListener returned a non-JSON body")
        return []

    dockets = [_parse(row) for row in payload.get("results", [])]
    cache[key] = {
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_matches": payload.get("count"),
        "results": [asdict(d) for d in dockets],
    }
    _save_cache(cache)

    _status = SearchStatus(
        ok=True,
        authenticated=bool(token),
        reason="" if token else NO_TOKEN_REASON,
        results=len(dockets),
    )
    return dockets


def search(
    query: str,
    court: str | list[str] | None = None,
    filed_after: str | date | None = None,
    *,
    party_name: str | None = None,
    limit: int = 20,
    use_cache: bool = True,
    timeout: float = 60.0,
) -> list[Docket]:
    """Run one RECAP search and return the dockets, newest first.

    `court` is a two-letter state code, a CourtListener court ID, or a list of
    either. Passing a state expands to that state's federal district courts.
    """
    params: dict[str, str] = {"type": "r", "order_by": "dateFiled desc"}
    if query:
        params["q"] = query
    if party_name:
        params["party_name"] = party_name
    if court:
        params["court"] = " ".join(_court_ids(court))
    if filed_after:
        params["filed_after"] = (
            filed_after.isoformat() if isinstance(filed_after, date) else str(filed_after)
        )
    if not query and not party_name:
        raise ValueError("search() needs a query or a party_name")

    return _request(params, use_cache, timeout)[:limit]


def _court_ids(court: str | list[str]) -> list[str]:
    values = [court] if isinstance(court, str) else list(court)
    ids: list[str] = []
    for value in values:
        key = value.strip()
        if key.upper() in STATE_DISTRICT_COURTS:
            ids.extend(STATE_DISTRICT_COURTS[key.upper()])
        else:
            ids.append(key.lower())
    return ids


def _dedupe(dockets: list[Docket]) -> list[Docket]:
    seen: set[tuple[str, str]] = set()
    out: list[Docket] = []
    for docket in dockets:
        key = (docket.docket_number, docket.court)
        if key in seen:
            continue
        seen.add(key)
        out.append(docket)
    return out


# --------------------------------------------------------------------------
# The two questions the agent asks
# --------------------------------------------------------------------------


def for_developer(
    name: str,
    filed_after: str | date | None = "2020-01-01",
    limit: int = 20,
) -> list[Docket]:
    """Has this developer been sued, and over what.

    Filters on party name rather than full text. A developer named in someone
    else's exhibit is not a defendant, and counting those inflates the risk
    signal, which is the one thing this number cannot afford.
    """
    if not name.strip():
        return []
    dockets = search("", party_name=name.strip(), filed_after=filed_after, limit=limit)
    return _dedupe(dockets)


def for_county(
    county: str,
    state: str,
    filed_after: str | date | None = "2020-01-01",
    limit: int = 20,
) -> list[Docket]:
    """Has this county been sued over a data center, a permit or a zoning call.

    Two passes, because the two ways this shows up look nothing alike:
    the county as a named party (a denied applicant suing the board), and a case
    that merely happens in the county (a citizen suit against the operator). Both
    matter to a timeline; only the first is a party-name hit.
    """
    county = county.strip()
    state = state.strip().upper()
    if not county or state not in STATE_DISTRICT_COURTS:
        return []

    label = county if county.lower().endswith(("county", "parish", "borough", "city")) else f"{county} County"

    as_party = search(
        "(" + " OR ".join(_LAND_USE_TERMS) + ")",
        court=state,
        filed_after=filed_after,
        party_name=label,
        limit=limit,
    )
    as_venue = search(
        f'"{label}" AND (' + " OR ".join(_SITING_TERMS) + ")",
        court=state,
        filed_after=filed_after,
        limit=limit,
    )
    return _dedupe(as_party + as_venue)[:limit]


def as_litigation_notes(dockets: list[Docket]) -> list[str]:
    """One line per case, shaped for SiteContext.litigation."""
    return [d.summary() for d in dockets]


if __name__ == "__main__":  # pragma: no cover
    print(f"authenticated: {authenticated()}")

    print("\n-- xAI, as a party --")
    for docket in for_developer("X.AI Corp.", filed_after="2024-01-01"):
        print(f"  {docket.summary()}")
        print(f"     {docket.url}")
    print(f"  status: {status().reason or 'ok'}")

    time.sleep(1)
    print("\n-- Prince William County, VA --")
    for docket in for_county("Prince William", "VA", filed_after="2021-01-01"):
        print(f"  {docket.summary()}")
    print(f"  status: {status().reason or 'ok'}")
