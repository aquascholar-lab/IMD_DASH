# How to use this app

Use IMD Climate Atlas to explore gridded rainfall, maximum temperature (Tmax), and
minimum temperature (Tmin) for a study area. Select **Dashboard** to return to the
analysis. Opening this guide keeps your dashboard settings and applied rectangle.

## Quick start

1. Select a **Climate variable** in the sidebar.
2. Choose your **Data source**: try **Demo · synthetic**, retrieve observations
   with **Download from IMD**, or use **Upload files**.
3. Select the **Study region** using coordinates, a drawn rectangle, or a polygon.
4. Load your data, then choose the **Years** and **Annual grouping**.
5. Explore the result tabs and download your tables or grids from **Data & exports**.

The default demo uses generated values for 2020–2024. It helps you learn the
controls; it is **not IMD observation data**. Switch the data source before using
results in research or reporting.

## 1. Choose a climate variable

| Variable | Display units | Monthly, seasonal and annual calculation |
| --- | --- | --- |
| Rainfall | mm | Sum of valid daily amounts |
| Maximum temperature | °C | Mean of valid daily Tmax values |
| Minimum temperature | °C | Mean of valid daily Tmin values |

Temperature in Kelvin is converted to Celsius when the source units identify it
as Kelvin. Choose the product that matches your data; Tmax and Tmin are separate
datasets.

## 2. Set the study region

### Enter a bounding box

Choose **Region method → Bounding box**. Enter west/east longitudes and south/north
latitudes in decimal degrees. West must be less than east; south must be less than
north. The default is a rectangle around Kerala, not its administrative boundary.

### Draw a rectangle on the map

1. Choose **Region method → Draw rectangle**.
2. Pan and zoom to your area, then select the rectangle tool on the map's left edge.
3. Drag across the area. Check the **Pending rectangle** coordinates.
4. Click **Apply rectangle** to use this area in calculations, maps and exports.
5. To change it, draw a replacement rectangle, or use the edit tool to move/resize
   the saved rectangle. For an edit, click **Save** in the map toolbar first, then
   **Apply rectangle**.

Only the latest rectangle is retained. Apply is enabled when a new draft is ready;
panning or an unapplied edit does not change your study area. **Clear selection**
removes the applied region and results until another rectangle is applied.
Deleting a draft with the map's delete tool does not clear an already applied area.

The map controls and basemap require browser internet access. If basemap tiles do
not load but the drawing controls are visible, coordinates can still be drawn.
Manual bounding-box entry is also available.

### Upload a polygon boundary

Choose **Region method → Upload polygon** and upload GeoJSON, KML, or a ZIP
containing one shapefile and its `.shx`, `.dbf`, and `.prj` companions. The file must
contain valid polygons and declare a coordinate reference system. The app converts
it to longitude/latitude for analysis.

Grid centers inside or on the boundary are included; polygon holes are excluded.
Every study area must contain at least one dataset grid center. Temperature grids
are coarser than the 0.25° rainfall grid, so a small polygon may contain none.

## 3. Retrieve or upload data

### Download observations inside the app

Choose **Data source → Download from IMD**, select the first and last download
years, then click **Download selected years**. The selected climate variable
determines whether the app retrieves rainfall, Tmax, or Tmin.

The app uses NetCDF for rainfall and annual binary grids for temperature. For
binary downloads, use the byte order specified by the data source; little endian
is the default. Successfully validated files are cached for reuse.

A year appearing in the controls does not guarantee IMD has published it. Failed
years appear under **Download details**; if some files succeed, results contain
only those years. Check coverage before interpreting the results. The server
running the app must be able to reach IMD's website.

### Upload NetCDF files

Choose **Upload files** and select one or more `.nc`, `.nc4`, or `.netcdf` files.
The app reads dates from the files, including leap days, and detects common IMD
variable and coordinate names. Files must describe the same rectilinear grid and
product, with non-overlapping daily dates.

Use **NetCDF / binary settings** to enter an explicit variable name if automatic
detection is ambiguous. Override source units only when the dataset documentation
supports that choice. Unsupported calendars, multiple vertical levels, subdaily
data and curvilinear grids require preprocessing.

### Upload an annual binary grid

Upload one complete `.grd` or `.bin` annual file at a time. Set **Binary file year**
and **Binary byte order** in **NetCDF / binary settings**; raw files do not contain
usable date metadata. The reader checks the exact 365/366-day float32 byte count.

Supported layouts are 135 × 129 for 0.25° rainfall and 31 × 31 for 1° Tmax/Tmin,
ordered by day, latitude, then longitude. Different binary layouts must first be
converted to dated NetCDF. Use multi-year NetCDF files or built-in downloads for
multi-year analysis.

## 4. Select years and annual grouping

