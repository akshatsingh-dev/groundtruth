"""Local news as a leading indicator of county opposition.

The hand-entered county file (ingest/counties.json) is 27 records that were read
from a primary source before they were typed. It is accurate and it is static.
The thing it cannot do is tell you that a county which was permissive last month
is now holding hearings, because nobody has re-typed it.

Opposition surfaces in a county newspaper and on a board agenda months before it
surfaces in a permit denial. That is the signal this module reads.

Two questions the agent asks:

  signals_for_county(county, state)   What is the local press saying about data
                                      centers in this county, how much of it is
                                      there, and is it rising
  reconcile()                         Run that against all 27 hand-entered
                                      records and report where they disagree

Sources, both keyless, verified 5 Aug 2026:

  * **GDELT DOC 2.0** — https://api.gdeltproject.org/api/v2/doc/doc
    Free, no key, no registration. Two modes are used.
      - `timelinevolraw` returns a raw article count per day for the full
        requested window, plus `norm`, the total number of articles GDELT
        monitored that day. It is not capped, so it is what volume and trend
        are computed from.
      - `artlist` returns individual articles (url, title, domain, seendate).
        It is capped at 250 records and, in testing, only reached back about
        three months regardless of the window asked for. So items are a
        shorter window than the volume series. That gap is reported, not hidden.
    Rate limit is one request every five seconds, enforced by IP, and it returns
    a plain-text "Please limit requests" body with HTTP 429 or even HTTP 200. We
    throttle, retry with backoff, and treat that body as a failure.

  * **Bing News RSS** — https://www.bing.com/news/search?...&format=RSS
    Free, no key. Returns roughly 5-10 items with a real one-line snippet, the
    publication display name and a pubDate. The `link` is a bing.com/apiclick
    redirect with the true article URL in its `url` query parameter, which we
    unwrap so the link a human clicks goes to the newspaper. This is where the
    summaries come from. GDELT does not return one and we do not write one.

  Google News RSS was checked and rejected. It answers, but its `<description>`
  is the headline wrapped in an anchor tag rather than a summary, and its links
  are opaque `news.google.com/rss/articles/CBMi...` redirects. Using it would
  have meant either shipping no summary or writing one, and writing one is
  fabrication.

What this cannot tell you, stated up front because the number looks more solid
than it is:

  * **Volume is not opposition.** A county with five newspapers generates more
    articles than a county with one. Every signal therefore carries
    `baseline_articles` — how many articles mentioned the county at all in the
    same window — and `coverage_share`, the data-center share of that. A county
    can look quiet because nobody covers it, and `thin_media` says so.
  * **GDELT matches the whole article body.** A statewide roundup that names
    this county once counts as a hit. `headline_named` counts the subset where
    the county appears in the headline, and the posture rules lean on that.
  * **One article is not organised opposition.** The floors are in
    `POSTURE_RULES` and they are stated in the evidence string.
  * **A derived posture is not a fact.** It is a label, a confidence, and a list
    of links. Where it disagrees with a hand-entered record, the hand-entered
    record wins, because that one was checked against a primary source. This
    module flags the record for re-checking; it does not overwrite it. See
    `apply_to`.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

import httpx

from providers.cache import ResponseCache

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
BING_URL = "https://www.bing.com/news/search"

_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = str(_ROOT / "data" / "cache.sqlite")
CACHE_MAX_AGE_DAYS = 3.0

#: GDELT asks for one request every five seconds. Five is not enough in practice:
#: a burst that respects it still gets refused, and once refused the IP stays in
#: a penalty box for a while. 8 s between calls plus a linear backoff on retry is
#: what got a clean 27-county run. This is the reason the response cache is not
#: optional — a cold reconciliation takes about twenty minutes and a warm one
#: takes two seconds.
GDELT_MIN_INTERVAL = 8.0
GDELT_RETRIES = 6

USER_AGENT = "deliverable/0.1 (permit pathway screen)"

_RATE_LIMIT_BODY = "please limit requests"


# --------------------------------------------------------------------------
# Posture
# --------------------------------------------------------------------------


class Posture(str, Enum):
    """Ordered least to most constrained. `rank` compares two counties.

    These are press postures, not legal ones. FORMAL_ACTION means the local
    press reported a board doing something, not that a clerk has certified an
    ordinance. `ingest/counties.json` is the file that holds the certified
    version.
    """

    QUIET = "quiet"
    ACTIVE_INTEREST = "active_interest"
    ORGANISED_OPPOSITION = "organised_opposition"
    FORMAL_ACTION = "formal_action"

    @property
    def rank(self) -> int:
        return list(Posture).index(self)

    @property
    def label(self) -> str:
        return {
            Posture.QUIET: "no data center coverage found",
            Posture.ACTIVE_INTEREST: "covered, no opposition or action language",
            Posture.ORGANISED_OPPOSITION: "repeated coverage carrying opposition language",
            Posture.FORMAL_ACTION: "press reports a board vote, ordinance or moratorium",
        }[self]


#: The thresholds, in one place, so the notes and the code cannot drift apart.
#:
#: `stories` counts deduplicated stories, not URLs. The same wire item under six
#: mastheads is one story. `headline_named` counts stories whose headline
#: contains the county name — the guard against a statewide roundup promoting a
#: county it mentions once.
POSTURE_RULES: dict[str, dict] = {
    "formal_action": {
        "min_stories_with_action_language": 2,
        "min_headline_named": 1,
        "why": "Two independent stories using board-action language, at least one "
        "of which names the county in its headline. Two rather than one because "
        "a single syndicated roundup naming six counties would otherwise promote "
        "all six.",
    },
    "organised_opposition": {
        "min_stories": 3,
        "min_stories_with_opposition_language": 2,
        "why": "Three stories in the window, two of them carrying opposition "
        "language. One article is a story, not a movement. Two articles about the "
        "same hearing collapse to one story in dedup before this is counted.",
    },
    "active_interest": {
        "min_stories": 2,
        "why": "Two stories about data centers in this county, with no opposition "
        "or action language in either.",
    },
    "quiet": {
        "why": "Fewer than two stories, or no data. Not the same as no opposition. "
        "Check baseline_articles before reading anything into it.",
    },
}

#: Below this many articles mentioning the county at all in the window, the
#: county's media market is too thin for absence to mean anything.
THIN_MEDIA_BASELINE = 30

#: Trend needs a floor too. Four articles split 1/3 is noise.
TREND_MIN_ARTICLES = 4
TREND_RISING = 1.5
TREND_FALLING = 0.67


# --------------------------------------------------------------------------
# Query vocabulary
# --------------------------------------------------------------------------

#: What the thing is called. "data centers" is listed separately because GDELT
#: phrase matching is over word tokens and does not stem the plural.
_DATA_CENTER_TERMS = ('"data center"', '"data centers"', '"data centre"', "datacenter")

#: Classifiers, run over the text we actually hold — headline plus, where the
#: feed gave one, the one-line summary. Not over the article body, which we do
#: not fetch. Stated because "the headline said moratorium" and "the article is
#: about a moratorium" are different claims.
_ACTION_TERMS = (
    "moratorium",
    "moratoria",
    "ordinance",
    "text amendment",
    "voted to",
    "vote to",
    "votes to",
    "denied",
    "denies",
    "rejects",
    "rejected",
    "turns down",
    "ban on",
    "bans ",
    "banned",
    "pause",
    "paused",
    "halt",
    "freeze",
    "hitting the brakes",
    "hitting brakes",
)
_OPPOSITION_TERMS = (
    "opposition",
    "opponents",
    "oppose",
    "opposed",
    "protest",
    "rally",
    "petition",
    "pushback",
    "push back",
    "backlash",
    "outcry",
    "grassroots",
    "coalition",
    "residents",
    "neighbors",
    "neighbours",
    "packed",
    "speak out",
    "spoke out",
    "concerns",
    "concerned",
    "fight",
    "fighting",
    "lawsuit",
    "sues",
    "sued",
    "appeal",
)
_PROCEEDING_TERMS = (
    "rezoning",
    "rezone",
    "special exception",
    "special use",
    "conditional use",
    "planning commission",
    "planning board",
    "board of supervisors",
    "board of commissioners",
    "county commission",
    "county council",
    "public hearing",
    "comprehensive plan",
    "zoning",
)
_INFRA_TERMS = (
    "substation",
    "gas turbine",
    "turbines",
    "transmission line",
    "megawatt",
    "power plant",
    "groundwater",
    "water use",
)

#: Consolidated city-counties, where the bare place name is the county and a
#: query for "X County" finds nothing. Keyed on FIPS to avoid name collisions.
_CONSOLIDATED = {
    "08014": "Broomfield",
    "08031": "Denver",
    "06075": "San Francisco",
    "24510": "Baltimore",
    "29510": "St. Louis",
}

#: Domains that publish national aggregate coverage. Not a blocklist — items
#: from these still appear — but a story that only exists on one of these is not
#: local coverage of this county, and `local_stories` excludes them.
_NATIONAL_DOMAINS = frozenset(
    {
        "newsweek.com",
        "usatoday.com",
        "reuters.com",
        "apnews.com",
        "cnbc.com",
        "cnn.com",
        "foxnews.com",
        "nytimes.com",
        "washingtonpost.com",
        "wsj.com",
        "bloomberg.com",
        "businessinsider.com",
        "forbes.com",
        "theguardian.com",
        "yahoo.com",
        "msn.com",
        "investmentwatchblog.com",
        "constructiondive.com",
        "utilitydive.com",
        "datacenterdynamics.com",
        "datacenterfrontier.com",
        "datacenterknowledge.com",
        "bisnow.com",
    }
)


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class NewsItem:
    """One story, after dedup.

    `summary` is empty unless a feed handed us one. GDELT does not, Bing does.
    Nothing here is written by this module or by a model.

    `also_reported_by` is the other mastheads that carried what dedup judged to
    be the same story. It is the receipt for the story count: if it is long, the
    item was syndicated, and counting URLs would have overstated the coverage.
    """

    headline: str
    publication: str
    published: str | None
    url: str
    summary: str = ""
    feed: str = ""
    county_in_headline: bool = False
    also_reported_by: tuple[str, ...] = ()

    def line(self) -> str:
        parts = [self.headline.strip()]
        if self.publication:
            parts.append(self.publication)
        if self.published:
            parts.append(self.published)
        head = " — ".join(parts)
        if self.also_reported_by:
            head += f" (+{len(self.also_reported_by)} other masthead(s))"
        return head


@dataclass(frozen=True)
class Trend:
    """Article volume in the first half of the window against the second half.

    Computed from GDELT's daily raw counts over the full window, which is not
    subject to the 250-record item cap. `direction` is "unknown" below
    TREND_MIN_ARTICLES because a 1-to-3 split is not a direction.
    """

    first_half: int
    second_half: int
    direction: str
    window_days: int

    @property
    def ratio(self) -> float | None:
        if self.first_half == 0:
            return None
        return self.second_half / self.first_half

    def describe(self) -> str:
        if self.direction == "unknown":
            return (
                f"trend unknown: {self.first_half + self.second_half} articles over "
                f"{self.window_days} days is below the {TREND_MIN_ARTICLES}-article floor"
            )
        return (
            f"{self.direction}: {self.first_half} articles in the first "
            f"{self.window_days // 2} days, {self.second_half} in the second"
        )


@dataclass
class LocalSignal:
    """What the local press says about data centers in one county.

    Read `posture` with `confidence` and `evidence` or do not read it at all.
    `items` is the point: the links are what a human checks.
    """

    county: str
    state: str
    fips: str | None = None

    posture: Posture = Posture.QUIET
    confidence: str = "none"  # none | low | medium | high
    evidence: list[str] = field(default_factory=list)
    items: list[NewsItem] = field(default_factory=list)

    story_count: int = 0
    local_story_count: int = 0
    headline_named: int = 0
    article_count: int = 0
    baseline_articles: int = 0
    coverage_share: float | None = None
    thin_media: bool = False

    trend: Trend = field(default_factory=lambda: Trend(0, 0, "unknown", 0))
    window_days: int = 180
    items_window_note: str = ""

    no_data: bool = False
    reason: str = ""
    queries: list[str] = field(default_factory=list)
    fetched: str = ""

    def describe(self) -> str:
        head = (
            f"{self.county} County, {self.state}: local news posture "
            f"{self.posture.value} ({self.posture.label}), confidence {self.confidence}"
        )
        if self.no_data:
            return f"{head}. {self.reason}"
        body = (
            f"{self.story_count} distinct stories from {self.article_count} articles "
            f"over {self.window_days} days; {self.headline_named} name the county in "
            f"the headline. {self.trend.describe()}."
        )
        share = (
            f" Data centers were {self.coverage_share:.1%} of the "
            f"{self.baseline_articles} articles mentioning this county at all."
            if self.coverage_share is not None
            else ""
        )
        thin = (
            " Thin media market — low volume here is a coverage fact, not a posture fact."
            if self.thin_media
            else ""
        )
        return f"{head}. {body}{share}{thin}"

    def as_note(self) -> str:
        """One line shaped for a report, with the caveat attached."""
        if self.no_data:
            return (
                f"Local news signal: no data ({self.reason}). This is not a finding of "
                f"no opposition."
            )
        return (
            f"Local news signal: {self.posture.value}, confidence {self.confidence}, "
            f"{self.story_count} distinct stories over {self.window_days} days, "
            f"{self.trend.direction}. Derived from headlines, not verified against a "
            f"primary source."
        )


@dataclass
class FetchStatus:
    """Why the last fetch returned what it returned.

    Mirrors ingest/dockets.py. No network, a rate limit or a parse failure all
    produce an empty result with a reason set. Nothing here ever reports "quiet"
    without saying which of those happened.
    """

    ok: bool = True
    reason: str = ""
    gdelt_calls: int = 0
    gdelt_from_cache: int = 0
    bing_calls: int = 0
    failures: list[str] = field(default_factory=list)


_status = FetchStatus()
_cache: ResponseCache | None = None
_last_gdelt_call = 0.0


def status() -> FetchStatus:
    return _status


def authenticated() -> bool:
    """Neither source takes a key. Here because every other ingest module has it
    and the planner checks it uniformly."""
    return True


def _cache_handle() -> ResponseCache | None:
    global _cache
    if _cache is None:
        try:
            _cache = ResponseCache(CACHE_PATH)
        except Exception:
            return None
    return _cache


# --------------------------------------------------------------------------
# Query construction
# --------------------------------------------------------------------------


def _county_label(county: str, state: str) -> str:
    """`Linn` -> `Linn County`. Louisiana takes Parish, Alaska takes Borough."""
    name = county.strip()
    if name.lower().endswith(("county", "parish", "borough", "city", "municipality")):
        return name
    suffix = {"LA": "Parish", "AK": "Borough"}.get(state.strip().upper(), "County")
    return f"{name} {suffix}"


def _county_phrases(county: str, state: str, fips: str | None = None) -> tuple[str, ...]:
    """Quoted phrases that mean this county, OR'd together in the query.

    Prince George's is why this is not one string: the apostrophe is rendered
    straight, curly or dropped depending on the paper's CMS, and GDELT indexes
    what it was given. Broomfield is why FIPS is checked: it is a consolidated
    city-county, so "Broomfield County" appears nowhere and the bare name is the
    county.
    """
    label = _county_label(county, state)
    phrases = [f'"{label}"']
    if "'" in label:
        phrases.append(f'"{label.replace(chr(39), "")}"')
    if fips and str(fips).zfill(5) in _CONSOLIDATED:
        bare = _CONSOLIDATED[str(fips).zfill(5)]
        phrases.append(f'"City and County of {bare}"')
        phrases.append(f'"{bare}"')
    return tuple(dict.fromkeys(phrases))


def _or_group(phrases: tuple[str, ...] | list[str]) -> str:
    """GDELT rejects parentheses around anything that is not an OR list, with
    "Parentheses may only be used around OR'd statements." A single-element
    group therefore has to go in bare. That refusal arrives as a plain-text body
    on an HTTP 200, so a wrapped single phrase reads as zero articles rather
    than as an error, which would have made every one-name county look quiet."""
    items = list(dict.fromkeys(phrases))
    return items[0] if len(items) == 1 else "(" + " OR ".join(items) + ")"


def _signal_query(county: str, state: str, fips: str | None = None) -> str:
    """County AND a data-center term. Nothing else.

    The wider term list from the brief — moratorium, rezoning, special
    exception, board of supervisors, planning commission, substation, gas
    turbine — was tested as OR alternatives at query level and rejected. On Linn
    County IA over 180 days it took the hit count from 69 to 98, and the 29
    extra articles were county board coverage with no data center in them. Those
    terms are used as classifiers over the returned headlines instead, where
    they discriminate rather than dilute.
    """
    counties = _or_group(_county_phrases(county, state, fips))
    terms = _or_group(_DATA_CENTER_TERMS)
    return f"{counties} {terms} sourcecountry:US"


def _baseline_query(county: str, state: str, fips: str | None = None) -> str:
    """County name alone. The denominator for the media-market problem."""
    return f"{_or_group(_county_phrases(county, state, fips))} sourcecountry:US"


def _bing_query(county: str, state: str) -> str:
    label = _county_label(county, state)
    return f'"{label}" "data center"'


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------


def _throttle() -> None:
    global _last_gdelt_call
    if _last_gdelt_call == 0.0:
        # First call of the process. We do not know what the last one from this
        # IP was, and GDELT holds a grudge, so pay the interval up front.
        time.sleep(GDELT_MIN_INTERVAL)
    else:
        wait = GDELT_MIN_INTERVAL - (time.monotonic() - _last_gdelt_call)
        if wait > 0:
            time.sleep(wait)
    _last_gdelt_call = time.monotonic()


def _gdelt(params: dict, *, use_cache: bool = True, timeout: float = 60.0) -> dict | None:
    """One GDELT call. Returns the parsed body or None. Never raises.

    Caches through providers/cache.py keyed on the full parameter dict, which is
    what makes a 27-county reconciliation re-runnable without spending twenty
    minutes on the rate limiter again.

    GDELT signals a rate limit with a plain-text body that is sometimes served
    with HTTP 200, so the body is checked as well as the status.
    """
    global _status
    cache = _cache_handle()
    if use_cache and cache is not None:
        hit = cache.get("gdelt/doc", params, max_age_days=CACHE_MAX_AGE_DAYS)
        if hit is not None and hit.ok:
            _status.gdelt_from_cache += 1
            return hit.body

    last = ""
    for attempt in range(GDELT_RETRIES):
        _throttle()
        if attempt:
            time.sleep(GDELT_MIN_INTERVAL * attempt)
        try:
            response = httpx.get(
                GDELT_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout
            )
        except httpx.HTTPError as exc:
            last = f"GDELT unreachable: {exc}"
            break
        _status.gdelt_calls += 1
        text = (response.text or "").strip()
        if _RATE_LIMIT_BODY in text[:200].lower() or response.status_code == 429:
            last = "GDELT rate limited (one request per 5 s, per IP)"
            continue
        if response.status_code != 200:
            last = f"GDELT returned HTTP {response.status_code}"
            break
        if not text:
            # An empty result set is served as an empty body, not as empty JSON.
            body = {}
        elif not text.startswith("{"):
            # Everything else GDELT says in plain text is a complaint about the
            # query or the load, and it is worth reporting verbatim rather than
            # as "no data".
            last = f"GDELT returned a non-JSON body: {' '.join(text.split())[:160]}"
            continue
        else:
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                last = "GDELT returned malformed JSON"
                continue
        if cache is not None:
            cache.set("gdelt/doc", params, response.status_code, body)
        return body

    _status.ok = False
    _status.reason = last
    _status.failures.append(f"{params.get('mode')}: {last}")
    return None


def _bing(query: str, *, use_cache: bool = True, timeout: float = 45.0) -> str | None:
    """One Bing News RSS call. Returns the XML text or None. Never raises."""
    global _status
    params = {"q": query, "format": "RSS", "count": "30"}
    cache = _cache_handle()
    if use_cache and cache is not None:
        hit = cache.get("bing/news_rss", params, max_age_days=CACHE_MAX_AGE_DAYS)
        if hit is not None and hit.ok and isinstance(hit.body, dict):
            return hit.body.get("xml")

    try:
        response = httpx.get(
            BING_URL,
            params=params,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        _status.failures.append(f"bing: unreachable ({exc})")
        return None
    _status.bing_calls += 1
    if response.status_code != 200:
        _status.failures.append(f"bing: HTTP {response.status_code}")
        return None
    if cache is not None:
        cache.set("bing/news_rss", params, 200, {"xml": response.text})
    return response.text


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def _daily_counts(body: dict | None) -> list[tuple[str, int]]:
    """[(YYYYMMDD, article_count)] from a timelinevolraw response."""
    if not body:
        return []
    out: list[tuple[str, int]] = []
    for series in body.get("timeline") or []:
        for point in series.get("data") or []:
            stamp = str(point.get("date") or "")[:8]
            if len(stamp) == 8:
                out.append((stamp, int(point.get("value") or 0)))
        break  # timelinevolraw returns one series
    return out


def _gdelt_items(body: dict | None, county: str, state: str) -> list[NewsItem]:
    if not body:
        return []
    label = _county_label(county, state).lower()
    bare = county.strip().lower()
    items: list[NewsItem] = []
    for row in body.get("articles") or []:
        url = (row.get("url") or "").strip()
        title = " ".join((row.get("title") or "").split())
        if not url or not title:
            continue
        stamp = str(row.get("seendate") or "")
        published = f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}" if len(stamp) >= 8 else None
        low = title.lower()
        items.append(
            NewsItem(
                headline=title,
                publication=(row.get("domain") or "").strip(),
                published=published,
                url=url,
                summary="",  # GDELT does not return one. We do not write one.
                feed="gdelt",
                county_in_headline=(label in low or f"{bare} county" in low),
            )
        )
    return items


def _unwrap_bing(link: str) -> str:
    """Pull the real article URL out of a bing.com/apiclick redirect."""
    if "bing.com/news/apiclick" not in link:
        return link
    parsed = urllib.parse.urlparse(link)
    target = urllib.parse.parse_qs(parsed.query).get("url")
    return target[0] if target else link


def _bing_items(xml: str | None, county: str, state: str, since: date) -> list[NewsItem]:
    if not xml:
        return []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        _status.failures.append("bing: unparseable RSS")
        return []

    label = _county_label(county, state).lower()
    items: list[NewsItem] = []
    for node in root.iter("item"):
        title = html.unescape((node.findtext("title") or "")).strip()
        url = _unwrap_bing(html.unescape((node.findtext("link") or "")).strip())
        if not title or not url:
            continue
        summary = html.unescape((node.findtext("description") or "")).strip()
        source = next(
            (c.text for c in node if c.tag.endswith("Source") and c.text),
            urllib.parse.urlparse(url).netloc,
        )
        published = _parse_rfc822(node.findtext("pubDate"))
        if published and published < since:
            continue
        items.append(
            NewsItem(
                headline=title,
                publication=(source or "").strip(),
                published=published.isoformat() if published else None,
                url=url,
                summary=summary,
                feed="bing",
                county_in_headline=label in title.lower(),
            )
        )
    return items


def _parse_rfc822(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# Dedup
# --------------------------------------------------------------------------

_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the to "
    "with was were will would county new news says said after over into".split()
)
_LOCATION_PREFIX = re.compile(r"^\s*\[?[A-Z][A-Za-z.\s]{2,30},\s*[A-Za-z.\s]{2,20}\]?\s*[-—–]\s*")
_MASTHEAD_SUFFIX = re.compile(r"\s*[-|–—]\s*[^-|–—]{2,40}$")


def _normalise_title(title: str) -> str:
    text = html.unescape(title)
    text = _LOCATION_PREFIX.sub("", text)
    text = _MASTHEAD_SUFFIX.sub("", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return " ".join(text.split())


def _tokens(title: str) -> frozenset[str]:
    return frozenset(w for w in _normalise_title(title).split() if w not in _STOPWORDS and len(w) > 2)


def _canonical_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/").lower()
    return f"{host}{path}"


def _same_story(a: NewsItem, b: NewsItem) -> bool:
    """Two items are one story if the URL is the same page, or the headlines
    overlap heavily and the dates are close.

    Jaccard on content tokens rather than an edit distance, because syndication
    rewrites the top and tail of a headline — a dateline goes on, a masthead
    comes off — while the middle survives. 0.6 was set by eye against the
    Prince George's cluster, where a Patch item ran under four MSN mastheads.
    """
    if _canonical_url(a.url) == _canonical_url(b.url):
        return True
    ta, tb = _tokens(a.headline), _tokens(b.headline)
    if not ta or not tb:
        return False
    jaccard = len(ta & tb) / len(ta | tb)
    if jaccard < 0.6:
        return False
    if a.published and b.published:
        gap = abs(date.fromisoformat(a.published) - date.fromisoformat(b.published)).days
        return gap <= 5
    return True


def deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    """Collapse syndicated copies into one story each.

    Local news syndicates hard. The same AP or Patch item runs under six
    mastheads, and counting URLs turns one board meeting into six data points.
    Representative selection prefers an item that has a real summary, then a
    non-national domain, then the earliest date — the earliest is usually the
    paper that did the reporting.
    """
    clusters: list[list[NewsItem]] = []
    for item in items:
        for cluster in clusters:
            if any(_same_story(item, existing) for existing in cluster):
                cluster.append(item)
                break
        else:
            clusters.append([item])

    out: list[NewsItem] = []
    for cluster in clusters:
        ordered = sorted(
            cluster,
            key=lambda i: (
                0 if i.summary else 1,
                0 if _canonical_url(i.url).split("/")[0] not in _NATIONAL_DOMAINS else 1,
                i.published or "9999",
            ),
        )
        lead = ordered[0]
        others = tuple(
            dict.fromkeys(i.publication for i in ordered[1:] if i.publication and i.publication != lead.publication)
        )
        out.append(
            NewsItem(
                headline=lead.headline,
                publication=lead.publication,
                published=lead.published,
                url=lead.url,
                summary=lead.summary,
                feed=lead.feed,
                county_in_headline=any(i.county_in_headline for i in cluster),
                also_reported_by=others,
            )
        )
    out.sort(key=lambda i: i.published or "", reverse=True)
    return out


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


def _hits(item: NewsItem, terms: tuple[str, ...]) -> list[str]:
    text = f"{item.headline} {item.summary}".lower()
    return [t.strip() for t in terms if t in text]


def _is_local(item: NewsItem) -> bool:
    host = _canonical_url(item.url).split("/")[0]
    return host not in _NATIONAL_DOMAINS


def _classify(stories: list[NewsItem]) -> tuple[Posture, list[str]]:
    """Apply POSTURE_RULES and say which stories drove the call.

    Every branch returns the evidence that satisfied it, including the count
    that cleared the floor, because "organised_opposition" with no reason
    attached is a number someone will quote without checking.
    """
    action = [(s, _hits(s, _ACTION_TERMS)) for s in stories]
    action = [(s, h) for s, h in action if h]
    opposition = [(s, _hits(s, _OPPOSITION_TERMS)) for s in stories]
    opposition = [(s, h) for s, h in opposition if h]
    proceeding = [(s, _hits(s, _PROCEEDING_TERMS)) for s in stories]
    proceeding = [(s, h) for s, h in proceeding if h]
    named = [s for s in stories if s.county_in_headline]

    evidence: list[str] = []

    rule = POSTURE_RULES["formal_action"]
    action_named = [s for s, _ in action if s.county_in_headline]
    if (
        len(action) >= rule["min_stories_with_action_language"]
        and len(action_named) >= rule["min_headline_named"]
    ):
        terms = sorted({t for _, h in action for t in h})
        evidence.append(
            f"formal_action: {len(action)} stories use board-action language "
            f"({', '.join(terms[:6])}), {len(action_named)} of them name the county in "
            f"the headline. Floor is {rule['min_stories_with_action_language']} stories "
            f"and {rule['min_headline_named']} headline mention."
        )
        evidence.extend(f"  drove it: {s.line()}" for s, _ in action[:3])
        return Posture.FORMAL_ACTION, evidence

    rule = POSTURE_RULES["organised_opposition"]
    if (
        len(stories) >= rule["min_stories"]
        and len(opposition) >= rule["min_stories_with_opposition_language"]
    ):
        terms = sorted({t for _, h in opposition for t in h})
        evidence.append(
            f"organised_opposition: {len(stories)} distinct stories, {len(opposition)} "
            f"carrying opposition language ({', '.join(terms[:6])}). Floor is "
            f"{rule['min_stories']} stories and "
            f"{rule['min_stories_with_opposition_language']} with opposition language. "
            f"One article is never organised opposition."
        )
        evidence.extend(f"  drove it: {s.line()}" for s, _ in opposition[:3])
        return Posture.ORGANISED_OPPOSITION, evidence

    rule = POSTURE_RULES["active_interest"]
    if len(stories) >= rule["min_stories"]:
        evidence.append(
            f"active_interest: {len(stories)} distinct stories about data centers in "
            f"this county, {len(named)} naming it in the headline. "
            f"{len(action)} with action language, {len(opposition)} with opposition "
            f"language, {len(proceeding)} mentioning a zoning proceeding — none of "
            f"those cleared their floor."
        )
        evidence.extend(f"  {s.line()}" for s in stories[:3])
        return Posture.ACTIVE_INTEREST, evidence

    evidence.append(
        f"quiet: {len(stories)} distinct story(s), below the "
        f"{POSTURE_RULES['active_interest']['min_stories']}-story floor. "
        f"Absence of coverage is not absence of opposition."
    )
    evidence.extend(f"  {s.line()}" for s in stories[:2])
    return Posture.QUIET, evidence


def _confidence(signal: LocalSignal) -> str:
    if signal.no_data:
        return "none"
    if signal.posture is Posture.QUIET and signal.thin_media:
        return "low"
    if signal.story_count >= 5 and signal.headline_named >= 2 and signal.trend.direction != "unknown":
        return "high"
    if signal.story_count >= 3 and signal.headline_named >= 1:
        return "medium"
    return "low"


def _trend(daily: list[tuple[str, int]], window_days: int) -> Trend:
    if not daily:
        return Trend(0, 0, "unknown", window_days)
    half = len(daily) // 2
    first = sum(v for _, v in daily[:half])
    second = sum(v for _, v in daily[half:])
    total = first + second
    if total < TREND_MIN_ARTICLES:
        return Trend(first, second, "unknown", window_days)
    if first == 0:
        return Trend(first, second, "rising", window_days)
    ratio = second / first
    if ratio >= TREND_RISING:
        direction = "rising"
    elif ratio <= TREND_FALLING:
        direction = "falling"
    else:
        direction = "flat"
    return Trend(first, second, direction, window_days)


# --------------------------------------------------------------------------
# The question the agent asks
# --------------------------------------------------------------------------


def signals_for_county(
    county: str,
    state: str,
    since_days: int = 180,
    *,
    fips: str | None = None,
    use_cache: bool = True,
    with_items: bool = True,
    max_items: int = 25,
) -> LocalSignal:
    """What is the local press saying about data centers in this county.

    Three GDELT calls and one Bing call, all keyless:

      1. `timelinevolraw` on county AND data-center terms — daily article counts
         over the full window. Volume and trend come from here because it is not
         capped.
      2. `timelinevolraw` on the county name alone — the media-market
         denominator. A county with five newspapers should not read as more
         opposed than a county with one.
      3. `artlist` on the same signal query — the actual articles. Capped at 250
         records and, in practice, the most recent ~90 days.
      4. Bing News RSS — the same question, for the one-line summaries GDELT does
         not carry.

    With no network this returns posture=quiet, no_data=True and a reason. That
    combination means "we could not look", and `describe()` says so. It does not
    mean the county is quiet.
    """
    global _status
    _status = FetchStatus()

    county = county.strip()
    state = state.strip().upper()
    fips = str(fips).zfill(5) if fips else None
    since_days = max(14, int(since_days))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=since_days)
    window = {
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
        "format": "json",
    }

    signal_q = _signal_query(county, state, fips)
    baseline_q = _baseline_query(county, state, fips)
    bing_q = _bing_query(county, state)

    signal = LocalSignal(
        county=county,
        state=state,
        fips=fips,
        window_days=since_days,
        queries=[signal_q, baseline_q, bing_q],
        fetched=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    volume = _gdelt({**window, "query": signal_q, "mode": "timelinevolraw"}, use_cache=use_cache)
    if volume is None:
        signal.no_data = True
        signal.reason = (
            f"Could not reach GDELT ({_status.reason or 'no network'}). No local news was "
            f"read for {county} County, {state}. Posture is reported as quiet because "
            f"there is nothing to report, not because the county is quiet."
        )
        signal.evidence = [signal.reason]
        return signal

    daily = _daily_counts(volume)
    signal.article_count = sum(v for _, v in daily)
    signal.trend = _trend(daily, since_days)

    baseline = _gdelt({**window, "query": baseline_q, "mode": "timelinevolraw"}, use_cache=use_cache)
    signal.baseline_articles = sum(v for _, v in _daily_counts(baseline))
    if signal.baseline_articles:
        signal.coverage_share = signal.article_count / signal.baseline_articles
        signal.thin_media = signal.baseline_articles < THIN_MEDIA_BASELINE
    else:
        signal.thin_media = True

    items: list[NewsItem] = []
    if with_items:
        artlist = _gdelt(
            {
                **window,
                "query": signal_q,
                "mode": "artlist",
                "maxrecords": "250",
                "sort": "datedesc",
            },
            use_cache=use_cache,
        )
        items.extend(_gdelt_items(artlist, county, state))
        items.extend(_bing_items(_bing(bing_q, use_cache=use_cache), county, state, start.date()))
        if items:
            dates = sorted(i.published for i in items if i.published)
            if dates:
                signal.items_window_note = (
                    f"Items span {dates[0]} to {dates[-1]}. The volume series covers the "
                    f"full {since_days} days; GDELT's article list reaches back about 90, "
                    f"so an older action can show in the counts and not in the links."
                )

    stories = deduplicate(items)
    signal.items = stories[:max_items]
    signal.story_count = len(stories)
    signal.local_story_count = sum(1 for s in stories if _is_local(s))
    signal.headline_named = sum(1 for s in stories if s.county_in_headline)

    if signal.article_count == 0 and not stories:
        signal.posture = Posture.QUIET
        signal.evidence = [
            f"quiet: zero articles in {since_days} days matching {signal_q}. "
            f"{signal.baseline_articles} articles mentioned this county at all, so the "
            + (
                "county is covered and data centers are not the subject."
                if not signal.thin_media
                else "county is barely covered at all and absence proves nothing."
            )
        ]
        signal.confidence = _confidence(signal)
        return signal

    signal.posture, signal.evidence = _classify(stories)
    signal.confidence = _confidence(signal)

    if signal.thin_media:
        signal.evidence.append(
            f"media-market caveat: only {signal.baseline_articles} articles mentioned "
            f"{county} County at all in {since_days} days, below the "
            f"{THIN_MEDIA_BASELINE}-article floor. Volume here is a coverage fact."
        )
    elif signal.coverage_share is not None:
        signal.evidence.append(
            f"media-market normalisation: data centers were {signal.coverage_share:.1%} "
            f"of the {signal.baseline_articles} articles mentioning this county, which "
            f"is the comparable number across counties. Raw volume is not."
        )
    if signal.headline_named == 0 and signal.story_count:
        signal.evidence.append(
            "no story names this county in its headline. GDELT matches the article "
            "body, so these may be statewide coverage that mentions the county once."
        )
    return signal


def tone_for_county(
    county: str,
    state: str,
    since_days: int = 180,
    *,
    fips: str | None = None,
    use_cache: bool = True,
) -> dict | None:
    """GDELT tone distribution for the signal query. Opt-in, and not load-bearing.

    What GDELT tone actually is: for each article, GDELT counts words appearing
    in its positive and negative emotion dictionaries across the **whole article
    body** and reports roughly (percent positive words - percent negative words).
    It is not a stance model. It does not know what the article is about. A local
    story about a data center hearing scores negative partly because "opposition"
    and "concerns" are negative words, and partly because the same page carried a
    car crash. We saw that directly: a query for Linn County plus data centers
    returned a rear-end-collision story in the -5 tone bin.

    So this returns the distribution and a mean, and nothing in `Posture` reads
    it. It is here because it is cheap context on a page a human is already
    looking at, not because it is a measurement of opposition.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(14, int(since_days)))
    body = _gdelt(
        {
            "query": _signal_query(county, state, fips),
            "mode": "tonechart",
            "format": "json",
            "startdatetime": start.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end.strftime("%Y%m%d%H%M%S"),
        },
        use_cache=use_cache,
    )
    if not body:
        return None
    bins = [(int(b.get("bin", 0)), int(b.get("count", 0))) for b in body.get("tonechart") or []]
    total = sum(c for _, c in bins)
    if not total:
        return None
    return {
        "articles": total,
        "mean_tone": round(sum(b * c for b, c in bins) / total, 2),
        "share_negative": round(sum(c for b, c in bins if b <= -2) / total, 3),
        "bins": dict(sorted(bins)),
        "what_it_measures": (
            "Dictionary word counts over the whole article body, positive minus "
            "negative, not a stance on the project."
        ),
    }


