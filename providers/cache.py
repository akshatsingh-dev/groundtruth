"""SQLite cache for provider HTTP responses.

The national sweep is roughly 3,140 counties at ~110 credits each, and we will
run it more than once before Monday. Without a cache the second run costs the
same as the first, in money and in wall clock. With one it costs nothing, which
means we can iterate on the scoring logic without re-buying the data.

The cache key is (endpoint, canonical JSON of the request params). Canonical
means sorted keys and floats rounded to six decimal places — six places is about
11 cm, so two coordinates that round the same are the same place, and a sweep
that regenerates its candidate grid with a slightly different float does not
miss every entry.

What goes in: the raw response body, the HTTP status, when we fetched it, and
the credit cost if we know one. Storing the raw body rather than a parsed object
matters because parsing is the part most likely to be wrong before the key
arrives — when a shape assumption turns out incorrect we fix the parser and
re-run against cached bytes, for free.

Thread safety: one connection per thread (SQLite connections are not shareable
across threads) plus WAL mode, which lets readers run while a writer commits. A
lock guards the in-memory counters only. Sized for a ThreadPoolExecutor of ~8.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

DEFAULT_PATH = os.path.join("data", "cache.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    key         TEXT PRIMARY KEY,
    endpoint    TEXT NOT NULL,
    params_json TEXT NOT NULL,
    status      INTEGER NOT NULL,
    body_json   TEXT NOT NULL,
    credits     REAL,
    fetched     TEXT NOT NULL,
    created_ts  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_responses_endpoint ON responses(endpoint);
CREATE INDEX IF NOT EXISTS idx_responses_created  ON responses(created_ts);
"""


def _round_floats(obj: Any, places: int = 6) -> Any:
    """Round every float in a nested structure so cache keys are stable.

    A latitude that arrives as 30.1996990000001 on one run and 30.199699 on the
    next is the same parcel. Without this the cache misses on float noise, which
    is the failure mode that quietly makes a cache look useless.
    """
    if isinstance(obj, float):
        return round(obj, places)
    if isinstance(obj, dict):
        return {k: _round_floats(v, places) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, places) for v in obj]
    return obj


