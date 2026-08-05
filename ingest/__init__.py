"""The two external sources, plus one hand-entered file.

Mireye answers everything physical. These three answer the things it does not
index, and they are deliberately the only external ingest in the repo:

  greenbook   EPA nonattainment designations by county FIPS. Two dBASE files,
              no key, no API. The single fact that flips the permit pathway.
  dockets     CourtListener / RECAP federal dockets. One free endpoint.
              Has this developer been sued; has this county been sued.
  counties    27 county moratorium and posture records, typed by hand from
              linked sources rather than scraped.

Schema, verification and staleness for all three: docs/ingest-notes.md.
"""

from __future__ import annotations

__all__ = ["counties", "dockets", "greenbook"]
