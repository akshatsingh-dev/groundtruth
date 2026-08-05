# Local news opposition signal — engineering note

`ingest/localnews.py`. Verified 5 August 2026.

Data Center Watch counts 833 active opposition groups across 49 states, up from
396 at the end of 2025, and 75 projects worth about $130B blocked or delayed in
Q1 2026 alone. Opposition is the leading indicator. It appears in a county
newspaper and on a board agenda months before it appears in a permit denial.

`ingest/counties.json` is 27 records typed by hand from a primary source. It is
accurate and it does not move. This module is the moving part: it reads what the
local press has published about data centers in any county, derives a posture
from it, and says what evidence drove the call.

It does not replace the hand file. Where the two disagree the hand file wins,
because it was checked against a board minute or an official announcement. The
news signal flags the record for re-reading. That is implemented in `apply_to`,
which writes only to `SiteContext.provenance["local_news"]` and never touches
`moratorium`, `moratorium_note` or `zoning_posture`.

---

## 1. The source

Four candidates were tested against live traffic. Two are in.

| Source | Key needed | Verdict |
|---|---|---|
| **GDELT DOC 2.0** | none | **In.** Volume, trend, media-market baseline, articles. |
| **Bing News RSS** | none | **In.** Real one-line summaries and publication names. |
| Google News RSS | none | Out. Answers, but useless for this. |
| CommonCrawl news / county agenda pages | none | Out of scope. See below. |

### GDELT DOC 2.0 — `https://api.gdeltproject.org/api/v2/doc/doc`

No key, no registration, no account. Two modes are used.

`mode=timelinevolraw` returns a raw article count per day for the whole
requested window, plus `norm`, the total number of articles GDELT monitored that
day. It is not capped. Linn County, Iowa over 180 days came back as 177 daily
points totalling 69 articles, with the monthly shape
Feb 9 / Mar 13 / Apr 5 / May 9 / Jun 9 / **Jul 21** — the July spike is the
1 July 2026 moratorium vote. This is where volume and trend come from.

`mode=artlist` returns the individual articles: `url`, `title`, `domain`,
`seendate`. It is capped at 250 records and, in testing, reached back only about
90 days no matter what window was requested — the same Linn query that produced
a 177-day volume series returned articles from 12 May onward and nothing before.
So the volume series and the article list cover different windows, and
`LocalSignal.items_window_note` says so on every result. An action five months
old shows in the counts and not in the links.

`mode=tonechart` also works and is exposed as `tone_for_county()`. It is opt-in
and nothing in the posture reads it. Section 7 explains why.

**Rate limit.** One request every five seconds, per IP, and the enforcement is a
leaky bucket rather than a fixed window — a burst that respects five seconds
still gets refused, and once refused the IP stays refused for a while. The
refusal is a plain-text body (`Please limit requests to one every 5 seconds...`)
served sometimes with HTTP 429 and sometimes with HTTP 200. The module checks the
body as well as the status, because a 200 with that body parsed as "no articles"
would have printed `quiet` for every county. `GDELT_MIN_INTERVAL` is 10 seconds
with six retries on a linear backoff. A cold 27-county reconciliation takes about
25 minutes. A warm one is instant, which is why the cache is not optional.

**Two query-syntax refusals worth knowing**, both of which arrive as plain text
on an HTTP 200:

- `Parentheses may only be used around OR'd statements.` A single-element group
  such as `("Linn County")` is rejected. `_or_group()` emits the bare phrase
  when there is one alternative. Before that fix every single-name county
  returned zero articles and read as quiet.
- `The specified phrase is too short.` A quoted two- or three-character phrase
  such as `"Md."` is rejected, which is why state disambiguation uses the full
  state name and not the postal abbreviation.

### Bing News RSS — `https://www.bing.com/news/search?...&format=RSS`

No key. Returns five to ten items per query with, per item: a real headline, a
real one-line snippet drawn from the article, a real `pubDate`, and the
publication display name in `News:Source`. The `link` is a
`bing.com/news/apiclick.aspx` redirect with the true article URL sitting in its
`url` query parameter, which `_unwrap_bing()` extracts so the link a human clicks
goes to the newspaper rather than to Microsoft.

This is the only source of the one-line summaries. GDELT does not return one and
nothing in this module writes one.

### Google News RSS — rejected

`https://news.google.com/rss/search?q=...` answers, keylessly, with correct
headlines and a `<source>` element carrying the publication name. It was
rejected on two counts:

- Its `<description>` is the headline wrapped in an anchor tag, not a summary.
  Shipping it as a summary would have been presenting the headline twice.
