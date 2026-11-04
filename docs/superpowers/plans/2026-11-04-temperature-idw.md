# Built-in temperature retrieval and IDW

User requests built-in temperature downloads and IDW maps; prior authorization to
proceed with judgment and push GitHub updates persists.

- [x] Add tested runtime discovery of IMD annual binary downloads from the official
  Tmax/Tmin landing pages. Parse links or the published year-select form, preserve
  hidden inputs/cookies, restrict targets to HTTPS IMD, validate binary length and
  dates before atomic cache publication. Never guess PHP field names. Expose both
  products in Download from IMD, with batch identity including product/year/byte order.
- [x] Implement bounded-neighbor IDW using geodesic distances, exact sample matches,
  finite-only samples, polygon holes/boundaries, explicit power/resolution controls,
  and optional original grid points. Default power 2, 120x120 target grid, 12 nearest
  valid samples. Keep statistics/exports based on original observations.
- [x] Run downloader fixtures (form/link/HTML errors/cache), numeric interpolation
  tests, Streamlit tests for all products and state invalidation, browser smoke,
  review, and full suite before committing and pushing.

Live IMD page access is blocked here. Download discovery is performed on the host
running the app and tested offline against realistic HTML forms and binary fixtures.
Report live access limits rather than claiming verified remote availability.
