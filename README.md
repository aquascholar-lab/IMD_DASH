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
Temperature data must be uploaded; no unverified live temperature API is assumed.

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
The app links this page when Maximum temperature is selected. Download the annual
file there, choose **Upload files**, and set **Binary file year** and byte order
in **NetCDF / binary settings**. This Tmax link must not be used as a Tmin source.
The page is an HTML landing page, not a NetCDF dataset URL. Its live download form
could not be inspected here because access to imdpune.gov.in returns a network
policy 403; no temperature request endpoint or form parameters are guessed.

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
  Maps show actual aggregated grid-center values, without IDW or implied higher
  resolution. Upload a larger region when a small polygon contains no grid centers.
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
python -m compileall -q imd_data.py imd_charts.py streamlit_imd_dashboard.py
```

Tests cover real xarray/NetCDF round trips, future/leap dates, alternate schemas,
Kelvin conversion, missing values, clipping and polygon holes, annual grouping,
binary length/layout, grid mismatch, overlapping dates, trend year spacing,
download validation/caching, and Streamlit reruns/exports for all three products.