- Its `<link>` is an opaque `news.google.com/rss/articles/CBMi...` redirect. It
  resolves in a browser, but the stored artefact does not name the publisher and
  cannot be checked without following it.

Bing does both of those things properly, so there was no reason to carry Google
as well.

### Not attempted

Individual county newspaper RSS feeds would be the highest-precision source and
the worst engineering trade: 3,140 counties, no registry of which paper covers
which, and every feed a separate breakage. County agenda and minutes pages are
the true primary source, and they are what `ingest/counties.json` was typed from
by hand. Automating them is a per-county scraper against Granicus, CivicPlus,
Legistar and a long tail of hand-rolled PHP. Both are the right next step and
neither is a keyless national query today.

---

## 2. Query construction

Three GDELT calls and one Bing call per county.

```
signal    "<County> County" <State> ("data center" OR "data centers"
                                     OR "data centre" OR datacenter)
                                     sourcecountry:US        [timelinevolraw]
                                                             [artlist, 250]
baseline  "<County> County" <State> sourcecountry:US         [timelinevolraw]
bing      "<County> County" <State> "data center"
```

**The state name is required, and it is the single biggest precision fix in the
module.** County names repeat. Measured 5 August 2026, 180-day windows:

| Query | Articles |
|---|---:|
| `"Montgomery County"` + data centre terms | 275 |
| `"Montgomery County" Maryland` + same | **60** |
| `"Marshall County"` + same | 35 |
| `"Marshall County" Indiana` + same | **9** |
| `"Linn County"` + same | 79 |
| `"Linn County" Iowa` + same | **69** |
| `"Loudoun County"` + same | 259 |
| `"Loudoun County" Virginia` + same | **228** |

Montgomery County exists in eighteen states; without the state clause 78% of its
hits are somewhere else. Marshall loses 74%. On a name that is already unique the
clause costs real recall — Loudoun drops 31 articles that are local coverage
never using the word Virginia — and it is applied anyway, uniformly, to the
baseline query as well as the signal query. Two reasons: counts have to be
comparable across counties, and because both halves of `coverage_share` carry the
same clause, most of the bias divides out.

**The wider term list was tested and moved to classification.** The brief lists
"moratorium", "rezoning", "special exception", "board of supervisors", "planning
commission", "substation" and "gas turbine". Added as OR alternatives at query
level on Linn County IA they took the 180-day count from 69 to 98, and the 29
extra articles were county board coverage with no data center in them. Those
terms discriminate when run over a returned headline and dilute when run as query
alternatives, so that is where they are: `_ACTION_TERMS`, `_OPPOSITION_TERMS`,
`_PROCEEDING_TERMS`, `_INFRA_TERMS`, matched against headline plus feed summary.

**Name variants.** `_county_phrases()` emits `"Prince George's County"` and
`"Prince Georges County"`, because the apostrophe is straight, curly or absent
depending on the paper's CMS and GDELT indexes what it was handed. Consolidated
city-counties are keyed on FIPS: Broomfield CO gets `"Broomfield County"`,
`"City and County of Broomfield"` and `"Broomfield"`, because a county whose name
never appears as "X County" would otherwise return nothing. Louisiana gets Parish
and Alaska gets Borough.

---

## 3. Deduplication

Local news syndicates hard. Counting URLs turns one board vote into six data
points, and the posture floors are counts, so this is load-bearing rather than
cosmetic.

Two items are the same story if any of:

1. **Same canonical URL.** Scheme, `www.` and query string stripped.
2. **Identical normalised headline**, at any distance in time. A weekly running
   the wire item eleven days late is not a second vote.
3. **Jaccard ≥ 0.6 on stemmed headline tokens, within 14 days.**

Normalisation strips a dateline prefix (`[LINN COUNTY, Iowa] —`), a masthead
suffix (` - Bisnow`), punctuation and case, then drops stopwords and words of two
characters or fewer, then applies a crude suffix stemmer (`-ing`, `-ies`, `-ed`,
`-es`, `-s`).

Both the stemmer and the 14-day window were forced by one real cluster — the
Prince George's County two-year moratorium, voted 7 July 2026:

| Masthead | Date | Headline |
|---|---|---|
| NBC4 Washington on MSN | 7 Jul | Prince George's County Council passes 2-year moratorium on new data centers |
| wtop.com | 7 Jul | Prince George's County Council passes two-year moratorium on data centers |
| Patch on MSN | 8 Jul | 2-year data center moratorium passed by Prince George's County Council |
| Afro | 18 Jul | Prince George's County Council passes two-year moratorium on data centers |

