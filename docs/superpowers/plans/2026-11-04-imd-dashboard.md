# IMD dashboard implementation plan

User authorized implementation using our judgment. Keep Streamlit and its launch command.

Goal: analyze gridded rainfall and Tmax/Tmin for any dates present in input files,
without calendar-year-based schema assumptions. Temperature uses means, rainfall
uses sums; missing observations remain missing and coverage is displayed.

Architecture: imd_data.py owns normalization, loading, selection and aggregations;
imd_charts.py owns Plotly figures; streamlit_imd_dashboard.py owns interaction.
NetCDF is the primary input; annual IMD binary grids use explicit year, byte order,
and documented fixed product grids. No invented timestamps for undated NetCDF.

- [x] 1. Write and run failing tests for mixed coordinate/variable names, leap dates,
  descending axes, missing values, Kelvin conversion, calendar/hydrological years,
  polygon holes, duplicate dates and inconsistent grids. Implement imd_data.py.
- [x] 2. Add local multi-file upload and validated atomic rainfall downloads.
  Temperature uploads supported; live temperature endpoints are not assumed.
  Verify binary lengths, ambiguous variables, invalid time, units and downloads.
- [x] 3. Rebuild Streamlit with a deliberate navy/teal theme, sidebar controls,
  demo data explicitly labeled synthetic, metrics and persistent overview, seasonal,
  spatial, trends and exports tabs. Year controls derive from loaded dates.
  Plotly figures show actual grid values, preserve gaps, and support hover/zoom.
- [x] 4. Verify using pytest, Streamlit AppTest across all products and year filters,
  compilation, and a local server health check. Document launch, input formats,
  coverage policy and limits. Review final code and diff.

Review focus: no hardcoded upper year; all-missing rainfall never becomes zero;
partial years explicitly identified; overlapping files rejected rather than doubled;
state reflects current file/product/region choices. Regional means use cosine latitude
weights. Trends use complete calendar/hydrological years and actual year coordinates.

Live IMD requests cannot be verified here because the environment's allowed hosts
exclude imdpune.gov.in; upload and synthetic fixtures provide offline verification.
