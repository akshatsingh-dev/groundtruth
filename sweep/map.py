"""The national artifact — every US county, coloured by days until legal power.

Reads ``data/county_scores.json`` and writes one self-contained HTML file. No
CDN, no fonts, no runtime fetch, no build step. Open it from a USB stick on a
plane in a year and it still works, because everything it needs is inside it.

How it is built
---------------
1.  Census cartographic boundary shapefile, 1:5,000,000, 2025 vintage. Parsed
    with a ~60 line reader in this file rather than a GIS stack — the .shp
    format is a header and a run of little-endian doubles.
2.  Projected to the Albers USA composite in Python, not in the browser. The
    page ships screen coordinates, so there is no trigonometry, no projection
    library and no math to get wrong at render time.
3.  Simplified with Ramer-Douglas-Peucker *in projected pixel space*, so the
    tolerance means the same thing in Maine and in Nevada. Simplifying in
    degrees over-smooths the north and under-smooths the south.
4.  Emitted as inline SVG ``<path>`` elements with relative integer coordinates
    on a 10x grid. The map is in the markup, so it renders with JavaScript
    disabled. JavaScript only adds the hover layer.

Colour
------
One hue, light to dark, on a five-step ordinal ramp keyed to days. Not a
rainbow, and not categorical-by-pathway: the pathway is *ordinal* here (minor
NSR is strictly easier than PSD, which is strictly easier than nonattainment
NSR), so an ordered ramp encodes it correctly and the pathway boundary falls
out of the data. Counties with no attainment data get a neutral hatch, never a
ramp step — an unknown is not a low value.

Both ramps are validated: monotone lightness, adjacent lightness gap >= 0.06,
light-end contrast >= 2:1 against the surface, single hue. Dark mode uses its
own steps against the dark surface rather than an automatic inversion, with the
anchor flipped so "few days" still recedes toward the surface.

Usage
-----
    python -m sweep.map
    python -m sweep.map --tolerance 0.6 --out outputs/county_map.html

Writes:
    outputs/county_map.html    the artifact
    outputs/county_map.svg     the same map, static, for PNG export
    outputs/county_extremes.md fastest and slowest counties, for the thread
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sweep.counties import (
    GAZETTEER_URL,
    OUTPUT_PATH,
    RAW,
    ROOT,
    _download,
    extremes,
)

DEG = math.pi / 180.0

CB_COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_5m.zip"
CB_STATE_URL = "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_state_5m.zip"
CB_VINTAGE = "2025 Census cartographic boundary files, 1:5,000,000"

#: Frame. Same geometry as the standard d3 Albers USA layout, extended 20px at
#: the bottom so Puerto Rico and the Hawaii inset are not clipped.
FRAME_W, FRAME_H = 975.0, 630.0
SCALE = 1300.0
TRANSLATE = (487.5, 305.0)
GRID = 10  # coordinates are emitted as integers on a 10x grid


# --------------------------------------------------------------------------
# Shapefile
# --------------------------------------------------------------------------


def _read_dbf(payload: bytes) -> list[dict[str, str]]:
    """dBASE III attribute table. Fixed-width character fields, no surprises."""
    count, header_len, record_len = struct.unpack("<IHH", payload[4:12])
    fields: list[tuple[str, int]] = []
    offset = 32
    while payload[offset] != 0x0D:
        descriptor = payload[offset : offset + 32]
        fields.append((descriptor[:11].split(b"\x00")[0].decode(), descriptor[16]))
        offset += 32
    rows: list[dict[str, str]] = []
    for i in range(count):
        record = payload[header_len + i * record_len : header_len + (i + 1) * record_len]
        cursor, row = 1, {}
        for name, length in fields:
            row[name] = record[cursor : cursor + length].decode("latin-1").strip()
            cursor += length
        rows.append(row)
    return rows


def _read_shp(payload: bytes) -> list[list[list[tuple[float, float]]]]:
    """Polygon and multipolygon records as lists of rings in lon/lat."""
    total = len(payload)
    offset = 100
    shapes: list[list[list[tuple[float, float]]]] = []
    while offset < total:
        _, content_len = struct.unpack(">ii", payload[offset : offset + 8])
        offset += 8
        end = offset + content_len * 2
        shape_type = struct.unpack("<i", payload[offset : offset + 4])[0]
        rings: list[list[tuple[float, float]]] = []
        if shape_type in (5, 15, 25):  # Polygon, PolygonZ, PolygonM
            part_count, point_count = struct.unpack("<ii", payload[offset + 36 : offset + 44])
            parts = struct.unpack(f"<{part_count}i", payload[offset + 44 : offset + 44 + 4 * part_count])
            points_at = offset + 44 + 4 * part_count
            coords = struct.unpack(
                f"<{point_count * 2}d", payload[points_at : points_at + 16 * point_count]
            )
            for i, start in enumerate(parts):
                stop = parts[i + 1] if i + 1 < part_count else point_count
                rings.append([(coords[2 * j], coords[2 * j + 1]) for j in range(start, stop)])
        shapes.append(rings)
        offset = end
    return shapes


def load_shapefile(url: str, name: str) -> list[tuple[dict[str, str], list[list[tuple[float, float]]]]]:
    archive = _download(url, RAW / name)
    with zipfile.ZipFile(archive) as zf:
        shp = next(n for n in zf.namelist() if n.endswith(".shp"))
        dbf = next(n for n in zf.namelist() if n.endswith(".dbf"))
        attributes = _read_dbf(zf.read(dbf))
        geometry = _read_shp(zf.read(shp))
    return list(zip(attributes, geometry))


# --------------------------------------------------------------------------
# Albers USA composite
# --------------------------------------------------------------------------


def _albers(
    parallel_0: float,
    parallel_1: float,
    rotate_lon: float,
    center: tuple[float, float],
    scale: float,
    translate: tuple[float, float],
):
    """One Albers conic equal-area projection, matching d3-geo's arithmetic.

    Equal-area matters on a choropleth: an equal-area projection is the only
    kind where the visual weight of a county is proportional to its actual size,
    which is the thing a reader is unconsciously integrating when they look at
    a map like this.
    """
    phi0, phi1 = parallel_0 * DEG, parallel_1 * DEG
    sin0 = math.sin(phi0)
    n = (sin0 + math.sin(phi1)) / 2.0
    c = 1.0 + sin0 * (2.0 * n - sin0)
    rho0 = math.sqrt(c) / n

    def raw(lam: float, phi: float) -> tuple[float, float]:
        rho = math.sqrt(c - 2.0 * n * math.sin(phi)) / n
        return rho * math.sin(lam * n), rho0 - rho * math.cos(lam * n)

    cx, cy = raw(center[0] * DEG, center[1] * DEG)
    dx = translate[0] - scale * cx
    dy = translate[1] + scale * cy

    def forward(lon: float, lat: float) -> tuple[float, float]:
        lam = (lon + rotate_lon) * DEG
        if lam > math.pi:
            lam -= 2.0 * math.pi
        elif lam < -math.pi:
            lam += 2.0 * math.pi
        x, y = raw(lam, lat * DEG)
        return dx + scale * x, dy - scale * y

    return forward


LOWER48 = _albers(29.5, 45.5, 96, (-0.6, 38.7), SCALE, TRANSLATE)
ALASKA = _albers(
    55, 65, 154, (-2, 58.5), SCALE * 0.35, (TRANSLATE[0] - 0.307 * SCALE, TRANSLATE[1] + 0.201 * SCALE)
)
HAWAII = _albers(
    8, 18, 157, (-3, 19.9), SCALE, (TRANSLATE[0] - 0.205 * SCALE, TRANSLATE[1] + 0.212 * SCALE)
)
#: Not part of d3's Albers USA composite. Puerto Rico is 78 municipios with EPA
#: designations of their own, so leaving it off a "national" map is a choice, not
#: a default. Placed as an inset below Florida.
PUERTO_RICO = _albers(
    8, 18, 66, (0, 18), SCALE, (TRANSLATE[0] + 0.330 * SCALE, TRANSLATE[1] + 0.232 * SCALE)
)

#: FIPS state codes that get their own inset. Everything else is lower 48.
_INSETS = {"02": ALASKA, "15": HAWAII, "72": PUERTO_RICO}

#: Clip boxes, in frame pixels, matching d3's Albers USA extents. Without these
#: the Aleutian islands past the antimeridian project into open ocean east of
#: Alaska and read as a line of debris across the Pacific.
_CLIP: dict[str, tuple[float, float, float, float]] = {
    "02": (
        TRANSLATE[0] - 0.425 * SCALE, TRANSLATE[1] + 0.120 * SCALE,
        TRANSLATE[0] - 0.214 * SCALE, TRANSLATE[1] + 0.234 * SCALE,
    ),
    "15": (
        TRANSLATE[0] - 0.214 * SCALE, TRANSLATE[1] + 0.166 * SCALE,
        TRANSLATE[0] - 0.115 * SCALE, TRANSLATE[1] + 0.234 * SCALE,
    ),
    "72": (
        TRANSLATE[0] + 0.290 * SCALE, TRANSLATE[1] + 0.190 * SCALE,
        TRANSLATE[0] + 0.380 * SCALE, TRANSLATE[1] + 0.260 * SCALE,
    ),
}
_CLIP_DEFAULT = (
    TRANSLATE[0] - 0.455 * SCALE, TRANSLATE[1] - 0.238 * SCALE,
    TRANSLATE[0] + 0.455 * SCALE, TRANSLATE[1] + 0.238 * SCALE,
)


def clip_for(state_fips: str) -> tuple[float, float, float, float]:
    return _CLIP.get(state_fips, _CLIP_DEFAULT)

#: Territories with no Albers placement. Scored in the JSON, not drawn. Stated
#: on the page rather than silently dropped.
_UNDRAWN = {"60": "American Samoa", "66": "Guam", "69": "Northern Mariana Islands", "78": "US Virgin Islands"}


def project_for(state_fips: str):
    return _INSETS.get(state_fips, LOWER48)


# --------------------------------------------------------------------------
# Simplification
# --------------------------------------------------------------------------


def _rdp(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker, iterative so a 4,000-point ring cannot blow the
    recursion limit."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    tol2 = tolerance * tolerance
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        ax, ay = points[first]
        bx, by = points[last]
        dx, dy = bx - ax, by - ay
        span2 = dx * dx + dy * dy
        worst, worst_at = -1.0, -1
        for i in range(first + 1, last):
            px, py = points[i]
            if span2 == 0.0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / span2
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > worst:
                worst, worst_at = d2, i
        if worst > tol2:
            keep[worst_at] = True
            stack.append((first, worst_at))
            stack.append((worst_at, last))
    return [p for p, k in zip(points, keep) if k]


def _ring_area(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(points)):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % len(points)]
        total += x0 * y1 - x1 * y0
    return abs(total) / 2.0


def path_for(
    rings: list[list[tuple[float, float]]],
    project,
    tolerance: float,
    min_area: float,
    clip: tuple[float, float, float, float] | None = None,
) -> str:
    """Projected, simplified, integer SVG path data.

    Relative commands on a 10x integer grid. A single ``l`` takes every
    following pair, so the payload is mostly digits, which is what keeps the
    file small without a topology encoder.
    """
    out: list[str] = []
    for ring in rings:
        projected = [project(lon, lat) for lon, lat in ring]
        if clip:
            x0, y0, x1, y1 = clip
            cx = sum(p[0] for p in projected) / len(projected)
            cy = sum(p[1] for p in projected) / len(projected)
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                continue
        if len(projected) > 2 and _ring_area(projected) < min_area:
            continue
        simplified = _rdp(projected, tolerance)
        if len(simplified) < 3:
            continue
        grid = []
        last = None
        for x, y in simplified:
            point = (round(x * GRID), round(y * GRID))
            if point != last:
                grid.append(point)
                last = point
        if len(grid) < 3:
            continue
        head = grid[0]
        parts = [f"M{head[0]} {head[1]}l"]
        previous = head
        deltas = []
        for point in grid[1:]:
            deltas.append(f"{point[0] - previous[0]} {point[1] - previous[1]}")
            previous = point
        parts.append(",".join(deltas))
        parts.append("z")
        out.append("".join(parts))
    return "".join(out)


# --------------------------------------------------------------------------
# Colour
# --------------------------------------------------------------------------

#: Bin edges on days_likely. Chosen on the shape of the data, not on quantiles:
#: three quarters of all counties land on one value, so a quantile scale would
#: paint the map a single colour and call it information.
BINS = (700, 850, 1050, 1350)

BIN_LABELS = (
    ("under 700", "~1.9 years or less"),
    ("700 to 849", "1.9 to 2.3 years"),
    ("850 to 1,049", "2.3 to 2.9 years"),
    ("1,050 to 1,349", "2.9 to 3.7 years"),
    ("1,350 or more", "3.7 years and up"),
)

#: Five steps of one blue hue. Validated in both modes: monotone lightness,
#: adjacent lightness gap >= 0.06, light-end contrast >= 2:1 on the surface,
#: single hue. The dark column is stepped for the dark surface and flips the
#: anchor, so "few days" recedes toward the surface in both modes.
RAMP_LIGHT = ("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b")
RAMP_DARK = ("#184f95", "#256abf", "#3987e5", "#86b6ef", "#cde2fb")


def bin_for(days: int) -> int:
    for i, edge in enumerate(BINS):
        if days < edge:
            return i
    return len(BINS)


# --------------------------------------------------------------------------
# Hover profiles
# --------------------------------------------------------------------------

#: Long trigger detail, compressed to something that fits in a tooltip. The full
#: text with its citation stays in data/county_scores.json.
_TRIGGER_LABELS = {
    "major_nonattainment_nsr": "Major nonattainment NSR — LAER plus emission offsets",
    "major_psd": "Major PSD — BACT, AERMOD modeling, public comment",
    "nonattainment_designation": "County designated nonattainment",
    "ozone_transport_region": "Ozone Transport Region — NOx regulated statewide",
    "ej_denial_authority": "State can deny on environmental justice grounds",
    "state_toxics": "State air toxics program on top of federal HAP",
    "title_v": "Title V operating permit",
    "nsps_turbine": "NSPS KKKK — the Jan 2026 turbine rule closed the fast path",
    "nsps_rice": "NSPS IIII/JJJJ and NESHAP ZZZZ",
    "county_moratorium": "County data center moratorium",
    "zoning_posture": "County has denied recent data center applications",
    "litigation": "Federal litigation touching this county",
    "class_i_aqrv": "Class I area within range — federal land manager review",
    "psd_increment_consumed": "PSD increment already consumed",
    "complex_terrain": "Complex terrain — AERMOD with terrain receptors",
    "gas_reachability": "Gas pipeline distance",
    "source_aggregation_risk": "Source aggregation risk",
    "synthetic_minor": "Synthetic minor — federally enforceable run-hour cap",
    "minor_nsr": "Minor NSR construction permit",
    "permit_by_rule": "Permit by rule / general permit",
}

#: Which triggers a reader should see first when only two fit. Pathway-deciding
#: triggers outrank timeline modifiers, which outrank things that are true
#: everywhere (Title V, NSPS).
_TRIGGER_PRIORITY = {
    "major_nonattainment_nsr": 0,
    "major_psd": 1,
    "nonattainment_designation": 2,
    "county_moratorium": 3,
    "ej_denial_authority": 4,
    "ozone_transport_region": 5,
    "zoning_posture": 6,
    "litigation": 7,
    "gas_reachability": 8,
    "psd_increment_consumed": 9,
    "class_i_aqrv": 10,
    "complex_terrain": 11,
    "state_toxics": 12,
    "source_aggregation_risk": 13,
    "synthetic_minor": 14,
    "minor_nsr": 15,
    "permit_by_rule": 16,
    "title_v": 90,
    "nsps_turbine": 91,
    "nsps_rice": 92,
}


#: The trigger that names the pathway is not a "why" — it is the answer, and it
#: is already displayed beside these labels. Showing it here would spend both
#: tooltip lines restating the pathway column.
_PATHWAY_TRIGGERS = frozenset(
    {"major_psd", "major_nonattainment_nsr", "minor_nsr", "synthetic_minor", "permit_by_rule"}
)


def top_triggers(record: dict, n: int = 2, skip_nonattainment: bool = False) -> list[str]:
    """The two triggers that most explain why this county differs from the median.

    Ranked by the curated priority, then by months added. Triggers that fire in
    every county in the country (Title V, NSPS KKKK) sit at the bottom and only
    surface when nothing else did — which is itself information: it means the
    county is unremarkable and the timeline is the base case.
    """
    skip = set(_PATHWAY_TRIGGERS)
    if skip_nonattainment:
        # The tooltip prints the designation on its own line. Repeating it here
        # would spend one of only two lines saying the same thing twice.
        skip.add("nonattainment_designation")
    candidates = [t for t in record["triggers"] if t["name"] not in skip]
    ordered = sorted(
        candidates,
        key=lambda t: (_TRIGGER_PRIORITY.get(t["name"], 50), -t.get("months_added", 0.0)),
    )
    out = []
    for trigger in ordered[:n]:
        if trigger["name"] == "nonattainment_designation" and record["nonattainment"]:
            label = "Nonattainment: " + ", ".join(
                f"{s['pollutant'].upper()} {s['classification']}" for s in record["nonattainment"]
            )
        else:
            label = _TRIGGER_LABELS.get(trigger["name"], trigger["name"].replace("_", " "))
        months = trigger.get("months_added") or 0.0
        out.append(f"{label} (+{months:.0f} mo)" if months else label)
    return out


def profile_key(record: dict) -> tuple:
    na = ";".join(f"{s['pollutant']} {s['classification']}" for s in record["nonattainment"])
    return (
        record["pathway_label"],
        record["days_low"],
        record["days_likely"],
        record["days_high"],
        record["agency"],
        na,
        tuple(top_triggers(record, skip_nonattainment=True)),
        bool(record["hard_stops"]),
        record["data_quality"],
    )


def build_profiles(records: list[dict]) -> tuple[list[dict], dict[str, int]]:  # noqa: C901
    """Counties collapse onto a small number of distinct answers.

    That is not a compression trick, it is the honest shape of the model: at
    county resolution there are only so many different things to say. Shipping
    it this way makes the file small and makes the resolution visible.
    """
    profiles: dict[tuple, int] = {}
    ordered: list[dict] = []
    assignment: dict[str, int] = {}
    for record in records:
        key = profile_key(record)
        if key not in profiles:
            profiles[key] = len(ordered)
            ordered.append(
                {
                    "p": record["pathway_label"],
                    "dl": record["days_low"],
                    "d": record["days_likely"],
                    "dh": record["days_high"],
                    "ml": record["months_low"],
                    "m": record["months_likely"],
                    "mh": record["months_high"],
                    "a": record["agency"],
                    "na": [
                        f"{s['pollutant'].upper()} {s['classification']}"
                        for s in record["nonattainment"]
                    ],
                    "t": top_triggers(record, skip_nonattainment=True),
                    "s": bool(record["hard_stops"]),
                    "q": record["data_quality"],
                    "b": bin_for(record["days_likely"]),
                    "n": 0,
                    "st": [],
                }
            )
        index = profiles[key]
        assignment[record["fips"]] = index
        ordered[index]["n"] += 1
        if record["state"] not in ordered[index]["st"]:
            ordered[index]["st"].append(record["state"])
    return ordered, assignment


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_svg(
    payload: dict,
    tolerance: float,
    min_area: float,
) -> tuple[str, str, list[dict], list[list], dict]:
    """Returns (county paths markup, state borders path, profiles, county rows, stats)."""
    records = {r["fips"]: r for r in payload["counties"]}
    profiles, assignment = build_profiles(payload["counties"])

    counties = load_shapefile(CB_COUNTY_URL, "cb_county_5m.zip")
    states = load_shapefile(CB_STATE_URL, "cb_state_5m.zip")

    paths: list[str] = []
    stop_paths: list[str] = []
    rows: list[list] = []
    drawn = 0
    stops = 0
    missing_geometry = set(records)
    undrawn_territory = 0

    for attributes, rings in sorted(counties, key=lambda item: item[0]["GEOID"]):
        fips = attributes["GEOID"]
        state_fips = attributes["STATEFP"]
        record = records.get(fips)
        if record is None:
            continue
        missing_geometry.discard(fips)
        if state_fips in _UNDRAWN:
            undrawn_territory += 1
            continue
        data = path_for(rings, project_for(state_fips), tolerance, min_area, clip_for(state_fips))
        if not data:
            continue
        index = len(rows)
        profile = assignment[fips]
        css = "q" if record["data_quality"] != "ok" else f"b{profiles[profile]['b']}"
        paths.append(
            f'<path class="c {css}" d="{data}" data-i="{index}" tabindex="0" role="img" '
            f'aria-label="{_esc(record["county"])}, {record["state"]}: '
            f'{record["days_likely"]:,} days"/>'
        )
        rows.append([record["county"], record["state"], profile])
        drawn += 1
        # A moratorium county can score 730 days and still be un-permittable.
        # The ramp encodes time; this second channel encodes "time may not be
        # the binding constraint here". It ships with a legend label, never as
        # colour alone.
        if record["hard_stops"]:
            stop_paths.append(data)
            stops += 1

    borders: list[str] = []
    for attributes, rings in states:
        state_fips = attributes.get("STATEFP", "")
        if state_fips in _UNDRAWN:
            continue
        data = path_for(
            rings, project_for(state_fips), tolerance * 1.2, min_area * 3, clip_for(state_fips)
        )
        if data:
            borders.append(data)

    stats = {
        "drawn": drawn,
        "scored": len(records),
        "undrawn_territory": undrawn_territory,
        "missing_geometry": sorted(missing_geometry),
        "profiles": len(profiles),
        "hard_stops": stops,
    }
    return "".join(paths), "".join(borders), profiles, rows, stats, "".join(stop_paths)


def render_html(payload: dict, svg_parts: tuple, generated: str) -> str:
    county_paths, borders, profiles, rows, stats, stop_paths = svg_parts
    counts = payload["counts"]
    config = payload["reference_config"]
    sources = payload["sources"]
    fastest, slowest = extremes(payload, n=5)

    view_w = int(FRAME_W * GRID)
    view_h = int(FRAME_H * GRID)

    bin_counts = [0] * (len(BINS) + 1)
    insufficient = 0
    for record in payload["counties"]:
        if record["data_quality"] != "ok":
            insufficient += 1
        else:
            bin_counts[bin_for(record["days_likely"])] += 1

    legend_items = "".join(
        f'<li><span class="sw b{i}"></span>'
        f'<span class="lg-t">{label} days</span>'
        f'<span class="lg-s">{sub}</span>'
        f'<span class="lg-n">{bin_counts[i]:,}</span></li>'
        for i, (label, sub) in enumerate(BIN_LABELS)
    )
    if insufficient:
        legend_items += (
            '<li><span class="sw q"></span><span class="lg-t">no attainment data</span>'
            '<span class="lg-s">score below is a floor</span>'
            f'<span class="lg-n">{insufficient:,}</span></li>'
        )
    if stats["hard_stops"]:
        legend_items += (
            '<li><span class="sw stopsw"></span><span class="lg-t">hard stop</span>'
            '<span class="lg-s">moratorium, offsets unavailable, or fuel supply — '
            "the timeline may not be the binding constraint</span>"
            f'<span class="lg-n">{stats["hard_stops"]:,}</span></li>'
        )

    def table_rows(items: list[dict]) -> str:
        out = []
        for record in items:
            tied = f' <span class="tie">+{record["tied_with"]:,} tied</span>' if record["tied_with"] else ""
            reason = top_triggers(record, 2)
            out.append(
                f"<tr><td class=\"num\">{record['days_likely']:,}</td>"
                f"<td>{_esc(record['county'])}, {record['state']}{tied}</td>"
                f"<td>{_esc(record['pathway_label'])}</td>"
                f"<td class=\"why\">{_esc('; '.join(reason))}</td></tr>"
            )
        return "".join(out)

    data_blob = json.dumps({"p": profiles, "c": rows}, separators=(",", ":"))
    pte = config["pte_tpy"]

    # Every distinct answer the model produces, as a table. This is the "reachable
    # without hovering" path, and at 43 rows it is also the honest statement of how
    # much resolution a county-level screen actually has.
    answer_rows = []
    for profile in sorted(profiles, key=lambda p: (p["d"], p["p"], -p["n"])):
        css = "q" if profile["q"] != "ok" else f"b{profile['b']}"
        states = sorted(profile["st"])
        where = ", ".join(states) if len(states) <= 8 else f"{len(states)} states"
        na = ", ".join(profile["na"]) if profile["na"] else "attainment"
        if profile["q"] != "ok":
            na = "no data"
        answer_rows.append(
            f'<tr><td class="num"><span class="sw {css}"></span>{profile["d"]:,}</td>'
            f'<td class="num">{profile["dl"]:,}&ndash;{profile["dh"]:,}</td>'
            f'<td>{_esc(profile["p"])}{" &middot; hard stop" if profile["s"] else ""}</td>'
            f'<td class="why">{_esc(na)}</td>'
            f'<td>{_esc(profile["a"])}</td>'
            f'<td class="num">{profile["n"]:,}</td>'
            f'<td class="why">{_esc(where)}</td></tr>'
        )
    answers_table = "".join(answer_rows)

    territories = ""
    if stats["undrawn_territory"]:
        territories = (
            f' {stats["undrawn_territory"]} territory county-equivalents '
            f'({", ".join(sorted(_UNDRAWN.values()))}) are scored in the data file but have no '
            f"place in this projection, so they are not drawn."
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Days until legal power — every US county</title>
<style>
:root {{
  color-scheme: light dark;
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --rule:#e1e0d9; --border:rgba(11,11,11,0.10); --stroke:#fcfcfb; --state:#52514e;
  --b0:{RAMP_LIGHT[0]}; --b1:{RAMP_LIGHT[1]}; --b2:{RAMP_LIGHT[2]}; --b3:{RAMP_LIGHT[3]}; --b4:{RAMP_LIGHT[4]};
  --nodata:#d6d5cd; --nodata-ink:#898781; --focus:#eb6834; --critical:#d03b3b;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
    --rule:#2c2c2a; --border:rgba(255,255,255,0.10); --stroke:#1a1a19; --state:#c3c2b7;
    --b0:{RAMP_DARK[0]}; --b1:{RAMP_DARK[1]}; --b2:{RAMP_DARK[2]}; --b3:{RAMP_DARK[3]}; --b4:{RAMP_DARK[4]};
    --nodata:#2c2c2a; --nodata-ink:#898781; --focus:#eb6834; --critical:#d03b3b;
  }}
}}
:root[data-theme="dark"] {{
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
  --rule:#2c2c2a; --border:rgba(255,255,255,0.10); --stroke:#1a1a19; --state:#c3c2b7;
  --b0:{RAMP_DARK[0]}; --b1:{RAMP_DARK[1]}; --b2:{RAMP_DARK[2]}; --b3:{RAMP_DARK[3]}; --b4:{RAMP_DARK[4]};
  --nodata:#2c2c2a; --nodata-ink:#898781; --focus:#eb6834; --critical:#d03b3b;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--plane); color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1180px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ font-size:clamp(22px,3.1vw,32px); line-height:1.2; margin:0 0 6px; letter-spacing:-0.01em; }}
.sub {{ color:var(--ink-2); margin:0 0 4px; max-width:74ch; }}
.method {{ color:var(--muted); font-size:13px; margin:0 0 18px; max-width:88ch; }}
.caveat {{
  border-left:3px solid var(--focus); background:var(--surface); border:1px solid var(--border);
  border-left:3px solid var(--focus); border-radius:6px; padding:10px 14px; margin:0 0 20px;
  font-size:13.5px; color:var(--ink-2); max-width:88ch;
}}
.caveat b {{ color:var(--ink); }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; }}
.mapcard {{ padding:10px 10px 4px; position:relative; }}
svg.map {{ display:block; width:100%; height:auto; }}
path.c {{ stroke:var(--stroke); stroke-width:.5; stroke-linejoin:round; vector-effect:non-scaling-stroke; }}
path.c:focus {{ outline:none; }}
.b0 {{ fill:var(--b0); }} .b1 {{ fill:var(--b1); }} .b2 {{ fill:var(--b2); }}
.b3 {{ fill:var(--b3); }} .b4 {{ fill:var(--b4); }}
.q {{ fill:url(#hatch); }}
path.borders {{ fill:none; stroke:var(--state); stroke-width:0.9; stroke-linejoin:round;
  vector-effect:non-scaling-stroke; opacity:.5; pointer-events:none; }}
path.stops {{ fill:none; stroke:var(--critical); stroke-width:1.4; stroke-linejoin:round;
  vector-effect:non-scaling-stroke; pointer-events:none; }}
path.hi {{ fill:none; stroke:var(--ink); stroke-width:2.4; stroke-linejoin:round;
  vector-effect:non-scaling-stroke; pointer-events:none; }}
.legend {{ list-style:none; margin:14px 0 0; padding:0 4px 8px;
  display:flex; flex-wrap:wrap; gap:6px 26px; font-size:12.5px; color:var(--ink-2); }}
.legend li {{ display:flex; align-items:baseline; gap:7px; }}
.sw {{ width:13px; height:13px; border-radius:3px; flex:none; border:1px solid var(--border);
  align-self:center; }}
.sw.b0{{background:var(--b0)}} .sw.b1{{background:var(--b1)}} .sw.b2{{background:var(--b2)}}
.sw.b3{{background:var(--b3)}} .sw.b4{{background:var(--b4)}}
.sw.stopsw {{ background:transparent; border:2px solid var(--critical); }}
.sw.q {{ background:var(--nodata);
  background-image:repeating-linear-gradient(45deg,transparent 0 3px,var(--nodata-ink) 3px 4px); }}
.lg-t {{ color:var(--ink); }}
.lg-s {{ color:var(--muted); }}
.lg-s::before {{ content:"\\00b7\\00a0"; }}
.lg-n {{ color:var(--muted); font-variant-numeric:tabular-nums; }}
.lg-n::before {{ content:"\\00b7\\00a0"; }}
td .sw {{ display:inline-block; margin-right:7px; vertical-align:-1px; }}
details {{ margin-top:18px; }}
details > summary {{ cursor:pointer; font-size:13px; color:var(--ink-2); padding:6px 0;
  list-style:none; }}
details > summary::-webkit-details-marker {{ display:none; }}
details > summary::before {{ content:"\\25b8\\00a0"; color:var(--muted); }}
details[open] > summary::before {{ content:"\\25be\\00a0"; }}
.scroll {{ overflow-x:auto; }}
.tip {{
  position:absolute; pointer-events:none; opacity:0; transform:translateY(3px);
  transition:opacity .09s ease, transform .09s ease; z-index:5; max-width:330px;
  background:var(--surface); border:1px solid var(--border); border-radius:8px;
  box-shadow:0 6px 22px rgba(0,0,0,.16); padding:10px 12px; font-size:12.5px; color:var(--ink-2);
}}
.tip.on {{ opacity:1; transform:translateY(0); }}
.tip .val {{ font-size:21px; color:var(--ink); font-weight:650; letter-spacing:-0.01em; }}
.tip .val small {{ font-size:12px; font-weight:400; color:var(--muted); }}
.tip .place {{ color:var(--ink); font-weight:600; margin-bottom:2px; }}
.tip .path {{ margin:5px 0 0; }}
.tip ul {{ margin:6px 0 0; padding:0; list-style:none; }}
.tip li {{ display:flex; gap:7px; margin-top:3px; }}
.tip li::before {{ content:""; flex:none; width:10px; height:2px; margin-top:8px;
  background:var(--muted); border-radius:1px; }}
.tip .stop {{ color:var(--focus); margin-top:6px; font-weight:600; }}
.tip .flag {{ color:var(--muted); margin-top:6px; font-style:italic; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:18px; margin-top:22px; }}
.panel {{ padding:16px 18px 18px; }}
.panel h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.07em;
  color:var(--muted); margin:0 0 10px; font-weight:600; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ text-align:left; padding:6px 8px 6px 0; border-bottom:1px solid var(--rule);
  vertical-align:top; }}
th {{ color:var(--muted); font-weight:600; font-size:11.5px; text-transform:uppercase;
  letter-spacing:.05em; }}
td.num {{ font-variant-numeric:tabular-nums; font-weight:650; color:var(--ink); white-space:nowrap; }}
td.why {{ color:var(--ink-2); }}
.tie {{ color:var(--muted); font-weight:400; }}
.stats {{ display:flex; flex-wrap:wrap; gap:10px 30px; margin:0; padding:0; list-style:none; }}
.stats li {{ min-width:110px; }}
.stats .n {{ display:block; font-size:22px; font-weight:650; color:var(--ink);
  letter-spacing:-0.01em; }}
.stats .k {{ font-size:12px; color:var(--muted); }}
footer {{ margin-top:26px; font-size:12px; color:var(--muted); max-width:92ch; }}
footer a {{ color:inherit; }}
code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }}
@media (max-width:640px) {{ .wrap {{ padding:20px 14px 44px; }} .legend {{ gap:4px 14px; }} }}
</style>
</head>
<body>
<div class="wrap">
<h1>Days until legal power</h1>
<p class="sub">Every US county, scored on how long it takes to get an air permit for the
same 500 MW combined-cycle gas plant. Not whether the site is good. Whether they will
let you switch it on.</p>
<p class="method">Method: {_esc(config['description'])}.
Potential to emit {pte['NOx']:,.0f} tpy NOx, {pte['CO']:,.0f} tpy CO at
{config['heat_input_mmbtu_hr']:,.0f} MMBtu/hr heat input (AP-42 factors, 8,760 hours).
Run through the pathway engine in <code>agent/pathway.py</code> against each county's EPA Green
Book designation and its state agency overlay. Timeline is application-complete to
permit-issued, likely case.</p>

<div class="caveat"><b>Screening layer. The parcel run is the real answer.</b>
This map is built from county-level facts only. It cannot see PSD increment already
consumed at your parcel, terrain relief in the modeling domain, distance to a gas
transmission pipeline, or how many people live within a kilometre of the fence line.
Any of those can move a county-green site to a two-year problem. Use this to pick where
to look, then run the parcel.</div>

<div class="card mapcard">
  <svg class="map" viewBox="0 0 {view_w} {view_h}" role="group"
       aria-label="Choropleth of US counties by days until an air permit is issued for a 500 MW gas plant">
    <defs>
      <!-- Pattern units are viewBox units (10x the frame), so these numbers are
           ten times what they look like on screen. -->
      <pattern id="hatch" width="70" height="70" patternUnits="userSpaceOnUse"
               patternTransform="rotate(45)">
        <rect width="70" height="70" fill="var(--nodata)"/>
        <line x1="0" y1="0" x2="0" y2="70" stroke="var(--nodata-ink)" stroke-width="24"/>
      </pattern>
    </defs>
    <g id="counties">{county_paths}</g>
    <path class="borders" d="{borders}"/>
    <path class="stops" d="{stop_paths}"/>
    <path class="hi" id="hi" d=""/>
  </svg>
  <ul class="legend">{legend_items}</ul>
  <div class="tip" id="tip" role="status" aria-live="polite"></div>
</div>

<div class="grid">
  <div class="card panel">
    <h2>Fastest five</h2>
    <table><thead><tr><th>Days</th><th>County</th><th>Pathway</th><th>Why</th></tr></thead>
    <tbody>{table_rows(fastest)}</tbody></table>
  </div>
  <div class="card panel">
    <h2>Slowest five</h2>
    <table><thead><tr><th>Days</th><th>County</th><th>Pathway</th><th>Why</th></tr></thead>
    <tbody>{table_rows(slowest)}</tbody></table>
  </div>
</div>

<div class="card panel" style="margin-top:18px">
  <h2>What the sweep found</h2>
  <ul class="stats">
    <li><span class="n">{counts['counties']:,}</span><span class="k">counties scored</span></li>
    <li><span class="n">{counts['by_pathway'].get('major_psd', 0):,}</span><span class="k">major PSD</span></li>
    <li><span class="n">{counts['by_pathway'].get('major_nonattainment_nsr', 0):,}</span><span class="k">major nonattainment NSR</span></li>
    <li><span class="n">{counts['with_hard_stop']:,}</span><span class="k">with a hard stop</span></li>
    <li><span class="n">{counts['insufficient_data']:,}</span><span class="k">insufficient data</span></li>
    <li><span class="n">{stats['profiles']}</span><span class="k">distinct answers</span></li>
  </ul>
  <p class="method" style="margin:14px 0 0">There is no county in the United States where
  this plant is a minor source. A 500 MW combined cycle puts a heat recovery steam
  generator on the site, which lands it in the first of the List of 28 named source
  categories and drops the PSD major threshold from 250 to 100 tons per year. At best-in-class
  control — dry low-NOx combustors, SCR and an oxidation catalyst — it still emits
  {pte['NOx']:,.0f} tpy of NOx. The question is never whether you need a major permit. It is
  which major permit, and whose desk it sits on. {stats['profiles']} distinct answers across
  {counts['counties']:,} counties is the honest resolution of a county-level model, and it is
  why the parcel run exists.</p>

  <details>
    <summary>Every distinct answer, {stats['profiles']} rows &mdash; the whole map without hovering</summary>
    <div class="scroll">
      <table>
        <thead><tr><th>Days</th><th>Range</th><th>Pathway</th><th>Nonattainment</th>
        <th>Agency</th><th>Counties</th><th>Where</th></tr></thead>
        <tbody>{answers_table}</tbody>
      </table>
    </div>
  </details>
</div>

<footer>
<p>Counties: {_esc(sources['counties']['name'])} —
<code>{_esc(GAZETTEER_URL)}</code>. Boundaries: {CB_VINTAGE}.
Nonattainment: {_esc(sources['nonattainment']['name'])}{
  ', fetched ' + _esc(sources['nonattainment']['fetched']) if sources['nonattainment'].get('fetched') else ''}.
County posture: {_esc(sources['county_posture']['name'])}.
Pathway engine: {_esc(sources['pathway_engine'])}.
Mireye enrichment: {_esc(sources['mireye'])}.</p>
<p>{stats['drawn']:,} counties drawn of {stats['scored']:,} scored.{territories}
Sweep generated {_esc(payload['generated'])}; page generated {_esc(generated)}.
Every timeline is a screen, not an applicability determination. A licensed professional
signs those.</p>
</footer>
</div>

<script>
(function () {{
  var D = {data_blob};
  var svg = document.querySelector('svg.map');
  var tip = document.getElementById('tip');
  var hi = document.getElementById('hi');
  var card = document.querySelector('.mapcard');
  var active = null;

  function el(tag, cls, text) {{
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;   // names are data; never innerHTML
    return n;
  }}

  function fill(node, row) {{
    var p = D.p[row[2]];
    node.replaceChildren();
    node.appendChild(el('div', 'place', row[0] + ', ' + row[1]));
    var v = el('div', 'val');
    v.appendChild(document.createTextNode(p.d.toLocaleString()));
    var s = el('small', null, ' days likely \\u00b7 ' + p.dl.toLocaleString() +
              '\\u2013' + p.dh.toLocaleString() + ' range');
    v.appendChild(s);
    node.appendChild(v);
    node.appendChild(el('div', 'path', p.p + ' \\u00b7 ' + p.a));
    if (p.na.length) node.appendChild(el('div', 'path', 'Nonattainment: ' + p.na.join(', ')));
    var ul = el('ul');
    for (var i = 0; i < p.t.length; i++) ul.appendChild(el('li', null, p.t[i]));
    node.appendChild(ul);
    if (p.s) node.appendChild(el('div', 'stop', 'Hard stop flagged \\u2014 see the record'));
    if (p.q !== 'ok') node.appendChild(el('div', 'flag',
      'No attainment data for this county. This number is a floor.'));
    node.appendChild(el('div', 'flag', 'County resolution. Run the parcel.'));
  }}

  function show(path, x, y) {{
    var i = +path.getAttribute('data-i');
    var row = D.c[i];
    if (!row) return;
    if (active !== path) {{ hi.setAttribute('d', path.getAttribute('d')); active = path; }}
    fill(tip, row);
    tip.classList.add('on');
    var box = card.getBoundingClientRect();
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = x - box.left + 16, top = y - box.top + 16;
    if (left + w > box.width - 8) left = x - box.left - w - 16;
    if (top + h > box.height - 8) top = y - box.top - h - 16;
    tip.style.left = Math.max(8, left) + 'px';
    tip.style.top = Math.max(8, top) + 'px';
  }}

  function hide() {{ tip.classList.remove('on'); hi.setAttribute('d', ''); active = null; }}

  svg.addEventListener('pointermove', function (e) {{
    var t = e.target;
    if (t && t.classList && t.classList.contains('c')) show(t, e.clientX, e.clientY);
    else hide();
  }});
  svg.addEventListener('pointerleave', hide);
  svg.addEventListener('focusin', function (e) {{
    var t = e.target;
    if (!t || !t.classList || !t.classList.contains('c')) return;
    var r = t.getBoundingClientRect();
    show(t, r.left + r.width / 2, r.top + r.height / 2);
  }});
  svg.addEventListener('focusout', hide);
}})();
</script>
</body>
</html>
"""