Without stemming, `passes`/`passed` and `centers`/`center` drop the Patch item to
0.55 Jaccard against NBC4 and it stays separate. Without the 14-day window the
Afro item splits off on its date. With both, **four URLs collapse to one story**,
and the three other mastheads are kept on the representative as
`also_reported_by` so the collapse is auditable rather than invisible.

Two bugs found in that same cluster and fixed:

- The masthead-suffix regex allowed zero whitespace around the separator, so it
  ate `two-year moratorium on data centers` off the end of a headline — a
  compound adjective is not a masthead. It now requires whitespace on both sides.
- Representative selection prefers an item that carries a summary, then a
  non-national domain, then the earliest date, which is usually the paper that
  did the reporting rather than the aggregator that picked it up.

A separate precision filter runs after dedup. `_names_another_county()` drops a
story whose **headline** names a county that is not ours. GDELT matches the
article body, so a regional paper writing about the county next door is a hit
whenever it mentions ours in passing. On Linn County IA that was pulling in
"Johnson County proposes stricter data center ordinance" and "Clayton County
Supervisors hold information session on Bitcoin data center", both of which would
otherwise have counted as board-action evidence for Linn. The count of dropped
stories is reported in the evidence.

---

## 4. Posture rules and their thresholds

Four values, ordered: `quiet`, `active_interest`, `organised_opposition`,
`formal_action`. All thresholds live in `POSTURE_RULES` in the module so this
document and the code cannot drift.

Everything below counts **deduplicated stories**, and `headline_named` counts
stories whose headline contains the county name.

| Posture | Floor | Why that floor |
|---|---|---|
| `formal_action` | ≥ 2 stories with board-action language, ≥ 1 of them naming the county in its headline | Two rather than one, because a syndicated roundup naming six counties would otherwise promote all six. The headline requirement is the guard against a statewide story mentioning the county once. |
| `organised_opposition` | ≥ 3 stories total **and** ≥ 2 carrying opposition language | **One article is not organised opposition.** Two articles about the same hearing collapse to one story in dedup before this is counted, so three stories is three events or three outlets doing independent work. |
| `active_interest` | ≥ 2 stories, no floor cleared above | Coverage exists, nothing in it reads as opposition or as a board acting. |
| `quiet` | fewer than 2 stories, **or no data** | Not a finding of no opposition. See section 6. |

Classification runs over the headline plus, where a feed supplied one, the
one-line summary. Not over the article body, which is never fetched. "The
headline said moratorium" and "the article is about a moratorium" are different
claims and only the first one is being made.

Every returned posture carries the evidence string that produced it, including
the count that cleared the floor and up to three of the stories that drove it.

**Confidence** is separate from posture:

- `none` — no data.
- `low` — fewer than 3 stories, or no story names the county in a headline, or a
  fetch failed part-way, or `quiet` in a thin media market.
- `medium` — ≥ 3 stories with ≥ 1 headline naming the county.
- `high` — ≥ 5 stories, ≥ 2 headline mentions, and enough volume to call a trend.

A partial fetch forces `low` and appends the failure to the evidence, because a
rate-limited article list makes the story count a floor and the posture
under-read.

**Trend** compares the first half of the window to the second, from the daily
volume series, which covers the full window and is not subject to the 250-record
item cap. Rising at a ratio ≥ 1.5, falling at ≤ 0.67, flat between, and `unknown`
below 4 articles total — a 1-to-3 split is not a direction.

---

## 5. The media-market problem

A county with five newspapers generates more articles than a county with one.
That is a media-market artifact and it is not a posture difference. Left alone it
would rank a well-covered permissive county above a barely-covered hostile one.

The normaliser is a second query: the county name and state with no data-center
terms at all. That is the denominator — everything published about this county in
the same window, through the same crawler, with the same state clause.

```
coverage_share = signal_articles / baseline_articles
```

Linn County, Iowa: 79 data-center articles against 956 mentioning the county at
all, so data centers were 8.3% of what was written about Linn County over 180
days. That number is comparable across counties. The raw 79 is not.

Below `THIN_MEDIA_BASELINE = 30` baseline articles the county is marked
`thin_media`, the evidence says so explicitly, and a `quiet` posture in a thin
market is capped at `low` confidence. A county nobody covers must not read as a
county with nothing happening.

Two things the share does not fix. Baseline coverage is itself uneven — a county
containing a large city gets more of everything, and its share denominator is
inflated by sport and crime. And GDELT's crawl is domain-weighted in ways nobody
outside GDELT can see. The share is a correction, not a control.

---

## 6. No data is not no opposition

Hard requirement, implemented three ways.

**Corrected 5 Aug after the source went down.** The failure path used to return
`posture=quiet` with the reason set in prose. `QUIET` means "no data center
coverage found in this county". A failed fetch means "we could not look". Those
are different facts and only one is a finding, and every consumer downstream
reads the enum rather than the prose, so a county whose source timed out was
indistinguishable from a county with no opposition and sorted to the permissive
end of the scale.

