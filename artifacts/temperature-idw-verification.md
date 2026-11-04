# Temperature retrieval and IDW verification — 2026-11-04

- Full pytest suite: 48 passed (10.74 s).
- compileall for imd_data, imd_sources, imd_charts and Streamlit entrypoint: passed.
- git diff --check: passed.
- Browser Chromium smoke: IDW heatmaps rendered for rainfall and Tmax; original
  grid-point overlay worked; built-in temperature download controls were visible;
  no JavaScript page errors.
- Downloader tests: Tmax/Tmin, year selection, hidden fields, selected secondary
  controls, checked inputs, POST/GET, direct links, standalone URL selects,
  follow-up download pages, cache reuse, HTML/unavailable-year rejection and
  destination restrictions.
- AppTest: downloaded multi-year temperature fixtures analyzed for both products;
  switching products invalidated the old batch.
- IDW tests: exact sample values, symmetric midpoint, constant/one-sample surface,
  missing samples, all-missing inputs, polygon boundaries/holes and exterior mask.
- Independent reviewer found changed form defaults; fixed with a failing fixture
  followed by a passing suite. Follow-up Referer now uses the preceding page URL.

## Limits

Live IMD retrieval could not be verified because this environment blocks HTTPS
access to imdpune.gov.in. The downloader discovers forms/links at runtime on the
host running the app. Tmin uses the corresponding Min_1_Bin.html source; its live
page was not inspected here. Unsupported JavaScript-only flows fail clearly.

## Choices

IDW uses great-circle distances and up to 12 nearest finite samples. Default
power 2 and 120x120 resolution are adjustable. Surfaces are region-masked, including
holes, and may extrapolate beyond observed centers inside the region. Original
observations alone determine all summary statistics and downloadable data.