**Years** shows years present in the loaded data. A single-year file is selected
automatically. Choose the range to analyze; the range filters input calendar years.

- **Calendar year:** January–December.
- **June–May hydrological year:** June through the following May, labeled by the
  June start year. For example, 2023 means June 2023–May 2024.

Hydrological periods at the edges of your selected calendar years may be partial.
Select enough input years to include the full June–May period. Months and IMD
seasons always use calendar years, regardless of annual grouping.

## 5. Read the results

| Dashboard tab | What to use it for |
| --- | --- |
| Overview | Daily regional values, a rolling mean, annual totals or mean temperatures |
| Seasons & months | Monthly heatmap and comparison of the four IMD seasons |
| Spatial explorer | Select an annual period and view an IDW surface or original grid centers |
| Trends | Mann–Kendall evidence and Theil–Sen slope from complete annual periods |
| Data & exports | Inspect regional tables and download tables or selected grid data |

Hover over charts for exact values and coverage. Use the chart toolbar to zoom,
pan, reset axes or download a PNG. The daily rolling mean requires a full window
of valid days.

### IMD seasons

| Season | Months |
| --- | --- |
| Winter | January–February |
| Pre-monsoon | March–May |
| Monsoon | June–September |
| Post-monsoon | October–December |

### IDW spatial maps

In **Spatial explorer**, select an **Annual period**. **IDW surface** estimates
values between valid grid centers using up to 12 nearest neighbors and
great-circle distances. Increase **IDW power** to give nearby points more
influence; change **Surface resolution** to adjust the rendering grid. Enable
**Overlay original grid centers** to inspect the source locations, or select
**Grid centers** to see the original annual values.

The surface is clipped to your selected region, including polygon holes. It can
extrapolate beyond observed centers inside that region. A smoother surface is
an interpolation, not additional observations or a finer-resolution measurement.
Statistics and exports use the original grid values. Colors share a scale across
selected annual periods to help comparison.

### Coverage, missing data and trends

Missing observations remain missing; they are never filled with zero. Rainfall
totals for partial periods are sums of available amounts, not estimates for the
missing days. Temperature means use available valid values.

Coverage is valid grid-days divided by expected grid-days. An annual period is
complete only if every selected grid cell has every expected daily value. Partial
annual bars have a pattern and are excluded from trend tests.

Regional values use cosine-latitude weights. Monthly, seasonal and annual
statistics aggregate each cell through time before spatial averaging; when data
are missing, they can differ from temporal aggregates of the regional daily chart.

Trends require at least three complete annual periods. The reported slope uses
actual elapsed years. The Mann–Kendall test does not correct for autocorrelation;
short records provide limited evidence. Check coverage and record length before
making a trend claim.

## 6. Download results

In **Data & exports**:

- Choose a daily, monthly, seasonal or annual table, then click **Download displayed
  table (CSV)**. Tables include coverage information.
- Click **Prepare selected grid data (NetCDF)**, then **Download selected grids**
  to save the original daily data for the selected dates and spatial mask.
- Click **Prepare annual grid points (GeoJSON)**, then **Download annual grid
  points** to save annual values at their original geographic grid centers.

After changing the source, region, years or annual grouping, prepare the relevant
export again. GeoJSON preserves annual field names without shapefile limits.
IDW surfaces are visualization layers and are not substituted into these exports.

## Troubleshooting

| Issue | What to check |
| --- | --- |
| No grid centers in the region | Enlarge the area; consider the source grid resolution |
| No data after choosing Draw rectangle | Draw an area and click Apply rectangle |
| Apply rectangle is disabled after an edit | Save the edit in the map toolbar; an unchanged rectangle does not need reapplying |
| An IMD year fails to download | Check publication availability, server internet access and Download details; upload a local file if needed |
| Variable or units cannot be identified | Choose the correct product and enter the documented variable/units in reader settings |
| Duplicate dates or different grids | Remove overlapping files; analyze different grids separately or preprocess them |
| Binary file size mismatch | Check year/leap year, resolution, float32 layout, and whether the file is a complete annual dataset |
| Incomplete annual periods | Check input gaps and the calendar-year range, especially June–May edges |
| Not enough trend data | Include at least three complete annual periods |

For large areas or long daily records, analyze smaller year ranges to limit
memory use. Keep a record of the source, selected dates, region, units, coverage
and annual grouping alongside exported results.

## Data sources

**Data credit:** India Meteorological Department (IMD), Ministry of Earth Sciences,
Government of India, for the gridded rainfall and temperature datasets. Acknowledge
IMD when using these datasets or publishing results derived from them. Synthetic
demo values are generated for this app and are not IMD observations.

Official source pages:
[Rainfall · 0.25° NetCDF](https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html) ·
[Maximum temperature](https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html) ·
[Minimum temperature](https://www.imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html).