`Posture.UNKNOWN` is now a member in its own right, with `rank == -1`,
deliberately off the 0-3 scale so any comparison involving it is visibly a bug
rather than a quiet mis-sort. The failure path returns `UNKNOWN` when
`_status.ok` is false and `QUIET` only when a fetch genuinely succeeded and found
nothing. `tests/test_localnews.py` pins it.

With no network and no keys, `signals_for_county()` returns
`posture=unknown, no_data=True, confidence=none` and a `reason` naming the failure.
`describe()` renders it as *"Posture is reported as quiet because there is
nothing to report, not because the county is quiet."* `as_note()` ends with
*"This is not a finding of no opposition."* The `get_local_signal` tool
description tells the model the same thing in the same words.

A real zero — the fetch worked and there were no articles — is a different
string, and it splits on the baseline: either the county is covered and data
centers are not the subject, or the county is barely covered at all and absence
proves nothing.

Nothing in this module raises. A refused geocode, an unreachable host, a rate
limit, a malformed body and an unparseable RSS document all produce a signal with
a reason attached.

---

## 7. What GDELT tone actually measures

`tone_for_county()` exists, returns a distribution and a mean, and **nothing in
`Posture` reads it.**

GDELT tone is not a stance model. For each article it counts words appearing in
its positive and negative emotion dictionaries across the **whole article body**
and reports roughly (percent positive words − percent negative words). It does
not know what the article is about, who is opposing what, or whether the negative
words belong to the data center or to something else on the page.

That last failure is not hypothetical. A `tonechart` query for Linn County plus
data-center terms put *"Man cited after driver injured in rear-end crash in rural
Cedar Rapids"* in the −5 bin. The article scores negative because a car crash is
negative. It tells you nothing about a data center.

There is also a directional confound that would matter even with a perfect
crawler: coverage of organised opposition scores negative because words like
"opposition", "concerns" and "fight" are negative, and coverage of a project
being welcomed scores positive. So tone partly tracks the thing we want and
partly tracks the emotional register of local journalism, and there is no way to
separate them from the histogram.

It is exposed because it is cheap context on a page a human is already reading.
It is not in the posture rules because it is not a measurement of opposition.

---

## 8. Reconciliation against the 27 hand-entered counties

**This has not run. Do not claim that it has.**

The reconciliation is the calibration that would tell you whether the signal is
worth anything: run it against all 27 hand-typed records and count agreement.
Agreement validates both. Disagreement means either a stale record or a noisy
signal, and looking at which is the whole exercise.

It did not happen because GDELT stopped answering from this machine partway
through the build. A single county query ran **4,820 seconds** before failing on
`_ssl.c:983: The handshake operation timed out`. That is a reachability failure,
not the documented rate limit, which returns a plain-text "Please limit requests"
body that this module already handles.

Individual county queries did work earlier in the session, which is where the
Linn County figures in sections 1, 5 and 7 came from. So the module is validated
per-county and unvalidated in aggregate.

To run it when the source is back:

```bash
python -m ingest.localnews --reconcile
```

Budget roughly a minute per county before retries, so about 30 minutes cold. It
caches, so a second pass is free. Until it has run, treat the news layer as
instrumentation rather than evidence, and keep `ingest/counties.json` as the
authority it already is.

---

## 9. What this can and cannot tell you

**Can:**

- Tell you a county that is not in the hand file is generating data-center
  coverage, and hand you the links.
- Tell you whether that coverage is rising or falling over six months, from a
  daily series that covers the full window.
- Separate one syndicated story from six mastheads, so the counts mean something.
- Normalise volume against how much the county gets covered at all, so a
  one-newspaper county is not scored as quiet for being a one-newspaper county.
- Point at a hand-entered record whose press activity no longer matches what was
  typed, which is a list of things to go re-read.

**Cannot:**

- Tell you an ordinance exists. It can tell you a newspaper said one passed.
  Those are different, and `ingest/counties.json` holds the second kind.
- See a board packet, a planning commission agenda or a staff report. Those are
  the primary sources and they are not in any keyless national feed.
- See coverage GDELT does not crawl, or anything behind a paywall it cannot
  read. Absence in GDELT is absence in GDELT.
- Distinguish organised opposition from a single loud reporter. The floors make
  that error less likely; they do not make it impossible.
- Reach further back than about 90 days for individual articles, even though the
  volume series reaches the full window.
- Be quoted as a fact. It is a label, a confidence, and a list of links, and the
  links are the part that is true.
