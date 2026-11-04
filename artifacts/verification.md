# Verification — 2026-11-04

- Python 3.12, Streamlit 1.66.1: pytest 31 passed (7.41 s).
- compileall: passed. git diff --check: passed.
- Local Streamlit server /_stcore/health: ok.
- Chromium: no JavaScript page errors.
- Phone viewport: 390 px, document width 390 px (no horizontal overflow).
- Browser upload: 2032 Tmax NetCDF with MAX_TEMP/TIME/LATITUDE/LONGITUDE,
  including February 29. Input 300 K displayed as 26.85 °C.
- Browser CSV and selected-grid NetCDF downloads completed without errors.
- AppTest: all three products, calendar/hydrological grouping, year selection,
  clearing results on empty uploads, NetCDF and GeoJSON export preparation.
- Independent code review: fixed float32 -99.9 masking (binary and NetCDF
  regression tests). Also preserved gaps for absent seasons in seasonal charts.
- Screenshots captured from the running application at desktop and phone sizes.
- Local fixtures and synthetic data used; no user observation files were supplied.
  Live IMD endpoint verification is blocked by the environment network policy.

## Decisions

Kept Streamlit; data-driven dated NetCDF is the multi-year input. Raw annual binary
requires explicit year and byte order. Upload-only temperature ingestion avoids
assuming an unverified IMD temperature endpoint. GeoJSON replaces daily shapefile
exports to preserve field names and avoid DBF limits. Actual grid centers replace
IDW maps to avoid implying resolution absent from input observations.