# --------------------------------------------------------------------------
# Landing it on a SiteContext
# --------------------------------------------------------------------------


def apply_to(site, signal: LocalSignal) -> object:
    """Record the news signal on a pathway.SiteContext without overwriting it.

    Deliberately writes only to `site.provenance["local_news"]`. It does not
    touch `site.moratorium`, `site.moratorium_note` or `site.zoning_posture`,
    because those come from `ingest/counties.json`, which was read from a
    primary source before it was typed. A headline is not a primary source.

    Where the two disagree the record wins and `recheck` is set, which is the
    honest division of labour: the hand file decides the answer, the news signal
    decides what to go re-read.
    """
    entry = {
        "source": "GDELT DOC 2.0 + Bing News RSS (both keyless)",
        "fetched": signal.fetched,
        "posture": signal.posture.value,
        "confidence": signal.confidence,
        "stories": signal.story_count,
        "articles": signal.article_count,
        "baseline_articles": signal.baseline_articles,
        "coverage_share": signal.coverage_share,
        "trend": signal.trend.direction,
        "thin_media": signal.thin_media,
        "evidence": signal.evidence,
        "links": [{"headline": i.headline, "publication": i.publication, "url": i.url} for i in signal.items[:8]],
        "no_data": signal.no_data,
        "note": signal.as_note(),
    }

    hand = getattr(site, "zoning_posture", None)
    hand_moratorium = bool(getattr(site, "moratorium", False))
    expected = expected_posture(hand, hand_moratorium)
    if not signal.no_data and expected is not None and expected is not signal.posture:
        entry["recheck"] = (
            f"The hand-entered record says {hand or 'unknown'}"
            + (" with a moratorium in effect" if hand_moratorium else "")
            + f", which reads as {expected.value}. The local news signal says "
            f"{signal.posture.value}. The hand record is what the pathway uses. "
            f"This is a prompt to re-read the source, not a correction."
        )
    site.provenance["local_news"] = entry
    return site


