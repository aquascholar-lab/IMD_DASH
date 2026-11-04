# Rectangle region selection verification — 2026-11-04

- Full suite: 58 passed (13.93 s), no warnings.
- Compilation and git diff --check: passed.
- Independent review: no important correctness defects; added analysis reuse for
  unchanged applied areas after the reviewer noted redundant calculations.
- Chromium real mouse gestures: draw and Apply, replacement drawing (one layer),
  restored rectangle edit handles, persistence across product changes, and Clear
  removing results all passed. No JavaScript page errors.
- Browser testing caught Apply being enabled before a replacement draft arrived.
  Apply now stays disabled until a new draft differs from the applied rectangle;
  regression assertions and the full browser gesture test passed after the fix.
- Coordinate tests: valid/reversed rectangles, closed-ring/four-corner constraints,
  invalid/rotated/degenerate shapes, coordinate limits and antimeridian rejection.
- AppTest: draft edits do not change applied bounds; Apply changes grid selection;
  Clear removes selection/results; draft reruns reuse the existing analysis.

Map controls load from jsDelivr with OpenStreetMap as the basemap. This environment
blocks OSM tile requests; drawing and editing still passed without tiles. Browser
CDN assets were fetched via TLS-verified requests through the configured session
proxy because Chromium does not trust that proxy's CA by default. No TLS checks
were disabled. Normal deployment requires browser access to the CDN and tile host.
