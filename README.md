# IMD Climate Atlas

A Streamlit dashboard for daily gridded IMD rainfall, maximum temperature (Tmax)
and minimum temperature (Tmin). The entry point remains
`streamlit_imd_dashboard.py`.

## Run

Python 3.10+ is recommended (verified here with Python 3.12).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_imd_dashboard.py
```

Open the URL printed by Streamlit (normally http://localhost:8501).
The default view is **synthetic demonstration data**, labeled as such. Switch to
**Upload files** to analyze observations. Nothing in the demo is an IMD observation.

## Workflow

1. Select Rainfall, Maximum temperature or Minimum temperature.
2. Select a bounding box or upload a polygon (GeoJSON, KML, or a zipped shapefile
   including its .shp, .shx, .dbf, and .prj). The default is Kerala's bounding box,
   **not** the Kerala administrative boundary. Upload a boundary for exact clipping.
3. Upload one or more daily NetCDF files. Dates determine the available years;
   filenames and year-based schema guesses are not used. Set a variable name or
   units override in the sidebar only when automatic detection is insufficient.
4. Choose any available year range. A single-year dataset is selected automatically.
5. Explore Overview, Seasons & months, Spatial explorer, Trends, and Data & exports.
   Results remain visible while changing chart controls or preparing downloads.

The rainfall downloader requests the selected years from the existing IMD RF25
endpoint and checks that the response is a readable, correctly dated rainfall
NetCDF before caching it. Its year range advances with the current year.
**A selectable year does not mean IMD has published it.** Failures are shown per
year and partial download batches are clearly identified. The live IMD endpoint
was not reachable for verification in this environment's network policy; the
validation/cache paths were tested with local NetCDF and HTML error fixtures.
The **Download from IMD** option also retrieves Tmax and Tmin annual binary files.
The downloader opens the selected product's official landing page at runtime and
uses a dated binary link, URL-valued year dropdown, or the published year-select
form. It preserves form fields/cookies, handles GET/POST and a follow-up download
page, validates the exact annual binary length, and caches a complete file
atomically. PHP endpoint names and request fields are discovered rather than
hardcoded. Download batches are isolated by product, years and byte order.

The host running the app needs HTTPS access to `www.imdpune.gov.in`. Live
availability could not be verified in this development environment because its
network policy blocks that site. Forms, direct links, follow-up pages, unavailable
years, invalid responses and caching were verified with offline fixtures. If IMD
changes to a JavaScript-only flow or captcha, the app reports the unsupported page
instead of saving an HTML error as data. Binary byte order defaults to little
endian and can be changed in the download controls based on source documentation.

## Supported data

### NetCDF (recommended for multi-year analysis)

- `.nc`, `.nc4`, `.netcdf`; Gregorian daily dates decoded by xarray/CF conventions.
- Rectilinear 1D time, latitude, longitude coordinates, with common IMD names
  (`TIME`, `LATITUDE`, `LONGITUDE`, `time`, `lat`, `lon`) or CF standard names/axes.
  Descending coordinates are sorted before clipping.
- Rainfall names: `RAINFALL`, `rf`, `rain`, `precip`, `precipitation`.
- Tmax names: `tmax`, `MAX_TEMP`, `maxtemp`, `tasmax`, `maximum_temperature`.
- Tmin names: `tmin`, `MIN_TEMP`, `mintemp`, `tasmin`, `minimum_temperature`.
- Other names work when there is one unambiguous 3D variable or the user selects
  it explicitly. The selected product must match the scientific meaning.
- Rainfall in mm or mm/day; temperature in Celsius or Kelvin (converted to °C).
  Unsupported/missing units require an explicit override based on source documentation.
- Extra singleton dimensions are removed. Multiple levels, subdaily dates, 2D
  curvilinear coordinates and non-Gregorian calendars require preprocessing.
- Files must have the same spatial grid and product. Duplicate or overlapping dates
  are rejected rather than silently doubled. Missing dates remain missing.

### IMD annual binary grids

Official source supplied for maximum temperature (Tmax):
[IMD 1° maximum-temperature binary data](https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html).
Select **Maximum temperature → Download from IMD**, choose the first and last
years, and click **Download selected years**. The app retrieves and analyzes each
annual binary without a manual upload. Minimum temperature uses the corresponding
[IMD Tmin landing page](https://www.imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html);
that sibling page's live availability is also unverified in this environment.
The app discovers the download controls on the running host.

Manual uploads remain available: choose **Upload files** and set **Binary file
year** and byte order in **NetCDF / binary settings**. The Tmax source is never
used for Tmin.

Upload **one annual `.grd`/`.bin` file at a time** and explicitly set its year and
byte order. Binary files contain no time metadata, so their dates cannot be inferred
reliably from bytes. The supported layout is raw float32, ordered day → latitude →
longitude (longitude changes fastest), with no header or Fortran record markers:

| Product | Grid | Latitude | Longitude |
| --- | --- | --- | --- |
| Rainfall | 135 × 129, 0.25° | 6.5–40.0° N | 66.5–98.5° E |
| Tmax / Tmin | 31 × 31, 1° | 7.5–37.5° N | 67.5–97.5° E |

The reader verifies the exact 365/366-day byte count. Different IMD binary
resolutions/layouts must first be converted to dated NetCDF. Little endian is the
default; select big endian only when the source documentation requires it.
Binary year bounds reflect the supported timestamp representation, 1678–2260;
NetCDF analysis has no historical publication-year cutoff.

## Calculations and interpretation

- Rainfall uses **observed sums** by month, season and annual period; temperature
  uses **observed means**, never sums. No missing value is filled with zero.
- CF fill values, non-finite values, and common IMD sentinels are masked. Negative
  rainfall is masked; negative temperatures remain valid. Temperature outside
  −100 to 70 °C is masked. Consult input source documentation for unusual codes.
- Spatial means use cosine-latitude weights. Daily charts average that day's valid
  cells. Monthly/seasonal/annual values aggregate each cell through time first,
  then take its weighted regional mean; these can differ from a temporal aggregate
  of the daily chart when observations are missing.
- Coverage = valid grid-days / expected grid-days. An annual period is complete
  only when every selected cell has every expected date. Partial totals/means are
  displayed with coverage; no extrapolation is made.
- Calendar years run January–December. Hydrological years run June–May and are
  labeled by the **June start year**: `2023` means June 2023–May 2024. The year
  selector filters input **calendar years**; June–May periods at the edges will
  be partial unless all their dates are included.
- IMD seasons use calendar years: Winter Jan–Feb, Pre-monsoon Mar–May, Monsoon
  Jun–Sep, Post-monsoon Oct–Dec. Seasonal hover shows observation coverage.
- Grid centers inside/on polygon boundaries are included; holes are excluded.
  Upload a larger region when a small polygon contains no grid centers.
- The spatial explorer defaults to **IDW surface**, with adjustable power (default
  2) and surface resolution (default 120 × 120). IDW uses up to 12 nearest valid
  grid centers and great-circle distances, preserves exact sample values, and
  clips to the study region including holes. Missing samples are excluded.
  Optional original-point overlays and a Grid centers mode aid comparison.
  The color scale stays fixed across selected years. IDW can extrapolate within
  the region beyond sample coverage; a smoother map is not new observation data.
  Regional statistics and exports always use the original grid, not the surface.
- Annual trends use complete periods only, require at least 3 periods, and show
  the Mann–Kendall p-value and Theil–Sen slope per **actual elapsed year**. The
  test does not correct for autocorrelation. Short records are weak evidence.

## Outputs

- Regional daily, monthly, seasonal and annual CSV tables (with coverage).
- Selected gridded daily NetCDF, preserving missing values and the polygon mask.
- Annual grid points as GeoJSON, preserving full year field names. This replaces
  daily shapefile exports that exceed DBF field limits or truncate date names.
- Plotly charts support hover, zoom and PNG download from their toolbar.

NetCDF is spatially subset before loading, and repeated uploads are cached by
content, product, reader settings and bounds. The selected region still loads into
memory: very large areas and century-long daily ranges should be analyzed in
smaller batches. Uploaded files default to a 512 MB per-file limit in Streamlit.

## Verification

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q imd_data.py imd_sources.py imd_charts.py streamlit_imd_dashboard.py
```

Tests cover real xarray/NetCDF round trips, future/leap dates, alternate schemas,
Kelvin conversion, missing values, clipping and polygon holes, annual grouping,
binary length/layout, grid mismatch, overlapping dates, trend year spacing,
download form discovery/validation/caching, IDW exact values and polygon masking,
and Streamlit reruns/exports/built-in temperature batches for all three products.