def render_static_svg(payload: dict, svg_parts: tuple) -> str:
    """The same map with no interaction, titled and captioned, for PNG export.

    Colours are inlined rather than themed: a PNG has no theme. Light steps,
    because that is what a slide or a thread image sits on. It carries its own
    title, legend and caveat so the image is safe to post on its own — an
    unlabelled choropleth is a rumour.
    """
    county_paths, borders, _profiles, _rows, stats, stop_paths = svg_parts
    counts = payload["counts"]
    bin_counts = [0] * (len(BINS) + 1)
    insufficient = 0
    for record in payload["counties"]:
        if record["data_quality"] != "ok":
            insufficient += 1
        else:
            bin_counts[bin_for(record["days_likely"])] += 1

    width = int(FRAME_W * GRID)
    top = 940  # header band, in grid units
    legend_y = top + int(FRAME_H * GRID) + 120

    styles = "".join(f".b{i}{{fill:{RAMP_LIGHT[i]}}}" for i in range(len(RAMP_LIGHT)))
    body = county_paths.replace(' tabindex="0"', "")

    # No text metrics available here, so advance on a conservative per-character
    # width and wrap before the right edge. An overflowing legend is the failure
    # mode, so the estimate errs high.
    char_w, row_h = 70, 190
    swatches = []
    x, row = 120, 0
    items = [(f"b{i}", f"{label} days", bin_counts[i]) for i, (label, _sub) in enumerate(BIN_LABELS)]
    if insufficient:
        items.append(("q", "no attainment data", insufficient))
    if stats["hard_stops"]:
        items.append(("stopsw", "hard stop \u2014 timeline may not bind", stats["hard_stops"]))
    for css, label, count in items:
        text = f"{label}  ({count:,})"
        advance = 152 + len(text) * char_w + 150
        if x > 120 and x + advance > width - 120:
            x, row = 120, row + 1
        y = legend_y + row * row_h
        swatches.append(
            f'<rect class="{css}" x="{x}" y="{y}" width="112" height="112" rx="24"/>'
            f'<text class="lg" x="{x + 152}" y="{y + 92}">{_esc(text)}</text>'
        )
        x += advance
    caption_y = legend_y + (row + 1) * row_h + 130
    height = caption_y + 330

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{int(FRAME_W * 2)}" height="{int(height / GRID * 2)}" role="img" aria-label="US counties by days until legal power for a 500 MW gas plant">
<style>
rect.bg{{fill:#fcfcfb}}
path.c{{stroke:#fcfcfb;stroke-width:4;stroke-linejoin:round}}
{styles}
.q{{fill:url(#hatch)}}
rect.q{{fill:url(#hatch)}}
path.borders{{fill:none;stroke:#52514e;stroke-width:9;stroke-linejoin:round;opacity:.5}}
path.stops{{fill:none;stroke:#d03b3b;stroke-width:14;stroke-linejoin:round}}
rect.stopsw{{fill:none}}
text{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}}
.h1{{font-size:290px;font-weight:680;fill:#0b0b0b;letter-spacing:-3}}
.h2{{font-size:150px;fill:#52514e}}
.lg{{font-size:130px;fill:#52514e}}
.cap{{font-size:120px;fill:#898781}}
</style>
<defs>
  <pattern id="hatch" width="70" height="70" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <rect width="70" height="70" fill="#d6d5cd"/>
    <line x1="0" y1="0" x2="0" y2="70" stroke="#898781" stroke-width="24"/>
  </pattern>
</defs>
<rect class="bg" x="0" y="0" width="{width}" height="{height}"/>
<text class="h1" x="120" y="360">Days until legal power</text>
<text class="h2" x="120" y="600">{counts['counties']:,} US counties &#183; same 500 MW combined-cycle gas plant &#183; air permit, application to issued</text>
<text class="h2" x="120" y="800">{counts['by_pathway'].get('major_psd', 0):,} major PSD &#183; {counts['by_pathway'].get('major_nonattainment_nsr', 0):,} major nonattainment NSR &#183; 0 minor sources anywhere in the country</text>
<g transform="translate(0,{top})">
  <g>{body}</g>
  <path class="borders" d="{borders}"/>
  <path class="stops" d="{stop_paths}"/>
</g>
{''.join(swatches)}
<text class="cap" x="120" y="{caption_y}">Screening layer, county resolution. It cannot see parcel-level PSD increment, terrain, or pipeline distance &#8212; the parcel run is the real answer.</text>
<text class="cap" x="120" y="{caption_y + 170}">Sources: EPA Green Book nonattainment designations, 2025 Census cartographic boundaries, AP-42 emission factors, 40 CFR 51/52. Built with Deliverable.</text>
</svg>
"""


def render_extremes_md(payload: dict) -> str:
    fastest, slowest = extremes(payload, n=5)
    config = payload["reference_config"]

    def block(title: str, items: list[dict]) -> str:
        lines = [f"### {title}", "", "| Days | County | Pathway | Why |", "|---:|---|---|---|"]
        for record in items:
            tied = f" (+{record['tied_with']:,} tied in {record['state']})" if record["tied_with"] else ""
            lines.append(
                f"| {record['days_likely']:,} | {record['county']}, {record['state']}{tied} | "
                f"{record['pathway_label']} | {'; '.join(top_triggers(record, 2))} |"
            )
        return "\n".join(lines) + "\n"

    return f"""# County sweep — fastest and slowest

Reference plant: {config['description']}. Potential to emit \
{config['pte_tpy']['NOx']:,.0f} tpy NOx at {config['heat_input_mmbtu_hr']:,.0f} MMBtu/hr \
heat input. {payload['counts']['counties']:,} counties scored.

County-level screening layer. It cannot see parcel-level increment consumption,
terrain, or pipeline distance. The parcel run is the real answer.

Ranking rule: days first, then hard stops, then offset tonnage, then land area
descending. Land area breaks ties because within a tier every county scores the
same and the one worth looking at is the one with room for 500 MW. Ties are
disclosed rather than hidden behind alphabetical order.

{block("Fastest five", fastest)}
{block("Slowest five", slowest)}
"""


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sweep.map", description="Render the national county map from data/county_scores.json."
    )
    parser.add_argument("--scores", default=str(OUTPUT_PATH))
    parser.add_argument("--out", default=str(ROOT / "outputs" / "county_map.html"))
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.45,
        help="Douglas-Peucker tolerance in projected pixels (frame is 975 wide)",
    )
    parser.add_argument(
        "--min-area", type=float, default=0.6, help="drop rings smaller than this many square pixels"
    )
    args = parser.parse_args(argv)

    scores = Path(args.scores)
    if not scores.exists():
        print(f"[map] {scores} not found. Run: python -m sweep.counties", file=sys.stderr)
        return 1
    payload = json.loads(scores.read_text())

    parts = build_svg(payload, args.tolerance, args.min_area)
    stats = parts[4]
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(payload, parts, generated), encoding="utf-8")

    svg_path = out.with_suffix(".svg")
    svg_path.write_text(render_static_svg(payload, parts), encoding="utf-8")

    md_path = out.parent / "county_extremes.md"
    md_path.write_text(render_extremes_md(payload), encoding="utf-8")

    print(
        f"[map] {out} — {out.stat().st_size / 1e6:.2f} MB, "
        f"{stats['drawn']:,} counties drawn, {stats['profiles']} distinct answers",
        file=sys.stderr,
    )
    print(f"[map] {svg_path} — {svg_path.stat().st_size / 1e6:.2f} MB (static, for PNG)", file=sys.stderr)
    print(f"[map] {md_path}", file=sys.stderr)
    if stats["missing_geometry"]:
        print(
            f"[map] {len(stats['missing_geometry'])} scored counties had no geometry: "
            f"{', '.join(stats['missing_geometry'][:8])}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
