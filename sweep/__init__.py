"""National county sweep and the map it produces.

Two modules, run in this order:

    python -m sweep.counties     # scores every county -> data/county_scores.json
    python -m sweep.map          # renders it -> outputs/county_map.html

`counties` runs the same pathway engine used for a single parcel across all
3,222 US counties and county equivalents, against one fixed reference plant, so
the only thing varying across the map is the ground. `map` turns that into one
self-contained HTML file with no CDN and no runtime fetch.

Both run with no API keys. Only the federal county file and the pathway engine
are required; nonattainment and county posture degrade to a visible "no data"
rather than to a clean score.

This is a **screening layer at county resolution**. It cannot see parcel-level
increment consumption, terrain, or pipeline distance. Method, limits and the
top and bottom county lists are in `docs/sweep-notes.md`.
"""