def expected_posture(zoning_posture: str | None, moratorium: bool) -> Posture | None:
    """Map a hand-entered county record onto the news posture scale.

    The two scales measure different things — one is what the county has enacted,
    the other is what the press printed — so this is a coarse crosswalk and it is
    only used to decide whether the two agree well enough to leave alone.

      moratorium in effect      -> formal_action
      hostile, no moratorium    -> formal_action  (a denial or an ordinance change
                                   is a board action and gets reported as one)
      special-exception         -> organised_opposition  (a discretionary regime
                                   exists because somebody argued for it)
      by-right                  -> active_interest or quieter
    """
    if moratorium:
        return Posture.FORMAL_ACTION
    return {
        "hostile": Posture.FORMAL_ACTION,
        "special-exception": Posture.ORGANISED_OPPOSITION,
        "by-right": Posture.ACTIVE_INTEREST,
    }.get(zoning_posture or "")


# --------------------------------------------------------------------------
# Reconciliation against the hand-entered file
# --------------------------------------------------------------------------


@dataclass
class Reconciliation:
    """One county: what was typed by hand, and what the press says now."""

    fips: str
    county: str
    state: str
    hand_posture: str
    hand_moratorium: bool
    hand_entered: str
    expected: str
    signal: LocalSignal

    @property
    def agrees(self) -> bool:
        return not self.signal.no_data and self.signal.posture.value == self.expected

    @property
    def direction(self) -> str:
        """Which way the disagreement runs. `hotter` means the press is reporting
        more activity than the record implies, which is the case that suggests
        the record is stale."""
        if self.agrees or self.signal.no_data:
            return "-"
        expected = Posture(self.expected)
        if self.signal.posture.rank > expected.rank:
            return "hotter"
        return "cooler"