def canonical(params: Any) -> str:
    """Deterministic JSON for a request body. Sorted keys, no incidental spacing."""
    return json.dumps(
        _round_floats(params),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def cache_key(endpoint: str, params: Any) -> str:
    return hashlib.sha256(f"{endpoint}\x00{canonical(params)}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CachedResponse:
    """One stored response. `age_days` is how stale it is right now."""

    endpoint: str
    status: int
    body: Any
    credits: float | None
    fetched: str
    created_ts: float

    @property
    def age_days(self) -> float:
        return (time.time() - self.created_ts) / 86400.0

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class ResponseCache:
    """Keyed cache of raw provider responses, backed by SQLite.

    `hits` and `misses` are per-process counters for this run. `credits` totals
    are read from the database, so they survive restarts and describe everything
    the cache has ever paid for, not just this session.
    """

    def __init__(self, path: str = DEFAULT_PATH, default_max_age_days: float | None = None):
        self.path = path
        self.default_max_age_days = default_max_age_days
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)

        self._local = threading.local()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._writes = 0
        self._credits_this_run = 0.0

        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # -- connection handling -------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """One connection per thread. SQLite objects are not thread-shareable.

        WAL lets the 8 reader threads keep reading while one commits, and a
        30 s busy timeout means a contended write waits rather than raising
        'database is locked' halfway through a sweep.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def close(self) -> None:
        """Close this thread's connection. Other threads keep their own."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # -- read / write --------------------------------------------------------

    def get(
        self,
        endpoint: str,
        params: Any,
        max_age_days: float | None = None,
    ) -> CachedResponse | None:
        """Return a stored response, or None on a miss or an expired entry.

        `max_age_days` overrides the instance default. Mireye publishes a
        `ttl_seconds` hint per field (a year for elevation, a day for FEMA
        flood); callers that care can pass the tighter number through.
        """
        key = cache_key(endpoint, params)
        row = self._connect().execute(
            "SELECT endpoint, status, body_json, credits, fetched, created_ts "
            "FROM responses WHERE key = ?",
            (key,),
        ).fetchone()

        if row is None:
            with self._lock:
                self._misses += 1
            return None

        limit = max_age_days if max_age_days is not None else self.default_max_age_days
        if limit is not None and (time.time() - row["created_ts"]) > limit * 86400.0:
            with self._lock:
                self._misses += 1
            return None

        with self._lock:
            self._hits += 1
        return CachedResponse(
            endpoint=row["endpoint"],
            status=row["status"],
            body=json.loads(row["body_json"]),
            credits=row["credits"],
            fetched=row["fetched"],
            created_ts=row["created_ts"],
        )

    def set(
        self,
        endpoint: str,
        params: Any,
        status: int,
        body: Any,
        credits: float | None = None,
    ) -> None:
        """Store a response.

        Callers decide what is worth storing. A transient 429 or 502 must not be
        cached — it would freeze a temporary failure into a permanent one. A
        404 address_too_coarse is a stable refusal and should be, so we do not
        pay to rediscover the same bad address on every re-run.
        """
        key = cache_key(endpoint, params)
        now = time.time()
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO responses "
                "(key, endpoint, params_json, status, body_json, credits, fetched, created_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    endpoint,
                    canonical(params),
                    int(status),
                    json.dumps(body, ensure_ascii=False, default=str),
                    float(credits) if credits is not None else None,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    now,
                ),
            )
        with self._lock:
            self._writes += 1
            if credits:
                self._credits_this_run += float(credits)

    def delete(self, endpoint: str, params: Any) -> bool:
        """Drop one entry. Used when a cached body turns out to be unparseable."""
        conn = self._connect()
        with conn:
            cur = conn.execute(
                "DELETE FROM responses WHERE key = ?", (cache_key(endpoint, params),)
            )
        return cur.rowcount > 0

    # -- housekeeping --------------------------------------------------------

    def purge(self, older_than_days: float) -> int:
        """Delete entries older than N days. Returns the number removed.

        Mireye's own guidance is a 24 h response cache upstream and a per-field
        `ttl_seconds` hint that runs from a day (FEMA flood) to a year
        (elevation). Purging at 30 days is a reasonable middle for a screen that
        gets re-run weekly; purging at 1 forces a fresh read of the fast-moving
        fields before a submission.
        """
        conn = self._connect()
        cutoff = time.time() - older_than_days * 86400.0
        with conn:
            cur = conn.execute("DELETE FROM responses WHERE created_ts < ?", (cutoff,))
        deleted = cur.rowcount
        if deleted:
            conn.execute("VACUUM")
        return deleted

    def stats(self) -> dict:
        """Hit rate for this run, plus everything the cache has ever paid for.

        `credits_spent` is the sum over stored rows: what the data in this file
        cost. `credits_spent_this_run` is what this process paid — the gap
        between the two is what the cache saved.
        """
        row = self._connect().execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(credits), 0) AS credits, "
            "MIN(created_ts) AS oldest, MAX(created_ts) AS newest "
            "FROM responses"
        ).fetchone()

        by_endpoint = {
            r["endpoint"]: {"entries": r["n"], "credits": r["credits"]}
            for r in self._connect().execute(
                "SELECT endpoint, COUNT(*) AS n, COALESCE(SUM(credits), 0) AS credits "
                "FROM responses GROUP BY endpoint ORDER BY n DESC"
            )
        }

        with self._lock:
            hits, misses, writes = self._hits, self._misses, self._writes
            run_credits = self._credits_this_run

        lookups = hits + misses
        return {
            "path": self.path,
            "entries": row["n"],
            "hits": hits,
            "misses": misses,
            "hit_rate": (hits / lookups) if lookups else 0.0,
            "writes_this_run": writes,
            "credits_spent": row["credits"],
            "credits_spent_this_run": run_credits,
            "credits_saved_this_run": max(0.0, row["credits"] - run_credits) if hits else 0.0,
            "oldest_entry_age_days": (
                (time.time() - row["oldest"]) / 86400.0 if row["oldest"] else None
            ),
            "newest_entry_age_days": (
                (time.time() - row["newest"]) / 86400.0 if row["newest"] else None
            ),
            "by_endpoint": by_endpoint,
        }

    def summary(self) -> str:
        s = self.stats()
        return (
            f"cache {s['path']}: {s['entries']:,} entries, "
            f"{s['hits']:,} hits / {s['misses']:,} misses "
            f"({s['hit_rate']:.0%} hit rate), "
            f"{s['credits_spent']:,.0f} credits stored, "
            f"{s['credits_spent_this_run']:,.0f} spent this run"
        )


def main() -> None:
    """Report on the cache without touching the network. `python -m providers.cache`."""
    import argparse

    parser = argparse.ArgumentParser(description="Inspect or purge the response cache.")
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument(
        "--purge",
        type=float,
        metavar="DAYS",
        help="delete entries older than DAYS and exit",
    )
    args = parser.parse_args()

    cache = ResponseCache(args.path)
    if args.purge is not None:
        removed = cache.purge(args.purge)
        print(f"purged {removed:,} entries older than {args.purge} days")

    stats = cache.stats()
    print(cache.summary())
    for endpoint, detail in stats["by_endpoint"].items():
        print(f"  {endpoint:26s} {detail['entries']:>7,} entries  {detail['credits']:>10,.0f} credits")


if __name__ == "__main__":
    main()
