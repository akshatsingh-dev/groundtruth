"""Satellite verification. Is there a hole in the ground yet?

The product's claim is that announced capacity is not deliverable capacity. Of
roughly 90 GW of announced behind-the-meter generation, about 2.2% is operating
and about 60% is announcement-only. A press release says Q4 2026 energization.
This module goes and looks at the dirt.

What it does: pull two cloud-free Sentinel-2 scenes over a parcel — one near the
announced groundbreaking date, one as recent as the archive has — measure how
much of the footprint changed from vegetated to bare, and return a verdict with
every scene id, acquisition date and cloud fraction attached.


MIREYE FIRST, AND WHAT MIREYE ALREADY ANSWERS
---------------------------------------------
Mireye cites Sentinel-2 as one of its own sources and it already serves NDVI:

    ndvi_current      SENTINEL2_NDVI, most recent Sentinel-2 NDVI at the cell
    ndvi_change_5y    SENTINEL2_NDVI, fixed 5-year NDVI change at the cell
    lcms_class        USFS LCMS life-form class, ~120 m block mode
    land_use_class    USFS LCMS land-use class, ~120 m block mode
    tree_canopy_pct   USFS/NLCD tree canopy cover, ~120 m block mode

Those are the right first call and this module reads them as corroboration. They
do not answer the question, and the reason is measurable rather than theoretical.
At 35.065,-90.075 — xAI Colossus 1 in South Memphis, the fastest data center
buildout on record, 122 days — Mireye returns `ndvi_current = 0.84` and
`ndvi_change_5y = +0.038`. Greener. The single ~10 m cell under an approximate
coordinate is a surviving tree, and a point sample reports the tree.

Three gaps, each of which independently blocks the use case:

1.  The dates are not selectable. `ndvi_change_5y` is a fixed 5-year window that
    does not line up with any project's announced groundbreaking date.
2.  The value is a point sample, not a footprint mean.
3.  No scene id, acquisition date or cloud fraction comes back, so the value
    cannot be checked and a cloudy scene cannot be rejected.

`/v1/ask` was tried before any of this was written, and refused in its own words:

    "This question requires time-series Sentinel-2 imagery analysis with specific
    scene metadata (acquisition dates, cloud cover, radiometric processing) and
    spatial aggregation (500 m radius averaging) that are outside the Mireye
    Earth catalog. Mireye provides only a single snapshot of NDVI (ndvi_current)
    at the query point, not historical scenes, scene dates, cloud cover, or
    area-averaged composites."

That is filed as `/v1/field-requests` `fr_39331af65eef4400986c0d4c8552dc5e`,
queued at position 6, three `accepted_new` sub-asks, 0 credits. Capture in
`docs/api-captures/fr5-ndvi-two-date-delta.json`. Everything below is the part
Mireye cannot do today.


WHERE THE PIXELS COME FROM
--------------------------
Copernicus Sentinel-2 L2A surface reflectance, from the AWS Open Data
`sentinel-cogs` bucket. **No credential, no account, no signing.** Scene search
is the Element 84 Earth Search STAC API; pixels are HTTP range reads straight
off the public COGs.

    search   POST https://earth-search.aws.element84.com/v1/search
    pixels   https://sentinel-cogs.s3.us-west-2.amazonaws.com/...

Two other paths were considered. Copernicus Data Space needs an OAuth token for
asset download. Microsoft Planetary Computer needs its assets SAS-signed. Both
work; both add a credential. This one does not, so a judge with no keys can run
`python -m ingest.satellite` and get the same numbers.

The STAC item carries `proj:epsg` and a per-asset `proj:transform`, so the
geo-referencing comes from the catalog rather than from parsing GeoTIFF keys.
The only thing this module has to do itself is WGS84 -> UTM, which is closed
form, and a windowed COG read, which is a TIFF IFD parse plus zlib. No GDAL, no
rasterio, no numpy. The repo's dependency list does not change.


WHAT SENTINEL-2 CAN AND CANNOT SEE
----------------------------------
**10 metres per pixel.** One pixel is 100 m^2 — a tennis court. You can see land
clearing, grading, laydown yards, haul roads and large pads. You cannot see a
turbine foundation, a transformer, a switchyard bay, a pipe rack or anything
else smaller than about 20 m. Nothing in this module's output should be read as
evidence about equipment.

**Cloud, snow, crop cycles and drought all move NDVI**, and some of them move it
further than construction does. Three things are done about that, and they are
the reason this is worth shipping at all:

1.  Cloud is measured over the *footprint* from the scene's own SCL band, not
    taken from the whole-tile `eo:cloud_cover`. A tile can be 60% cloudy and the
    parcel clear, or the reverse.
2.  Above 10% footprint cloud, shadow or snow the answer is `insufficient_imagery`.
    A refusal is a correct answer here. Guessing is not.
3.  Every metric is differenced against a **control ring** — the annulus from
    `radius_m` to `3 x radius_m` around the same point, on the same two scenes.
    Same day, same sun angle, same atmospheric correction, same weather, same
    crop calendar, adjacent ground. Regional greening or drought moves the ring
    and the footprint together and cancels. Construction moves only the
    footprint. Every headline number here is an *excess over the ring*.

**This corroborates. It does not prove.** A cleared pad is not a permitted
plant — Project Jupiter cleared ground and still had its pipeline right-of-way
denied twice. An empty parcel is not proof a project is dead — it may be in
procurement, or building somewhere else first. This is one observation to set
beside the permit pathway, not a substitute for it.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import struct
import zlib
from array import array
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from itertools import accumulate
from pathlib import Path
from typing import Any, Iterable, Sequence

import httpx

from providers.cache import ResponseCache

_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = _ROOT / "outputs" / "satellite"

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
SOURCE = (
    "Copernicus Sentinel-2 L2A via AWS Open Data (sentinel-cogs), "
    "searched through the Element 84 Earth Search STAC API. No credential."
)
SOURCE_URL = "https://registry.opendata.aws/sentinel-2-l2a-cogs/"

#: Ground sample distance of the bands the change metric runs on.
RESOLUTION_M = 10

#: DO NOT apply the STAC asset `raster:bands.offset`. It is there, it says
#: -0.1, and it is wrong for these files. Sentinel-2 L2A from processing
#: baseline 04.00 (Jan 2022) carries BOA_ADD_OFFSET = -1000, so the nominal
#: conversion is (DN - 1000) / 10000. The sentinel-cogs COGs are harmonized
#: back to the pre-04.00 convention, and the STAC metadata was not updated to
#: match. Measured over one pixel in South Memphis, same month, seven years:
#:
#:   2020-06-14  offset 0     red DN 642   NIR DN 3275
#:   2021-06-14  offset 0     red DN 546   NIR DN 3406
#:   2022-06-29  offset -0.1  red DN 687   NIR DN 3306
#:   2023-06-24  offset -0.1  red DN 664   NIR DN 3286
#:   2024-06-13  offset -0.1  red DN 639   NIR DN 3407
#:   2025-06-23  offset -0.1  red DN 636   NIR DN 3462
#:
#: There is no 1000-count step where the baseline changed, so the offset is
#: already in the bytes. Applying it again drives more than half the visible
#: band negative and pins NDVI at 1.0, which is what happened on the first run
#: of this module. Flip this to True only if that table stops holding.
APPLY_STAC_OFFSET = False

#: STAC asset keys this module reads. B11 and SCL are 20 m and are sampled
#: nearest-neighbour onto the 10 m grid; that is stated rather than hidden.
_ASSETS = ("blue", "green", "red", "nir", "swir16", "scl")

#: Sentinel-2 Scene Classification Layer values that make a pixel unusable.
#: 0 no data, 1 saturated/defective, 3 cloud shadow, 8 cloud medium probability,
#: 9 cloud high probability, 10 thin cirrus, 11 snow or ice.
_SCL_BAD = frozenset({0, 1, 3, 8, 9, 10, 11})
_SCL_LABEL = {
    0: "no_data", 1: "saturated", 2: "dark_area", 3: "cloud_shadow",
    4: "vegetation", 5: "not_vegetated", 6: "water", 7: "unclassified",
    8: "cloud_medium_prob", 9: "cloud_high_prob", 10: "thin_cirrus",
    11: "snow_or_ice",
}

#: Refuse above this fraction of the footprint being cloud, shadow or snow.
MAX_AOI_CLOUD = 0.10
#: Stop probing as soon as a scene is this clean. Between this and MAX_AOI_CLOUD
#: a scene is usable but kept only if nothing better turns up in the budget.
CLEAN_AOI_CLOUD = 0.02
#: Refuse below this fraction of the footprint being usable at all.
MIN_AOI_VALID = 0.60

#: Whole-tile pre-filter before we spend a read on the SCL band. Deliberately
#: loose: a 40%-cloudy tile is often a clear parcel.
MAX_SCENE_CLOUD_PCT = 60.0
#: How many candidate scenes per window we are willing to read SCL for.
MAX_SCL_PROBES = 10
#: Days either side of the announced groundbreaking date that a baseline scene
#: may come from, and how far back a "recent" scene may come from. Both are
#: wide on purpose: a refusal because the only nearby scene was cloudy is a
#: worse answer than a dated scene the reader can discount for themselves.
BASELINE_WINDOW_DAYS = 180
RECENT_WINDOW_DAYS = 400

# -- change metric thresholds ------------------------------------------------
#
# These are screening thresholds, not a calibrated classifier. They are stated
# here, in one block, so anyone can move them and re-run.

#: A pixel counts as disturbed when NDVI falls by at least this much AND the
#: bare-soil index rises by at least _BSI_RISE. Requiring both is the point:
#: NDVI alone moves on drought and harvest.
_NDVI_DROP = 0.15
_BSI_RISE = 0.05
#: Arid ground has no vegetation to lose, so the pair test above cannot fire.
#: The second detector is brightening on already-bare ground: fresh cut, graded
#: caliche and gravel pads are brighter than undisturbed desert crust.
_BRIGHT_RISE = 0.030
_ARID_NDVI = 0.25
#: Bright and unvegetated in the recent scene: concrete, metal roof, new asphalt.
#: Bare soil in the visible sits around 0.12-0.22; roofs and concrete run higher.
_BUILT_BRIGHT = 0.22
_BUILT_NDVI = 0.15

#: Verdict ladder, on excess disturbed fraction over the control ring.
_T_CLEARING = 0.05
_T_EARTHWORKS = 0.15
_T_STRUCTURES = 0.40
#: `structures_present` additionally needs this much of the footprint reading as
#: bright and unvegetated. Without it the verdict is capped one rung down,
#: because a gravel laydown yard and a concrete slab are the same pixel at 10 m.
_T_BUILT_FRACTION = 0.15

VERDICTS = (
    "no_visible_activity",
    "clearing_underway",
    "earthworks_or_foundations",
    "structures_present",
    "insufficient_imagery",
)

#: The fastest buildout in this repo's own backtest, used only as a sanity
#: bound on an announced schedule. xAI Colossus 1: 122 days from site
#: announcement to first cluster training — and that was a retrofit of an
#: existing factory building with trailer-mounted turbines, which is the
#: fastest possible case and not a normal one. See backtest/cases.py.
FASTEST_OBSERVED_MONTHS = 4.0

_DAYS_PER_MONTH = 30.4375


#: Log prefix that means the catalog was unreachable, as opposed to reachable
#: and cloudy. The two are different answers and the output says which.
_SEARCH_FAILED = "scene search failed"


class SatelliteError(RuntimeError):
    """Imagery could not be obtained or read. Never raised out of
    `verify_construction` — it becomes `insufficient_imagery`."""


# --------------------------------------------------------------------------
# Geodesy — WGS84 to UTM, closed form
# --------------------------------------------------------------------------
#
# Snyder, USGS Professional Paper 1395, eqs 8-9 to 8-11. Sub-millimetre inside
# a zone, which is four orders of magnitude better than a 10 m pixel needs. It
# is here so the module has no projection dependency; the EPSG code and the
# pixel transform both come from the STAC item, so this is the only piece of
# geo-referencing we own.

_A = 6378137.0
_F = 1.0 / 298.257223563
_E2 = _F * (2.0 - _F)
_EP2 = _E2 / (1.0 - _E2)
_K0 = 0.9996


def utm_zone_for(lon: float) -> int:
    return int(math.floor((lon + 180.0) / 6.0)) + 1


def epsg_for(lat: float, lon: float) -> int:
    zone = utm_zone_for(lon)
    return (32600 if lat >= 0 else 32700) + zone


def lonlat_to_utm(lat: float, lon: float, epsg: int) -> tuple[float, float]:
    """Geodetic WGS84 to UTM easting/northing in the given EPSG."""
    if not (32601 <= epsg <= 32660 or 32701 <= epsg <= 32760):
        raise SatelliteError(f"EPSG {epsg} is not a WGS84 UTM zone; refusing to guess a transform")
    zone = epsg % 100
    southern = epsg >= 32700
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    phi = math.radians(lat)
    lam = math.radians(lon)
    sin_phi, cos_phi, tan_phi = math.sin(phi), math.cos(phi), math.tan(phi)

    n = _A / math.sqrt(1.0 - _E2 * sin_phi * sin_phi)
    t = tan_phi * tan_phi
    c = _EP2 * cos_phi * cos_phi
    a_ = (lam - lon0) * cos_phi

    m = _A * (
        (1 - _E2 / 4 - 3 * _E2**2 / 64 - 5 * _E2**3 / 256) * phi
        - (3 * _E2 / 8 + 3 * _E2**2 / 32 + 45 * _E2**3 / 1024) * math.sin(2 * phi)
        + (15 * _E2**2 / 256 + 45 * _E2**3 / 1024) * math.sin(4 * phi)
        - (35 * _E2**3 / 3072) * math.sin(6 * phi)
    )

    easting = _K0 * n * (
        a_
        + (1 - t + c) * a_**3 / 6
        + (5 - 18 * t + t * t + 72 * c - 58 * _EP2) * a_**5 / 120
    ) + 500000.0

    northing = _K0 * (
        m
        + n * tan_phi * (
            a_**2 / 2
            + (5 - t + 9 * c + 4 * c * c) * a_**4 / 24
            + (61 - 58 * t + t * t + 600 * c - 330 * _EP2) * a_**6 / 720
        )
    )
    if southern:
        northing += 10000000.0
    return easting, northing


# --------------------------------------------------------------------------
# A windowed COG reader
# --------------------------------------------------------------------------
#
# A cloud-optimized GeoTIFF is a tiled TIFF whose header sits at the front of
# the file, so a client that can do HTTP range requests can read a 300x300
# window out of a 220 MB scene by pulling the header and one or two tiles.
# That is the whole point of the format and it is about 150 lines to use it
# directly.
#
# Sentinel-2 L2A COGs on AWS are classic little-endian TIFF, one uint16 (uint8
# for SCL) sample per pixel, Adobe Deflate with horizontal differencing
# (predictor 2), 1024x1024 tiles at full resolution. Everything else raises.

_TIFF_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
_TIFF_TYPE_FMT = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d"}

_TAG_WIDTH = 256
_TAG_HEIGHT = 257
_TAG_BITS = 258
_TAG_COMPRESSION = 259
_TAG_SAMPLES = 277
_TAG_PREDICTOR = 317
_TAG_TILE_WIDTH = 322
_TAG_TILE_HEIGHT = 323
_TAG_TILE_OFFSETS = 324
_TAG_TILE_BYTES = 325
_TAG_SAMPLE_FORMAT = 339

_HEADER_BYTES = 32768


@dataclass
class _Window:
    """A rectangle of pixel values read out of one band, plus where it came from."""

    values: list[array]  # one array per row, native typecode
    col0: int
    row0: int
    width: int
    height: int


class CogReader:
    """Reads a pixel window from a remote COG over HTTP range requests.

    Everything is cached by (href, window) through the same SQLite response
    cache the Mireye client uses, so re-running the backtest is free and the
    chips are reproducible byte for byte.
    """

    def __init__(self, client: httpx.Client, cache: ResponseCache | None = None):
        self._client = client
        self._cache = cache
        self._headers: dict[str, bytes] = {}

    # -- HTTP ----------------------------------------------------------------

    def _range(self, href: str, start: int, length: int) -> bytes:
        end = start + length - 1
        resp = self._client.get(href, headers={"Range": f"bytes={start}-{end}"})
        if resp.status_code not in (200, 206):
            raise SatelliteError(f"{resp.status_code} reading {href} bytes {start}-{end}")
        return resp.content

    # -- TIFF ----------------------------------------------------------------

    def _header(self, href: str) -> bytes:
        blob = self._headers.get(href)
        if blob is None:
            blob = self._range(href, 0, _HEADER_BYTES)
            self._headers[href] = blob
        return blob

    def _ifd0(self, href: str) -> dict[int, tuple[int, int, int]]:
        """Parse the first IFD. Returns {tag: (type, count, value_offset)}."""
        blob = self._header(href)
        if blob[:2] != b"II":
            raise SatelliteError(f"{href}: not a little-endian TIFF (got {blob[:2]!r})")
        if struct.unpack_from("<H", blob, 2)[0] != 42:
            raise SatelliteError(f"{href}: BigTIFF is not supported by this reader")
        offset = struct.unpack_from("<I", blob, 4)[0]
        count = struct.unpack_from("<H", blob, offset)[0]
        tags: dict[int, tuple[int, int, int]] = {}
        for i in range(count):
            pos = offset + 2 + i * 12
            tag, typ, n = struct.unpack_from("<HHI", blob, pos)
            size = _TIFF_TYPE_SIZE.get(typ, 1) * n
            value_offset = pos + 8 if size <= 4 else struct.unpack_from("<I", blob, pos + 8)[0]
            tags[tag] = (typ, n, value_offset)
        return tags

    def _tag(self, href: str, tags: dict, tag: int, default: Any = None) -> Any:
        entry = tags.get(tag)
        if entry is None:
            return default
        typ, n, offset = entry
        fmt = _TIFF_TYPE_FMT.get(typ)
        if fmt is None:
            raise SatelliteError(f"{href}: unsupported TIFF value type {typ} on tag {tag}")
        blob = self._header(href)
        need = offset + _TIFF_TYPE_SIZE[typ] * n
        if need > len(blob):
            # The tile offset array can sit past the header block we pulled.
            extra = self._range(href, len(blob), need - len(blob) + 4096)
            blob = blob + extra
            self._headers[href] = blob
        values = struct.unpack_from("<" + fmt * n, blob, offset)
        return values[0] if n == 1 else list(values)

    # -- pixels --------------------------------------------------------------

    def read_window(self, href: str, col0: int, row0: int, width: int, height: int) -> _Window:
        key = {"href": href, "col0": col0, "row0": row0, "w": width, "h": height, "v": 1}
        if self._cache is not None:
            hit = self._cache.get("sentinel2_cog_window", key)
            if hit is not None and hit.ok:
                body = hit.body
                raw = base64.b64decode(body["b64"])
                code = body["typecode"]
                rows = []
                stride = width * (2 if code == "H" else 1)
                for r in range(height):
                    a = array(code)
                    a.frombytes(raw[r * stride:(r + 1) * stride])
                    rows.append(a)
                return _Window(rows, col0, row0, width, height)

        window = self._read_window_uncached(href, col0, row0, width, height)
        if self._cache is not None:
            code = window.values[0].typecode if window.values else "H"
            raw = b"".join(row.tobytes() for row in window.values)
            self._cache.set(
                "sentinel2_cog_window",
                key,
                200,
                {"typecode": code, "b64": base64.b64encode(raw).decode("ascii")},
                credits=0.0,
            )
        return window

    def _read_window_uncached(
        self, href: str, col0: int, row0: int, width: int, height: int
    ) -> _Window:
        tags = self._ifd0(href)
        img_w = self._tag(href, tags, _TAG_WIDTH)
        img_h = self._tag(href, tags, _TAG_HEIGHT)
        bits = self._tag(href, tags, _TAG_BITS, 16)
        compression = self._tag(href, tags, _TAG_COMPRESSION, 1)
        samples = self._tag(href, tags, _TAG_SAMPLES, 1)
        predictor = self._tag(href, tags, _TAG_PREDICTOR, 1)
        sample_format = self._tag(href, tags, _TAG_SAMPLE_FORMAT, 1)
        tile_w = self._tag(href, tags, _TAG_TILE_WIDTH)
        tile_h = self._tag(href, tags, _TAG_TILE_HEIGHT)
        offsets = self._tag(href, tags, _TAG_TILE_OFFSETS)
        byte_counts = self._tag(href, tags, _TAG_TILE_BYTES)

        if samples != 1:
            raise SatelliteError(f"{href}: {samples} samples per pixel; this reader handles 1")
        if bits not in (8, 16):
            raise SatelliteError(f"{href}: {bits}-bit samples are not supported")
        if sample_format != 1:
            raise SatelliteError(f"{href}: sample format {sample_format} is not unsigned integer")
        if compression not in (1, 8, 32946):
            raise SatelliteError(
                f"{href}: compression {compression}; this reader handles none and deflate only"
            )
        if predictor not in (1, 2):
            raise SatelliteError(f"{href}: predictor {predictor} is not supported")
        if tile_w is None or offsets is None:
            raise SatelliteError(f"{href}: not tiled; stripped TIFFs are not supported")
        if isinstance(offsets, int):
            offsets, byte_counts = [offsets], [byte_counts]

        code = "H" if bits == 16 else "B"
        mask = 0xFFFF if bits == 16 else 0xFF
        tiles_across = (img_w + tile_w - 1) // tile_w

        col0 = max(0, min(col0, img_w - 1))
        row0 = max(0, min(row0, img_h - 1))
        width = max(1, min(width, img_w - col0))
        height = max(1, min(height, img_h - row0))

        out = [array(code, bytes(width * (2 if code == "H" else 1))) for _ in range(height)]

        first_tx, last_tx = col0 // tile_w, (col0 + width - 1) // tile_w
        first_ty, last_ty = row0 // tile_h, (row0 + height - 1) // tile_h

        for ty in range(first_ty, last_ty + 1):
            for tx in range(first_tx, last_tx + 1):
                index = ty * tiles_across + tx
                if index >= len(offsets):
                    continue
                blob = self._range(href, offsets[index], byte_counts[index])
                if compression in (8, 32946):
                    blob = zlib.decompress(blob)

                # Rows we actually need out of this tile, and the last column we
                # need. Predictor 2 is a running difference from column 0, so a
                # row has to be reconstructed from its start — but only the rows
                # in the window, and only up to the last column in the window.
                r_lo = max(row0, ty * tile_h) - ty * tile_h
                r_hi = min(row0 + height, (ty + 1) * tile_h) - ty * tile_h
                c_lo = max(col0, tx * tile_w) - tx * tile_w
                c_hi = min(col0 + width, (tx + 1) * tile_w) - tx * tile_w

                item = 2 if code == "H" else 1
                row_bytes = tile_w * item
                for r in range(r_lo, r_hi):
                    src = array(code)
                    src.frombytes(blob[r * row_bytes:(r + 1) * row_bytes])
                    if predictor == 2:
                        running = [v & mask for v in accumulate(src[:c_hi])]
                        segment = running[c_lo:c_hi]
                    else:
                        segment = src[c_lo:c_hi]
                    dest_row = ty * tile_h + r - row0
                    dest_col = tx * tile_w + c_lo - col0
                    out[dest_row][dest_col:dest_col + (c_hi - c_lo)] = array(code, segment)

        return _Window(out, col0, row0, width, height)


# --------------------------------------------------------------------------
# STAC
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Scene:
    """One Sentinel-2 acquisition, with everything needed to check the claim."""

    scene_id: str
    acquired: str            # ISO 8601 UTC
    platform: str
    scene_cloud_pct: float   # eo:cloud_cover, whole 110 km tile
    epsg: int
    mgrs: str
    assets: dict[str, dict]  # asset key -> {href, transform, shape}
    aoi_cloud_pct: float | None = None
    aoi_valid_pct: float | None = None

    @property
    def acquired_date(self) -> str:
        return self.acquired[:10]

    def cited(self) -> str:
        cloud = (
            f"{self.aoi_cloud_pct:.1f}% over the footprint"
            if self.aoi_cloud_pct is not None
            else f"{self.scene_cloud_pct:.1f}% over the tile"
        )
        return f"{self.scene_id} acquired {self.acquired_date}, cloud {cloud}"

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "acquired": self.acquired,
            "platform": self.platform,
            "scene_cloud_pct": round(self.scene_cloud_pct, 2),
            "aoi_cloud_pct": None if self.aoi_cloud_pct is None else round(self.aoi_cloud_pct, 2),
            "aoi_valid_pct": None if self.aoi_valid_pct is None else round(self.aoi_valid_pct, 2),
            "epsg": self.epsg,
            "mgrs": self.mgrs,
            "source": SOURCE,
            "source_url": SOURCE_URL,
        }


def _scene_from_item(item: dict) -> Scene | None:
    props = item.get("properties") or {}
    epsg = props.get("proj:epsg")
    if not isinstance(epsg, int):
        return None
    assets = {}
    for key in _ASSETS:
        entry = (item.get("assets") or {}).get(key)
        if not entry or not entry.get("href"):
            return None
        transform = entry.get("proj:transform") or props.get("proj:transform")
        shape = entry.get("proj:shape") or props.get("proj:shape")
        if not transform or not shape:
            return None
        bands = (entry.get("raster:bands") or [{}])[0]
        assets[key] = {
            "href": entry["href"],
            "transform": list(transform),
            "shape": list(shape),
            "scale": bands.get("scale"),
            "offset": bands.get("offset"),
            "nodata": bands.get("nodata"),
        }
    return Scene(
        scene_id=item.get("id", "?"),
        acquired=props.get("datetime") or "",
        platform=props.get("platform") or "sentinel-2",
        scene_cloud_pct=float(props.get("eo:cloud_cover") or 0.0),
        epsg=epsg,
        mgrs=props.get("grid:code") or "",
        assets=assets,
    )


def search_scenes(
    client: httpx.Client,
    lat: float,
    lon: float,
    start: date,
    end: date,
    cache: ResponseCache | None = None,
    max_cloud_pct: float = MAX_SCENE_CLOUD_PCT,
    limit: int = 100,
) -> list[Scene]:
    """Scenes covering the point in a date window, newest first.

    The whole-tile cloud filter here is only a pre-filter — it decides which
    scenes are worth spending an SCL read on. The cloud number that governs the
    verdict is measured over the footprint later.
    """
    body = {
        "collections": [COLLECTION],
        "intersects": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": limit,
        "query": {"eo:cloud_cover": {"lt": max_cloud_pct}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }

    payload = None
    if cache is not None:
        hit = cache.get("sentinel2_stac_search", body, max_age_days=1.0)
        if hit is not None and hit.ok:
            payload = hit.body
    if payload is None:
        resp = client.post(STAC_URL, json=body)
        if resp.status_code != 200:
            raise SatelliteError(f"STAC search returned {resp.status_code}: {resp.text[:200]}")
        payload = resp.json()
        if cache is not None:
            cache.set("sentinel2_stac_search", body, 200, payload, credits=0.0)

    # A point on a UTM zone boundary is served by two MGRS tiles in two
    # different projections. Prefer the tile in the zone the longitude actually
    # falls in, so the two scenes we compare share one pixel grid.
    natural = epsg_for(lat, lon)
    scenes = [s for s in (_scene_from_item(i) for i in payload.get("features", [])) if s]
    preferred = [s for s in scenes if s.epsg == natural]
    return preferred or scenes


# --------------------------------------------------------------------------
# Reading a footprint out of a scene
# --------------------------------------------------------------------------


@dataclass
class _Grid:
    """The pixel window read for one scene, and the masks over it."""

    width: int
    height: int
    ndvi: list[float | None]
    bsi: list[float | None]
    bright: list[float | None]
    scl: list[int]
    aoi: list[bool]
    ring: list[bool]
    rgb: list[tuple[float, float, float] | None]


def _window_origin(transform: Sequence[float], easting: float, northing: float) -> tuple[float, float]:
    """Fractional (col, row) of a UTM coordinate under a GDAL-order transform."""
    px, _, ox, _, py, oy = transform[:6]
    return (easting - ox) / px, (northing - oy) / py


def _read_grid(
    reader: CogReader,
    scene: Scene,
    lat: float,
    lon: float,
    radius_m: float,
    ring_factor: float,
) -> _Grid:
    """Read one scene over the footprint and its control ring, at 10 m."""
    easting, northing = lonlat_to_utm(lat, lon, scene.epsg)
    half_m = radius_m * ring_factor
    span_px = int(round(2 * half_m / RESOLUTION_M))
    span_px = max(8, span_px)

    ten_m = scene.assets["red"]["transform"]
    cx, cy = _window_origin(ten_m, easting, northing)
    col0 = int(round(cx - span_px / 2))
    row0 = int(round(cy - span_px / 2))

    windows: dict[str, _Window] = {}
    for key in _ASSETS:
        asset = scene.assets[key]
        px = abs(asset["transform"][0])
        factor = px / RESOLUTION_M  # 1 for 10 m bands, 2 for 20 m bands
        acol, arow = _window_origin(asset["transform"], easting, northing)
        a_span = int(math.ceil(span_px / factor)) + 1
        a_col0 = int(round(acol - a_span / 2))
        a_row0 = int(round(arow - a_span / 2))
        windows[key] = reader.read_window(asset["href"], a_col0, a_row0, a_span, a_span)

    # Centre of the 10 m window in its own pixel coordinates, so distance from
    # the site is measured in metres rather than assumed to be the array centre.
    centre_col = cx - windows["red"].col0
    centre_row = cy - windows["red"].row0

    def sample(key: str, r: int, c: int) -> int:
        """Value at 10 m grid cell (r, c), nearest-neighbour from its own grid."""
        w = windows[key]
        factor = abs(scene.assets[key]["transform"][0]) / RESOLUTION_M
        if factor == 1.0:
            rr, cc = r, c
        else:
            rr = int((row0 + r) / factor) - w.row0
            cc = int((col0 + c) / factor) - w.col0
        if 0 <= rr < w.height and 0 <= cc < w.width:
            return w.values[rr][cc]
        return 0

    def reflect(key: str, raw: int) -> float | None:
        asset = scene.assets[key]
        nodata = asset.get("nodata")
        if raw == 0 or (nodata is not None and raw == nodata):
            return None
        scale = asset.get("scale") or 0.0001
        offset = asset.get("offset") if APPLY_STAC_OFFSET else 0.0
        value = raw * scale + (offset or 0.0)
        # Surface reflectance is bounded. Clamp rather than drop; a saturated
        # pixel is still an observation.
        return max(0.0, min(1.6, value))

    n = span_px * span_px
    ndvi: list[float | None] = [None] * n
    bsi: list[float | None] = [None] * n
    bright: list[float | None] = [None] * n
    rgb: list[tuple[float, float, float] | None] = [None] * n
    scl_out = [0] * n
    aoi = [False] * n
    ring = [False] * n

    r_in2 = radius_m * radius_m
    r_out2 = (radius_m * ring_factor) ** 2

    for r in range(span_px):
        dy = (r + 0.5 - centre_row) * RESOLUTION_M
        for c in range(span_px):
            i = r * span_px + c
            dx = (c + 0.5 - centre_col) * RESOLUTION_M
            d2 = dx * dx + dy * dy
            if d2 <= r_in2:
                aoi[i] = True
            elif d2 <= r_out2:
                ring[i] = True

            scl_out[i] = sample("scl", r, c)

            blue = reflect("blue", sample("blue", r, c))
            green = reflect("green", sample("green", r, c))
            red = reflect("red", sample("red", r, c))
            nir = reflect("nir", sample("nir", r, c))
            swir = reflect("swir16", sample("swir16", r, c))
            if None in (blue, green, red, nir):
                continue

            rgb[i] = (red, green, blue)
            bright[i] = (blue + green + red) / 3.0

            denom = nir + red
            if denom > 1e-6:
                ndvi[i] = (nir - red) / denom
            if swir is not None:
                num = (swir + red) - (nir + blue)
                den = (swir + red) + (nir + blue)
                if abs(den) > 1e-6:
                    bsi[i] = num / den

    return _Grid(span_px, span_px, ndvi, bsi, bright, scl_out, aoi, ring, rgb)


def _cloud_stats(grid: _Grid) -> tuple[float, float, dict[str, float]]:
    """Footprint cloud/shadow/snow fraction, usable fraction, and the SCL histogram."""
    total = bad = usable = 0
    hist: dict[int, int] = {}
    for i, inside in enumerate(grid.aoi):
        if not inside:
            continue
        total += 1
        cls = grid.scl[i]
        hist[cls] = hist.get(cls, 0) + 1
        if cls in _SCL_BAD:
            bad += 1
        elif grid.ndvi[i] is not None:
            usable += 1
    if total == 0:
        return 100.0, 0.0, {}
    named = {
        _SCL_LABEL.get(k, str(k)): round(100.0 * v / total, 2)
        for k, v in sorted(hist.items(), key=lambda kv: -kv[1])
        if v
    }
    return 100.0 * bad / total, 100.0 * usable / total, named


# --------------------------------------------------------------------------
# Scene selection
# --------------------------------------------------------------------------


def _pick_scene(
    reader: CogReader,
    client: httpx.Client,
    lat: float,
    lon: float,
    radius_m: float,
    ring_factor: float,
    start: date,
    end: date,
    order: str,
    target: date | None,
    cache: ResponseCache | None,
    require_epsg: int | None = None,
    probe_limit: int = MAX_SCL_PROBES,
) -> tuple[Scene | None, _Grid | None, list[str]]:
    """Find the first scene in a window that is clear enough over the footprint.

    Two stages, because SCL is a real read. Stage one is the catalog's whole-tile
    cloud percentage, which is free and wrong at parcel scale. Stage two reads
    the scene's own SCL band over the footprint and is what the verdict uses.

    One wide window with a probe budget, rather than a widening loop: widening
    re-sorts to the same nearest-in-time scenes and would re-probe the ones that
    just failed.
    """
    log: list[str] = []
    try:
        scenes = search_scenes(client, lat, lon, start, end, cache=cache)
    except (httpx.HTTPError, SatelliteError) as exc:
        log.append(f"{_SEARCH_FAILED} for {start}..{end}: {exc}")
        return None, None, log

    if require_epsg is not None:
        same = [s for s in scenes if s.epsg == require_epsg]
        if len(same) < len(scenes):
            log.append(
                f"dropped {len(scenes) - len(same)} scene(s) in a different UTM zone so both "
                f"dates sit on one pixel grid"
            )
        scenes = same

    if not scenes:
        log.append(
            f"no Sentinel-2 scene under {MAX_SCENE_CLOUD_PCT:.0f}% tile cloud between "
            f"{start} and {end}"
        )
        return None, None, log

    if order == "nearest" and target is not None:
        # Bucket by fortnight, then prefer the cleaner tile inside the bucket.
        # Straight nearest-in-time picks a hazy scene over a clean one five days
        # further out, and a hazy baseline is what a false clearing signal looks
        # like. This is the ordering only; the gate below is still SCL.
        scenes.sort(
            key=lambda s: (
                abs((_parse_iso(s.acquired_date) - target).days) // 15,
                round(s.scene_cloud_pct),
                abs((_parse_iso(s.acquired_date) - target).days),
            )
        )
    else:
        scenes.sort(key=lambda s: s.acquired, reverse=True)

    best: tuple[Scene, _Grid] | None = None
    for scene in scenes[:probe_limit]:
        try:
            grid = _read_grid(reader, scene, lat, lon, radius_m, ring_factor)
        except (httpx.HTTPError, SatelliteError, zlib.error) as exc:
            log.append(f"{scene.scene_id}: read failed ({exc})")
            continue
        cloud, valid, hist = _cloud_stats(grid)
        scene = Scene(**{**asdict_scene(scene), "aoi_cloud_pct": cloud, "aoi_valid_pct": valid})
        if cloud > MAX_AOI_CLOUD * 100 or valid < MIN_AOI_VALID * 100:
            log.append(
                f"{scene.scene_id} ({scene.acquired_date}): rejected, "
                f"{cloud:.1f}% of the footprint is cloud/shadow/snow, {valid:.1f}% usable "
                f"({', '.join(f'{k} {v}%' for k, v in list(hist.items())[:3])})"
            )
            continue

        if best is None or cloud < (best[0].aoi_cloud_pct or 100.0):
            best = (scene, grid)

        if cloud <= CLEAN_AOI_CLOUD * 100:
            log.append(
                f"{scene.scene_id} ({scene.acquired_date}): accepted, "
                f"{cloud:.1f}% footprint cloud, {valid:.1f}% usable, "
                f"{scene.scene_cloud_pct:.1f}% over the whole tile"
            )
            return scene, grid, log

        log.append(
            f"{scene.scene_id} ({scene.acquired_date}): usable at {cloud:.1f}% footprint cloud "
            f"but not clean; still looking for one under {CLEAN_AOI_CLOUD * 100:.0f}%"
        )

    if best is not None:
        scene, grid = best
        log.append(
            f"{scene.scene_id} ({scene.acquired_date}): accepted as the cleanest of "
            f"{min(len(scenes), probe_limit)} probed, {scene.aoi_cloud_pct:.1f}% footprint cloud. "
            f"Residual haze and cloud shadow move reflectance, so read the change metric with "
            f"that in mind."
        )
        return scene, grid, log

    log.append(
        f"probed {min(len(scenes), probe_limit)} of {len(scenes)} scene(s) between {start} and "
        f"{end}; none had the footprint under {MAX_AOI_CLOUD * 100:.0f}% cloud"
    )
    return None, None, log


def asdict_scene(scene: Scene) -> dict:
    return {
        "scene_id": scene.scene_id,
        "acquired": scene.acquired,
        "platform": scene.platform,
        "scene_cloud_pct": scene.scene_cloud_pct,
        "epsg": scene.epsg,
        "mgrs": scene.mgrs,
        "assets": scene.assets,
        "aoi_cloud_pct": scene.aoi_cloud_pct,
        "aoi_valid_pct": scene.aoi_valid_pct,
    }


# --------------------------------------------------------------------------
# The change metric
# --------------------------------------------------------------------------


def _mean(values: Iterable[float]) -> float | None:
    total = count = 0.0
    for v in values:
        total += v
        count += 1
    return total / count if count else None


@dataclass
class ZoneChange:
    """Change over one zone — the footprint, or the control ring."""

    pixels: int
    ndvi_before: float | None
    ndvi_after: float | None
    bsi_before: float | None
    bsi_after: float | None
    bright_before: float | None
    bright_after: float | None
    disturbed_fraction: float
    built_fraction: float

    @property
    def ndvi_delta(self) -> float | None:
        if self.ndvi_before is None or self.ndvi_after is None:
            return None
        return self.ndvi_after - self.ndvi_before

    @property
    def bsi_delta(self) -> float | None:
        if self.bsi_before is None or self.bsi_after is None:
            return None
        return self.bsi_after - self.bsi_before

    @property
    def bright_delta(self) -> float | None:
        if self.bright_before is None or self.bright_after is None:
            return None
        return self.bright_after - self.bright_before

    def to_dict(self) -> dict:
        def r(v: float | None, n: int = 4) -> float | None:
            return None if v is None else round(v, n)

        return {
            "pixels": self.pixels,
            "area_ha": round(self.pixels * RESOLUTION_M**2 / 10000.0, 1),
            "ndvi_before": r(self.ndvi_before, 3),
            "ndvi_after": r(self.ndvi_after, 3),
            "ndvi_delta": r(self.ndvi_delta, 3),
            "bsi_before": r(self.bsi_before, 3),
            "bsi_after": r(self.bsi_after, 3),
            "bsi_delta": r(self.bsi_delta, 3),
            "brightness_before": r(self.bright_before, 3),
            "brightness_after": r(self.bright_after, 3),
            "brightness_delta": r(self.bright_delta, 3),
            "disturbed_fraction": r(self.disturbed_fraction, 3),
            "built_fraction": r(self.built_fraction, 3),
        }


def _pixel_disturbed(
    ndvi_a: float | None, ndvi_b: float | None,
    bsi_a: float | None, bsi_b: float | None,
    bright_a: float | None, bright_b: float | None,
) -> bool:
    """Two detectors, either of which marks a pixel disturbed.

    A. Vegetated ground that lost vegetation AND gained bare-soil signal.
       Requiring both is what rejects drought and harvest: a harvested field
       loses NDVI and gains BSI too, which is why the control ring exists on
       top of this, not instead of it.

    B. Already-bare ground that got brighter without greening. Desert parcels
       have no vegetation to lose, so A cannot fire on them; grading fresh
       caliche or laying a gravel pad raises visible reflectance.
    """
    if None not in (ndvi_a, ndvi_b, bsi_a, bsi_b):
        if (ndvi_a - ndvi_b) >= _NDVI_DROP and (bsi_b - bsi_a) >= _BSI_RISE:
            return True
    if None not in (ndvi_a, ndvi_b, bright_a, bright_b):
        if (
            ndvi_b < _ARID_NDVI
            and ndvi_b <= ndvi_a
            and (bright_b - bright_a) >= _BRIGHT_RISE
        ):
            return True
    return False


def _zone_change(before: _Grid, after: _Grid, zone: str) -> tuple[ZoneChange, list[bool]]:
    mask_attr = before.aoi if zone == "aoi" else before.ring
    n = min(len(before.ndvi), len(after.ndvi))

    nb, na, bb, ba, rb, ra = [], [], [], [], [], []
    disturbed = [False] * n
    disturbed_count = built_count = usable = 0

    for i in range(n):
        if not mask_attr[i]:
            continue
        if before.scl[i] in _SCL_BAD or after.scl[i] in _SCL_BAD:
            continue
        if before.ndvi[i] is None or after.ndvi[i] is None:
            continue
        usable += 1
        nb.append(before.ndvi[i])
        na.append(after.ndvi[i])
        if before.bsi[i] is not None:
            bb.append(before.bsi[i])
        if after.bsi[i] is not None:
            ba.append(after.bsi[i])
        if before.bright[i] is not None:
            rb.append(before.bright[i])
        if after.bright[i] is not None:
            ra.append(after.bright[i])

        if _pixel_disturbed(
            before.ndvi[i], after.ndvi[i],
            before.bsi[i], after.bsi[i],
            before.bright[i], after.bright[i],
        ):
            disturbed[i] = True
            disturbed_count += 1

        if (
            after.bright[i] is not None
            and after.bright[i] >= _BUILT_BRIGHT
            and after.ndvi[i] < _BUILT_NDVI
        ):
            built_count += 1

    change = ZoneChange(
        pixels=usable,
        ndvi_before=_mean(nb), ndvi_after=_mean(na),
        bsi_before=_mean(bb), bsi_after=_mean(ba),
        bright_before=_mean(rb), bright_after=_mean(ra),
        disturbed_fraction=(disturbed_count / usable) if usable else 0.0,
        built_fraction=(built_count / usable) if usable else 0.0,
    )
    return change, disturbed


def _classify(aoi: ZoneChange, ring: ZoneChange) -> tuple[str, float, list[str]]:
    """Verdict from excess disturbance over the control ring."""
    excess = aoi.disturbed_fraction - ring.disturbed_fraction
    reasons = [
        f"{aoi.disturbed_fraction * 100:.1f}% of the footprint changed from vegetated to bare "
        f"or from bare to brighter-bare; the control ring moved {ring.disturbed_fraction * 100:.1f}% "
        f"on the same two scenes, so the excess attributable to this parcel is {excess * 100:.1f}%."
    ]

    ndvi_excess = None
    if aoi.ndvi_delta is not None and ring.ndvi_delta is not None:
        ndvi_excess = aoi.ndvi_delta - ring.ndvi_delta
        reasons.append(
            f"Mean NDVI over the footprint moved {aoi.ndvi_delta:+.3f}; the ring moved "
            f"{ring.ndvi_delta:+.3f}. Excess {ndvi_excess:+.3f}."
        )

    if excess < _T_CLEARING:
        if ndvi_excess is not None and ndvi_excess < -0.05:
            reasons.append(
                "NDVI is down against the ring but too few pixels cross both thresholds "
                "to call it clearing. Read this as a watch item, not as activity."
            )
        return "no_visible_activity", excess, reasons

    if excess < _T_EARTHWORKS:
        return "clearing_underway", excess, reasons

    if excess < _T_STRUCTURES:
        return "earthworks_or_foundations", excess, reasons

    if aoi.built_fraction >= _T_BUILT_FRACTION:
        reasons.append(
            f"{aoi.built_fraction * 100:.1f}% of the footprint now reads bright "
            f"(visible reflectance >= {_BUILT_BRIGHT:.2f}) and unvegetated, which is the "
            f"signature of roofs, concrete or new pavement. At 10 m this cannot separate a "
            f"finished building from a slab or a gravel laydown yard."
        )
        return "structures_present", excess, reasons

    reasons.append(
        f"Excess disturbance is above {_T_STRUCTURES * 100:.0f}% but only "
        f"{aoi.built_fraction * 100:.1f}% of the footprint reads bright and unvegetated, under "
        f"the {_T_BUILT_FRACTION * 100:.0f}% needed to call structures. Held at earthworks."
    )
    return "earthworks_or_foundations", excess, reasons


# --------------------------------------------------------------------------
# PNG output
# --------------------------------------------------------------------------
#
# Written by hand because the alternative is a Pillow dependency for forty lines
# of zlib. Chips are the demo artefact, so the stretch is fixed rather than
# per-scene: a percentile stretch would make two dates look different because
# the histogram moved, which is exactly the thing we are trying to measure.

_STRETCH_LOW = 0.005
_STRETCH_HIGH = 0.26
_GAMMA = 0.62


def _png_bytes(pixels: list[tuple[int, int, int]], width: int, height: int) -> bytes:
    raw = bytearray()
    for r in range(height):
        raw.append(0)  # filter type 0, none
        row = pixels[r * width:(r + 1) * width]
        for px in row:
            raw.extend(px)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def _stretch(value: float | None) -> int:
    if value is None:
        return 0
    x = (value - _STRETCH_LOW) / (_STRETCH_HIGH - _STRETCH_LOW)
    x = max(0.0, min(1.0, x)) ** _GAMMA
    return int(round(x * 255))


def _render_chip(
    grid: _Grid,
    path: Path,
    scale: int,
    radius_px: float,
    overlay: list[bool] | None = None,
) -> Path:
    """True-colour chip with the footprint circle drawn, optionally with the
    disturbed-pixel mask painted over it."""
    w, h = grid.width, grid.height
    cx, cy = w / 2.0, h / 2.0
    base: list[tuple[int, int, int]] = []
    for r in range(h):
        for c in range(w):
            i = r * w + c
            px = grid.rgb[i]
            if px is None:
                rgb = (24, 24, 28)
            else:
                rgb = (_stretch(px[0]), _stretch(px[1]), _stretch(px[2]))

            if overlay is not None and i < len(overlay) and overlay[i]:
                # Warm wash, not a flat fill, so the underlying ground stays readable.
                rgb = (min(255, rgb[0] // 2 + 190), rgb[1] // 2 + 40, rgb[2] // 2)

            # Footprint boundary, one pixel wide.
            d = math.hypot(c + 0.5 - cx, r + 0.5 - cy)
            if abs(d - radius_px) < 0.6:
                rgb = (255, 255, 255)
            base.append(rgb)

    if scale > 1:
        big: list[tuple[int, int, int]] = []
        for r in range(h * scale):
            src = r // scale
            row = base[src * w:(src + 1) * w]
            for c in range(w * scale):
                big.append(row[c // scale])
        base, w, h = big, w * scale, h * scale

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png_bytes(base, w, h))
    return path


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_QUARTER = re.compile(r"\bQ([1-4])\s*(\d{4})\b", re.I)
_QUARTER_REV = re.compile(r"\b(\d{4})\s*Q([1-4])\b", re.I)
_YEAR_ONLY = re.compile(r"\b(19|20)\d{2}\b")
_QUARTER_START = {1: 1, 2: 4, 3: 7, 4: 10}


def _parse_iso(value: str) -> date:
    return date.fromisoformat(value)


def parse_announced(value: Any) -> tuple[date | None, str]:
    """Parse a date as a press release states it.

    Accepts a date, `YYYY-MM-DD`, `YYYY-MM`, `YYYY`, and `Q4 2026` / `2026 Q4`,
    because that is the form these dates are actually published in. Returns the
    date and how it was read, so the output can say "Q4 2026, read as 2026-10-01"
    rather than pretending to a precision the source did not have.
    """
    if value is None:
        return None, "not supplied"
    if isinstance(value, datetime):
        return value.date(), "datetime"
    if isinstance(value, date):
        return value, "date"

    text = str(value).strip()
    if not text:
        return None, "not supplied"

    try:
        return date.fromisoformat(text), "exact date"
    except ValueError:
        pass

    m = _QUARTER.search(text) or None
    q = y = None
    if m:
        q, y = int(m.group(1)), int(m.group(2))
    else:
        m = _QUARTER_REV.search(text)
        if m:
            y, q = int(m.group(1)), int(m.group(2))
    if q and y:
        return date(y, _QUARTER_START[q], 1), f"quarter {text!r}, read as the first day of Q{q} {y}"

    m = re.fullmatch(r"(\d{4})-(\d{1,2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1), f"month {text!r}, read as the first of the month"

    m = _YEAR_ONLY.search(text)
    if m:
        year = int(m.group(0))
        return date(year, 1, 1), f"year {year} taken from {text!r}, read as 1 January"

    return None, f"could not parse {text!r} as a date"


def _months_between(a: date, b: date) -> float:
    return (b - a).days / _DAYS_PER_MONTH


# --------------------------------------------------------------------------
# The verdict
# --------------------------------------------------------------------------


@dataclass
class ConstructionVerdict:
    """What the imagery says, with everything needed to check it."""

    verdict: str
    lat: float
    lon: float
    radius_m: float
    reasons: list[str] = field(default_factory=list)
    baseline: Scene | None = None
    recent: Scene | None = None
    aoi: ZoneChange | None = None
    ring: ZoneChange | None = None
    excess_disturbed: float | None = None
    schedule: dict = field(default_factory=dict)
    chips: list[str] = field(default_factory=list)
    scene_log: list[str] = field(default_factory=list)
    mireye: dict | None = None
    label: str | None = None

    @property
    def ok(self) -> bool:
        return self.verdict != "insufficient_imagery"

    def headline(self) -> str:
        if not self.ok:
            return f"insufficient_imagery — {self.reasons[0] if self.reasons else 'no usable scenes'}"
        return (
            f"{self.verdict} — {self.baseline.acquired_date} to {self.recent.acquired_date}, "
            f"{self.excess_disturbed * 100:.1f}% of the footprint disturbed above the control ring"
        )

    def citation(self) -> str:
        if self.baseline is None or self.recent is None:
            return SOURCE
        return (
            f"{self.baseline.cited()}; {self.recent.cited()}. Source: {SOURCE} "
            f"Resolution {RESOLUTION_M} m."
        )

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "label": self.label,
            "headline": self.headline(),
            "footprint": {
                "lat": self.lat,
                "lon": self.lon,
                "radius_m": self.radius_m,
                "area_ha": round(math.pi * self.radius_m**2 / 10000.0, 1),
            },
            "method": METHOD,
            "source": SOURCE,
            "source_url": SOURCE_URL,
            "resolution_m": RESOLUTION_M,
            "baseline_scene": self.baseline.to_dict() if self.baseline else None,
            "recent_scene": self.recent.to_dict() if self.recent else None,
            "footprint_change": self.aoi.to_dict() if self.aoi else None,
            "control_ring_change": self.ring.to_dict() if self.ring else None,
            "excess_disturbed_fraction": (
                None if self.excess_disturbed is None else round(self.excess_disturbed, 4)
            ),
            "reasons": self.reasons,
            "schedule": self.schedule,
            "chips": self.chips,
            "scene_selection_log": self.scene_log,
            "mireye_corroboration": self.mireye,
            "limits": LIMITS,
            "citation": self.citation(),
        }


METHOD = (
    "Two Sentinel-2 L2A scenes over a circular footprint, differenced against the "
    "annulus from radius_m to 3x radius_m on the same two scenes. A pixel is "
    "disturbed when NDVI = (NIR-RED)/(NIR+RED) falls by at least 0.15 AND "
    "BSI = ((SWIR16+RED)-(NIR+BLUE))/((SWIR16+RED)+(NIR+BLUE)) rises by at least 0.05; "
    "or, on ground that was already unvegetated, when mean visible reflectance rises by "
    "at least 0.030 while NDVI stays under 0.25 and does not increase. The reported number "
    "is the footprint's disturbed fraction minus the ring's, so regional greening, drought "
    "and harvest cancel. Cloud, shadow and snow are masked per pixel from the scene's own "
    "SCL band; above 10% of the footprint masked, the answer is insufficient_imagery."
)

LIMITS = [
    "Sentinel-2 is 10 m per pixel. Clearing, grading, laydown yards, haul roads and large "
    "pads are visible. A turbine foundation, a transformer, a switchyard bay or any object "
    "under about 20 m is not. Nothing here is evidence about equipment.",
    "This corroborates a permit-pathway verdict. It does not prove one. A cleared pad is "
    "not a permitted plant, and an empty parcel is not proof a project is dead.",
    "The footprint is a circle around a published coordinate, not a parcel boundary. Where "
    "the coordinate is approximate, the circle is approximate with it.",
    "Cloud, snow, drought and crop cycles all move NDVI. The control ring removes what is "
    "regional; it does not remove a change that happens to be confined to this parcel for "
    "some other reason.",
    "A brownfield retrofit inside an existing building produces little surface change and "
    "will read low here even when the buildout is real.",
    "The thresholds are screening thresholds, not a calibrated classifier. They are in one "
    "block at the top of ingest/satellite.py and are meant to be moved and re-run.",
    "The `structures_present` gate uses an absolute visible-reflectance threshold (0.22) and "
    "that number does not travel. Desert ground is above it before anyone builds anything; the "
    "dark metal roofs at xAI Colossus 1 measure 0.11 and never reach it. Treat the top rung as "
    "'bright and paved', reachable mainly on arid sites, and read the disturbed fraction rather "
    "than the label where the two disagree.",
]


def _schedule_block(
    groundbreaking: Any, energization: Any, as_of: date, verdict: str
) -> dict:
    gb, gb_note = parse_announced(groundbreaking)
    en, en_note = parse_announced(energization)

    block: dict[str, Any] = {
        "as_of": as_of.isoformat(),
        "announced_groundbreaking": str(groundbreaking) if groundbreaking else None,
        "announced_groundbreaking_read_as": gb.isoformat() if gb else None,
        "groundbreaking_parse": gb_note,
        "announced_energization": str(energization) if energization else None,
        "announced_energization_read_as": en.isoformat() if en else None,
        "energization_parse": en_note,
    }

    if gb:
        block["months_since_announced_groundbreaking"] = round(_months_between(gb, as_of), 1)
    if en:
        block["months_to_announced_energization"] = round(_months_between(as_of, en), 1)

    lines: list[str] = []
    if gb and verdict == "no_visible_activity":
        months = _months_between(gb, as_of)
        lines.append(
            f"{months:.0f} months past the announced groundbreaking date and the footprint "
            f"shows no surface change above the control ring."
        )
    elif gb:
        months = _months_between(gb, as_of)
        lines.append(
            f"{months:.0f} months past the announced groundbreaking date, and the footprint "
            f"reads {verdict.replace('_', ' ')}."
        )

    if en:
        remaining = _months_between(as_of, en)
        if remaining < 0:
            lines.append(
                f"The announced energization date passed {abs(remaining):.0f} months ago."
            )
            block["announced_date_already_passed"] = True
        else:
            lines.append(f"{remaining:.1f} months remain to the announced energization date.")
            if verdict == "no_visible_activity" and remaining < 24:
                lines.append(
                    f"An unbroken parcel {remaining:.1f} months out requires a full buildout "
                    f"in less time than any case in this repo's backtest except xAI Colossus 1, "
                    f"which was {FASTEST_OBSERVED_MONTHS:.0f} months and was a retrofit of an "
                    f"existing factory building using trailer-mounted turbines. This is a "
                    f"schedule sanity check, not a construction-duration model."
                )
                block["schedule_below_fastest_observed"] = remaining < FASTEST_OBSERVED_MONTHS
    block["implication"] = " ".join(lines) if lines else "No announced dates supplied."
    return block


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "site"


def verify_construction(
    lat: float,
    lon: float,
    announced_groundbreaking: Any = None,
    announced_energization: Any = None,
    radius_m: float = 500.0,
    as_of: date | str | None = None,
    label: str | None = None,
    write_chips: bool = True,
    output_dir: Path | str | None = None,
    cache: ResponseCache | None = None,
    mireye_facts: dict | None = None,
    ring_factor: float = 3.0,
    timeout: float = 120.0,
) -> ConstructionVerdict:
    """Is there a hole in the ground yet?

    Returns a `ConstructionVerdict`. It never raises: no network, no scenes,
    an unreadable COG and a snowed-in parcel all come back as
    `insufficient_imagery` with the reason attached, because a screening tool
    that crashes the agent loop is worse than one that says it does not know.

    `announced_groundbreaking` and `announced_energization` take dates in the
    form press releases publish them: `2025-09`, `Q4 2026`, `2024-06-15`.
    """
    as_of_date = (
        date.today() if as_of is None
        else as_of if isinstance(as_of, date)
        else _parse_iso(str(as_of))
    )
    radius_m = float(max(60.0, min(5000.0, radius_m)))
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    verdict = ConstructionVerdict(
        verdict="insufficient_imagery", lat=lat, lon=lon, radius_m=radius_m, label=label
    )
    verdict.mireye = _mireye_block(mireye_facts)

    gb, _ = parse_announced(announced_groundbreaking)
    baseline_target = gb or (as_of_date - timedelta(days=730))

    owns_cache = cache is None
    try:
        cache = cache if cache is not None else ResponseCache()
    except Exception as exc:  # a broken cache must not stop a read
        verdict.scene_log.append(f"response cache unavailable ({exc}); running uncached")
        cache = None
        owns_cache = False

    client = httpx.Client(
        timeout=httpx.Timeout(timeout, connect=15.0),
        follow_redirects=True,
        headers={"user-agent": "deliverable/0.1 (Mireye Build Challenge)"},
    )
    reader = CogReader(client, cache)

    try:
        base_scene, base_grid, log = _pick_scene(
            reader, client, lat, lon, radius_m, ring_factor,
            baseline_target - timedelta(days=BASELINE_WINDOW_DAYS),
            min(baseline_target + timedelta(days=BASELINE_WINDOW_DAYS), as_of_date),
            order="nearest", target=baseline_target, cache=cache,
            probe_limit=MAX_SCL_PROBES,
        )
        verdict.scene_log.extend(log)

        if base_scene is None or base_grid is None:
            if any(line.startswith(_SEARCH_FAILED) for line in log):
                verdict.reasons.append(
                    "The Sentinel-2 catalog could not be reached, so no imagery was read and "
                    "no construction claim is made either way. This needs no credential; if it "
                    "is failing, it is the network. See scene_selection_log."
                )
            else:
                verdict.reasons.append(
                    f"No Sentinel-2 scene with the footprint under {MAX_AOI_CLOUD * 100:.0f}% "
                    f"cloud within {BASELINE_WINDOW_DAYS} days of the announced groundbreaking "
                    f"date ({baseline_target}). Sentinel-2 revisits every ~5 days, so a gap this "
                    f"long means persistent cloud, and a cloudy scene is not evidence."
                )
            return verdict

        offset_days = abs((base_scene_date(base_scene) - baseline_target).days)
        if offset_days > 60:
            verdict.scene_log.append(
                f"the accepted baseline is {offset_days} days from the announced groundbreaking "
                f"date; everything before that date is attributed to the baseline, so a real "
                f"change that happened inside that gap is missed"
            )

        recent_scene, recent_grid, log = _pick_scene(
            reader, client, lat, lon, radius_m, ring_factor,
            max(
                as_of_date - timedelta(days=RECENT_WINDOW_DAYS),
                base_scene_date(base_scene) + timedelta(days=30),
            ),
            as_of_date,
            order="recent", target=None, cache=cache,
            require_epsg=base_scene.epsg,
            probe_limit=MAX_SCL_PROBES,
        )
        verdict.scene_log.extend(log)

        if recent_scene is None or recent_grid is None:
            verdict.reasons.append(
                "Found a baseline scene but no recent cloud-free scene over the footprint. "
                "Nothing can be said about change from one date."
            )
            verdict.baseline = base_scene
            return verdict

        aoi, disturbed = _zone_change(base_grid, recent_grid, "aoi")
        ring, _ = _zone_change(base_grid, recent_grid, "ring")

        if aoi.pixels < 50:
            verdict.reasons.append(
                f"Only {aoi.pixels} pixels are usable in both scenes over the footprint. "
                f"Too few to average."
            )
            verdict.baseline, verdict.recent = base_scene, recent_scene
            return verdict

        name, excess, reasons = _classify(aoi, ring)
        verdict.verdict = name
        verdict.baseline = base_scene
        verdict.recent = recent_scene
        verdict.aoi = aoi
        verdict.ring = ring
        verdict.excess_disturbed = excess
        verdict.reasons = reasons
        verdict.reasons.append(
            f"Scenes: {base_scene.cited()}; {recent_scene.cited()}. "
            f"Sentinel-2 is {RESOLUTION_M} m per pixel — this sees clearing and earthworks, "
            f"not equipment."
        )
        verdict.schedule = _schedule_block(
            announced_groundbreaking, announced_energization, as_of_date, name
        )

        if write_chips:
            stem = _slug(label or f"{lat:.4f}_{lon:.4f}")
            radius_px = radius_m / RESOLUTION_M
            # Target roughly 600-1000 px on the long edge: big enough for a
            # video frame, small enough to commit. Nearest-neighbour upscaling
            # adds no information and is not pretending to.
            scale = 1 if base_grid.width >= 600 else (2 if base_grid.width >= 250 else 4)
            try:
                verdict.chips = [
                    str(_render_chip(
                        base_grid,
                        out_dir / f"{stem}_{base_scene.acquired_date}_baseline.png",
                        scale, radius_px,
                    ).relative_to(_ROOT)),
                    str(_render_chip(
                        recent_grid,
                        out_dir / f"{stem}_{recent_scene.acquired_date}_recent.png",
                        scale, radius_px,
                    ).relative_to(_ROOT)),
                    str(_render_chip(
                        recent_grid,
                        out_dir / f"{stem}_{recent_scene.acquired_date}_change.png",
                        scale, radius_px, overlay=disturbed,
                    ).relative_to(_ROOT)),
                ]
            except OSError as exc:
                verdict.scene_log.append(f"could not write chips: {exc}")

        return verdict

    except (httpx.HTTPError, SatelliteError, zlib.error, ValueError, KeyError) as exc:
        verdict.verdict = "insufficient_imagery"
        verdict.reasons.append(
            f"{exc.__class__.__name__}: {exc}. No imagery was read, so no construction "
            f"claim is made either way."
        )
        return verdict
    finally:
        client.close()
        if owns_cache and cache is not None:
            cache.close()


def base_scene_date(scene: Scene) -> date:
    return _parse_iso(scene.acquired_date)


def _mireye_block(facts: dict | None) -> dict:
    """What Mireye already said about this ground, recorded next to the imagery.

    Mireye's Sentinel-2 NDVI is the right first call and it is cheap. It is
    also a single-cell point sample with no scene date, which is why this
    module exists — so both numbers go in the output side by side and the
    difference is visible rather than argued.
    """
    block: dict[str, Any] = {
        "policy": (
            "Mireye answers first. ndvi_current, ndvi_change_5y, lcms_class, land_use_class "
            "and tree_canopy_pct are read from Mireye and reported here as corroboration."
        ),
        "gap": (
            "Mireye's NDVI is one ~10 m cell with no acquisition date, no cloud fraction and "
            "no selectable dates; ndvi_change_5y is a fixed 5-year window. Filed as "
            "/v1/field-requests fr_39331af65eef4400986c0d4c8552dc5e (queued, 3 accepted_new "
            "sub-asks, 0 credits)."
        ),
        "fields": {},
    }
    if not facts:
        block["note"] = "No Mireye land-cover facts were in the run's fact set."
        return block
    for key in (
        "ndvi_current", "ndvi_change_5y", "lcms_class", "land_use_class",
        "tree_canopy_pct", "primary_building_footprint_sqm", "cdl_class",
    ):
        if key in facts:
            block["fields"][key] = facts[key]
    if not block["fields"]:
        block["note"] = "No Mireye land-cover facts were in the run's fact set."
    return block


# --------------------------------------------------------------------------
# CLI — runs the three backtest cases
# --------------------------------------------------------------------------

#: The three real projects, with the dates as they were announced. Dates come
#: from backtest/cases.py. Coordinates are published locations, not surveyed
#: parcels.
#:
#: Two of the three published coordinates are wrong, and both are run anyway,
#: against the corrected one, because the pairs are the clearest statement this
#: repo can make about what an approximate coordinate costs.
#:
#: Memphis. `backtest/cases.py` has 35.065, -90.075, labelled "South Memphis,
#: approximate". That point is 7.3 km east of the site, in a residential
#: neighbourhood. Colossus 1 is the former Electrolux plant, 3231 Paul R Lowry
#: Rd, Memphis TN 38109, geocoded through Mireye at 0.95 confidence, rooftop
#: grade, to 35.060553, -90.155133.
#:
#: Santa Teresa. `backtest/cases.py` has 31.870, -106.690, labelled "Santa
#: Teresa, approximate". No coordinate for Project Jupiter is public — Baxtel
#: withholds the street address — so this one was found rather than looked up:
#: the change metric was run over a 15 km window on the NM-136 corridor and the
#: 300 m blocks were ranked by disturbed-pixel count. The top cluster is at
#: 31.8175, -106.6675, which is 6.2 km south-southeast of the published point,
#: 1.6 km off the Pete V. Domenici International Highway, 1.1 km from a
#: substation, and 3.3 km from an EIA-860M generator Mireye reports as
#: "V) UNDER CONSTRUCTION, MORE THAN 50 PERCENT COMPLETE". That is consistent
#: with the reported Project Jupiter site and is not a confirmed parcel ID.
BACKTEST_SITES = [
    {
        "key": "jupiter-construction",
        "label": "Project Jupiter — the construction found on the NM-136 corridor",
        "lat": 31.8175, "lon": -106.6675,
        "groundbreaking": "2025-09",
        "energization": "Q4 2026",
        "radius_m": 900.0,
        "expect": "reported: construction began Sept 2025, 1,200+ workers by spring 2026",
    },
    {
        "key": "jupiter-published-coord",
        "label": "Project Jupiter — the approximate coordinate in backtest/cases.py",
        "lat": 31.870, "lon": -106.690,
        "groundbreaking": "2025-09",
        "energization": "Q4 2026",
        "radius_m": 1200.0,
        "expect": "6.2 km NNW of the construction; should read empty",
    },
    {
        "key": "vineland",
        "label": "Nebius / DataOne — Vineland, NJ",
        "lat": 39.447, "lon": -75.010,
        "groundbreaking": "2024-06",
        "energization": "2026-12",
        "radius_m": 500.0,
        "expect": "air permit never issued, switched to fuel cells May 2026",
    },
    {
        "key": "memphis-colossus1",
        "label": "xAI Colossus 1 — Memphis, TN (geocoded street address)",
        "lat": 35.060553, "lon": -90.155133,
        "groundbreaking": "2024-06",
        "energization": "2024-09",
        "radius_m": 800.0,
        "expect": "POSITIVE CONTROL — this one was built, 122 days",
    },
    {
        "key": "memphis-published-coord",
        "label": "xAI Colossus 1 — the approximate coordinate in backtest/cases.py",
        "lat": 35.065, "lon": -90.075,
        "groundbreaking": "2024-06",
        "energization": "2024-09",
        "radius_m": 800.0,
        "expect": "CONTROL ON THE CONTROL — 7.3 km off the site; should read empty",
    },
]


def run_backtest(
    as_of: str | None = None,
    radius_m: float | None = None,
    verbose: bool = True,
) -> list[ConstructionVerdict]:
    cache = ResponseCache()
    out: list[ConstructionVerdict] = []

    def say(text: str = "") -> None:
        if verbose:
            print(text)

    try:
        for site in BACKTEST_SITES:
            say(f"\n=== {site['label']}")
            say(f"    {site['lat']}, {site['lon']}  ({site['expect']})")
            v = verify_construction(
                site["lat"], site["lon"],
                announced_groundbreaking=site["groundbreaking"],
                announced_energization=site["energization"],
                radius_m=radius_m or site["radius_m"],
                as_of=as_of,
                label=site["key"],
                cache=cache,
            )
            out.append(v)
            say(f"    -> {v.headline()}")
            for line in v.reasons:
                say(f"       {line}")
            if v.schedule.get("implication"):
                say(f"       {v.schedule['implication']}")
            for chip in v.chips:
                say(f"       chip {chip}")
    finally:
        cache.close()
    return out


def main() -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        description="Satellite construction verification over Sentinel-2. No credential needed."
    )
    parser.add_argument("coord", nargs="?", help="'lat,lon'. Omit to run the three backtest cases.")
    parser.add_argument("--groundbreaking", help="Announced groundbreaking: 2025-09, Q4 2026, ...")
    parser.add_argument("--energization", help="Announced energization date.")
    parser.add_argument("--radius", type=float, default=500.0, help="Footprint radius in metres.")
    parser.add_argument("--as-of", help="Treat this date as today (ISO).")
    parser.add_argument("--label", help="Name used for the chip filenames.")
    parser.add_argument("--json", action="store_true", help="Print the full verdict as JSON.")
    args = parser.parse_args()

    if not args.coord:
        results = run_backtest(as_of=args.as_of, verbose=not args.json)
        if args.json:
            print(json.dumps([r.to_dict() for r in results], indent=1))
        return

    lat_s, lon_s = args.coord.split(",")
    v = verify_construction(
        float(lat_s), float(lon_s),
        announced_groundbreaking=args.groundbreaking,
        announced_energization=args.energization,
        radius_m=args.radius,
        as_of=args.as_of,
        label=args.label,
    )
    if args.json:
        print(json.dumps(v.to_dict(), indent=1))
        return
    print(v.headline())
    for line in v.reasons:
        print(f"  {line}")
    if v.schedule.get("implication"):
        print(f"  {v.schedule['implication']}")
    for chip in v.chips:
        print(f"  chip {chip}")


if __name__ == "__main__":  # pragma: no cover
    main()