def reconcile(
    since_days: int = 180,
    *,
    use_cache: bool = True,
    only: list[str] | None = None,
) -> list[Reconciliation]:
    """Run the signal against every county in ingest/counties.json.

    This is the calibration. If the news signal reproduces the hand-entered
    postures, both are worth something. If it does not, the reconciliation says
    which record to re-read and which signal to distrust.
    """
    from . import counties as counties_module

    rows: list[Reconciliation] = []
    for fips, record in sorted(
        counties_module.load().items(), key=lambda kv: (kv[1]["state"], kv[1]["county"])
    ):
        if only and fips not in only:
            continue
        signal = signals_for_county(
            record["county"], record["state"], since_days, fips=fips, use_cache=use_cache
        )
        expected = expected_posture(record["zoning_posture"], record["moratorium"])
        rows.append(
            Reconciliation(
                fips=fips,
                county=record["county"],
                state=record["state"],
                hand_posture=record["zoning_posture"],
                hand_moratorium=bool(record["moratorium"]),
                hand_entered=record["entered"],
                expected=expected.value if expected else "-",
                signal=signal,
            )
        )
    return rows


def _print_reconciliation(rows: list[Reconciliation]) -> None:
    header = (
        f"{'FIPS':6} {'County':16} {'ST':3} {'hand':17} {'M':2} {'expected':21} "
        f"{'news signal':21} {'conf':7} {'st':3} {'base':5} {'share':6} {'trend':8} agree"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        s = row.signal
        share = f"{s.coverage_share:.1%}" if s.coverage_share is not None else "-"
        print(
            f"{row.fips:6} {row.county[:16]:16} {row.state:3} {row.hand_posture:17} "
            f"{'Y' if row.hand_moratorium else 'n':2} {row.expected:21} "
            f"{s.posture.value:21} {s.confidence:7} {s.story_count:<3} "
            f"{s.baseline_articles:<5} {share:6} {s.trend.direction:8} "
            f"{'yes' if row.agrees else row.direction}"
        )

    agreed = sum(1 for r in rows if r.agrees)
    nodata = sum(1 for r in rows if r.signal.no_data)
    print()
    print(f"{agreed}/{len(rows)} agree. {nodata} returned no data.")
    hotter = [r for r in rows if r.direction == "hotter"]
    cooler = [r for r in rows if r.direction == "cooler"]
    if hotter:
        print(f"\nPress hotter than the record ({len(hotter)}) — re-read these:")
        for r in hotter:
            print(f"  {r.county}, {r.state}: record {r.expected} (entered {r.hand_entered}), "
                  f"press {r.signal.posture.value} at {r.signal.confidence} confidence")
    if cooler:
        print(f"\nPress cooler than the record ({len(cooler)}) — signal is probably thin, not the record:")
        for r in cooler:
            print(f"  {r.county}, {r.state}: record {r.expected}, press "
                  f"{r.signal.posture.value}, {r.signal.story_count} stories, "
                  f"baseline {r.signal.baseline_articles}"
                  + (" (thin media market)" if r.signal.thin_media else ""))


def main() -> None:  # pragma: no cover
    import argparse

    try:
        from dotenv import load_dotenv

        load_dotenv(".env", override=False)
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Local news opposition signal.")
    parser.add_argument("county", nargs="?", help="County name, e.g. Loudoun")
    parser.add_argument("state", nargs="?", help="Two-letter state code")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--fips")
    parser.add_argument("--reconcile", action="store_true", help="Run all 27 hand-entered counties")
    parser.add_argument("--tone", action="store_true", help="Also fetch the GDELT tone distribution")
    parser.add_argument("--fresh", action="store_true", help="Ignore the response cache")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.reconcile:
        rows = reconcile(args.days, use_cache=not args.fresh)
        if args.json:
            print(
                json.dumps(
                    [
                        {
                            "fips": r.fips,
                            "county": r.county,
                            "state": r.state,
                            "hand_posture": r.hand_posture,
                            "hand_moratorium": r.hand_moratorium,
                            "expected": r.expected,
                            "news_posture": r.signal.posture.value,
                            "confidence": r.signal.confidence,
                            "stories": r.signal.story_count,
                            "headline_named": r.signal.headline_named,
                            "articles": r.signal.article_count,
                            "baseline": r.signal.baseline_articles,
                            "share": r.signal.coverage_share,
                            "trend": r.signal.trend.direction,
                            "thin_media": r.signal.thin_media,
                            "agrees": r.agrees,
                            "direction": r.direction,
                            "evidence": r.signal.evidence,
                            "items": [
                                {
                                    "headline": i.headline,
                                    "publication": i.publication,
                                    "published": i.published,
                                    "url": i.url,
                                    "summary": i.summary,
                                    "also_reported_by": list(i.also_reported_by),
                                }
                                for i in r.signal.items
                            ],
                        }
                        for r in rows
                    ],
                    indent=1,
                )
            )
        else:
            _print_reconciliation(rows)
        return

    if not args.county or not args.state:
        parser.error("give a county and a state, or --reconcile")

    signal = signals_for_county(args.county, args.state, args.days, fips=args.fips, use_cache=not args.fresh)
    print(signal.describe())
    print()
    for line in signal.evidence:
        print(f"  {line}")
    if signal.items_window_note:
        print(f"\n  {signal.items_window_note}")
    print()
    for item in signal.items:
        print(f"  {item.line()}")
        if item.summary:
            print(f"     {item.summary[:160]}")
        print(f"     {item.url}")
    if args.tone:
        tone = tone_for_county(args.county, args.state, args.days, fips=args.fips)
        print(f"\n  tone: {tone}")
    if status().failures:
        print(f"\n  fetch problems: {status().failures}")


if __name__ == "__main__":  # pragma: no cover
    main()
