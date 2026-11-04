"""Validated IMD data ingestion and analysis, independent of the UI.

Canonical arrays have time, latitude, longitude dimensions; clipped arrays use
(time, point). All aggregation preserves NaN. No schema depends on file year.
"""
from __future__ import annotations

import calendar
import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import xarray as xr
from shapely import intersects_xy

PRODUCTS = {
    'rainfall': {'label': 'Rainfall', 'unit': 'mm', 'color': '#007f86', 'scale': 'Teal'},
    'tmax': {'label': 'Maximum temperature', 'unit': '°C', 'color': '#c75331', 'scale': 'OrRd'},
    'tmin': {'label': 'Minimum temperature', 'unit': '°C', 'color': '#4267b2', 'scale': 'Blues'},
}
ALIASES = {
    'rainfall': {'rainfall', 'rf', 'rain', 'precip', 'precipitation'},
    'tmax': {'tmax', 'maxtemp', 'max_temp', 'maximum_temperature', 'maximumtemperature', 'tasmax'},
    'tmin': {'tmin', 'mintemp', 'min_temp', 'minimum_temperature', 'minimumtemperature', 'tasmin'},
}
SEASONS = ['Winter', 'Pre-monsoon', 'Monsoon', 'Post-monsoon']
SEASON_MONTHS = { 'Winter': [1,2], 'Pre-monsoon': [3,4,5], 'Monsoon': [6,7,8,9], 'Post-monsoon': [10,11,12] }


def normalize_dataset(ds: xr.Dataset, product: str, variable: str | None = None,
                      units_override: str | None = None) -> xr.DataArray:
    """Detect CF/IMD names and normalize an actual dated, rectilinear daily grid."""
    if product not in PRODUCTS:
        raise ValueError('Choose rainfall, tmax or tmin.')
    names = {'time': {'time','date','day'}, 'latitude': {'latitude','lat'}, 'longitude': {'longitude','lon'}}
    rename = {}
    for target, aliases in names.items():
        matches = [n for n in ds.variables if n.lower() in aliases or
                   ds[n].attrs.get('standard_name', '').lower() == target or
                   ds[n].attrs.get('axis', '').upper() == {'time':'T','latitude':'Y','longitude':'X'}[target]]
        matches = [n for n in matches if ds[n].ndim == 1]
        if len(matches) != 1:
            raise ValueError(f'Cannot identify a unique 1D {target} coordinate; found {matches}.')
        name = matches[0]
        dim = ds[name].dims[0]
        if dim != name:
            ds = ds.swap_dims({dim: name})
        if name != target:
            rename[name] = target
    ds = ds.rename(rename)
    if variable is None:
        matches = [n for n in ds.data_vars if n.lower() in ALIASES[product]]
        if not matches:
            other_names = set().union(*(v for k,v in ALIASES.items() if k != product))
            if any(n.lower() in other_names for n in ds.data_vars):
                raise ValueError(f'No variable for selected product {product!r}; choose the matching climate variable.')
            matches = [n for n in ds.data_vars if {'time','latitude','longitude'} <= set(ds[n].dims)]
        if len(matches) != 1:
            raise ValueError(f'Select a data variable explicitly. Candidates: {matches or list(ds.data_vars)}')
        variable = matches[0]
    if variable not in ds.data_vars:
        raise ValueError(f'Data variable {variable!r} not found. Available: {list(ds.data_vars)}')
    a = ds[variable]
    for dim in set(a.dims) - {'time','latitude','longitude'}:
        if a.sizes[dim] != 1:
            raise ValueError(f'Unsupported dimension {dim!r}. Select a single level before uploading.')
        a = a.isel({dim: 0}, drop=True)
    if set(a.dims) != {'time','latitude','longitude'}:
        raise ValueError('Data variable must have time, latitude and longitude dimensions.')
    if not np.issubdtype(a.time.dtype, np.datetime64):
        raise ValueError('NetCDF time must decode to Gregorian dates using CF time units/calendar.')
    dates = pd.DatetimeIndex(a.time.values)
    if dates.hasnans or dates.duplicated().any() or not dates.equals(dates.normalize()):
        raise ValueError('Expected unique daily dates at midnight; duplicate or subdaily time found.')
    a = a.transpose('time','latitude','longitude').sortby(['time','latitude','longitude'])
    for name in ['latitude','longitude']:
        vals = np.asarray(a[name].values, dtype=float)
        if not len(vals) or not np.isfinite(vals).all() or len(np.unique(vals)) != len(vals):
            raise ValueError(f'Invalid or duplicate {name} coordinates.')
    if (abs(a.latitude.values) > 90).any() or (abs(a.longitude.values) > 180).any():
        raise ValueError('Coordinates must use latitude ±90 and longitude ±180 degrees.')
    attrs = a.attrs.copy()
    source_dtype = a.dtype
    a = a.astype('float64')
    a = a.where(np.isfinite(a))
    for sentinel in [-999, -9999, -99.9, attrs.get('missing_value'), attrs.get('_FillValue')]:
        if sentinel is not None:
            for v in np.atleast_1d(sentinel):
                # Compare at original precision: float32(-99.9) differs from float64(-99.9).
                sentinel_value = np.asarray(v, dtype=source_dtype).item() if np.issubdtype(source_dtype, np.floating) else v
                a = a.where(a != sentinel_value)
    units = (units_override or attrs.get('units', '')).strip().lower().replace(' ', '').replace('°','')
    if product == 'rainfall':
        if units not in {'mm','millimeter','millimeters','millimetre','millimetres','mm/day','mmd-1','mmday-1','kgm-2','kgm-2day-1','kgm-2d-1'}:
            raise ValueError(f'Unsupported rainfall units {units!r}; choose mm/day override only if justified by the source.')
        a = a.where(a >= 0)
    else:
        if units in {'k','kelvin','degrees_kelvin','degree_kelvin'}:
            a = a - 273.15
        elif units not in {'c','degc','celsius','degree_celsius','degrees_celsius','degreecelsius','degreescelsius'}:
            raise ValueError(f'Unsupported temperature units {units!r}; choose °C or K override based on the source.')
        a = a.where((a >= -100) & (a <= 70))
    a.name = product
    a.attrs = {'units': 'mm' if product == 'rainfall' else 'degC', 'source_variable': variable}
    return a


def read_netcdf(source, product: str, variable=None, units_override=None, bounds=None):
    """Close handles and optionally subset before loading large annual arrays."""
    with xr.open_dataset(source) as ds:
        a = normalize_dataset(ds, product, variable, units_override)
        if bounds is not None:
            west,south,east,north = bounds
            a = a.sel(latitude=slice(south,north), longitude=slice(west,east))
        return a.load()


def combine_arrays(arrays: list[xr.DataArray]) -> xr.DataArray:
    if not arrays:
        raise ValueError('No valid datasets loaded.')
    first = arrays[0]
    for a in arrays:
        if a.name != first.name:
            raise ValueError('Files must contain the same product.')
        if not np.array_equal(first.latitude, a.latitude) or not np.array_equal(first.longitude,a.longitude):
            raise ValueError('Files use a different grid. Analyze each grid separately; automatic regridding is disabled.')
    out = xr.concat(arrays, dim='time').sortby('time')
    if pd.DatetimeIndex(out.time.values).duplicated().any():
        raise ValueError('Overlapping or duplicate dates found across input files. Remove overlapping files.')
    return out


def select_region(a: xr.DataArray, bounds, geometry=None) -> xr.DataArray:
    west,south,east,north = bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError('Region bounds must be ordered west < east and south < north.')
    a = a.sel(latitude=slice(south,north),longitude=slice(west,east))
    if not a.sizes['latitude'] or not a.sizes['longitude']:
        raise ValueError('No grid centers inside these bounds. Expand the region.')
    points = a.stack(point=('latitude','longitude')).transpose('time','point')
    if geometry is not None:
        mask = intersects_xy(geometry,points.longitude.values,points.latitude.values)
        points = points.isel(point=np.flatnonzero(mask))
    if not points.sizes['point']:
        raise ValueError('No grid centers intersect the polygon. A finer-resolution dataset or larger region is required.')
    return points


def read_binary(raw: bytes, product: str, year: int, byte_order='<') -> xr.DataArray:
    """Annual IMD float32 grids, day/latitude/longitude (longitude fastest).

    RF 0.25°: 135 lat (6.5–40), 129 lon (66.5–98.5).
    Tmax/Tmin 1°: 31 lat (7.5–37.5), 31 lon (67.5–97.5).
    """
    if product not in PRODUCTS or byte_order not in {'<','>'} or not 1678 <= year <= 2260:
        raise ValueError('Invalid product, byte order or year (supported: 1678–2260).')
    nlat,nlon,lat0,lon0,step = (135,129,6.5,66.5,.25) if product == 'rainfall' else (31,31,7.5,67.5,1.)
    days = 366 if calendar.isleap(year) else 365
    expected = days*nlat*nlon*4
    if len(raw) != expected:
        raise ValueError(f'Binary size mismatch for {year}: expected {expected:,} bytes, got {len(raw):,}. Use a complete annual float32 grid.')
    vals = np.frombuffer(raw,dtype=f'{byte_order}f4').reshape(days,nlat,nlon)
    ds = xr.Dataset({product: (('time','latitude','longitude'), vals, {'units':'mm' if product == 'rainfall' else 'degC'})}, coords={'time':pd.date_range(f'{year}-01-01',periods=days), 'latitude':lat0+step*np.arange(nlat), 'longitude':lon0+step*np.arange(nlon)})
    return normalize_dataset(ds,product)


def read_region(raw: bytes, filename: str) -> gpd.GeoDataFrame:
    """Read a polygon; require a CRS and safely extract zipped shapefiles."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        if filename.lower().endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if sum(f.file_size for f in z.infolist()) > 100_000_000:
                    raise ValueError('Region archive expands beyond 100 MB.')
                for f in z.infolist():
                    if '\\' in f.filename or not (root / f.filename).resolve().is_relative_to(root.resolve()):
                        raise ValueError('Unsafe path in region archive.')
                z.extractall(root)
            shapes = list(root.rglob('*.shp'))
            if len(shapes) != 1:
                raise ValueError('ZIP must contain exactly one shapefile with its .shx, .dbf and .prj files.')
            path = shapes[0]
        else:
            path = root / ('region' + Path(filename).suffix.lower())
            path.write_bytes(raw)
        gdf = gpd.read_file(path)
    if gdf.empty or gdf.crs is None:
        raise ValueError('Region must contain polygons and declare its coordinate reference system (CRS).')
    gdf = gdf.to_crs(4326)
    if not gdf.geometry.geom_type.isin(['Polygon','MultiPolygon']).all() or not gdf.is_valid.all():
        raise ValueError('Region must contain valid Polygon or MultiPolygon geometries.')
    return gdf


def _aggregate_points(a, groups, product):
    g = a.groupby(groups)
    return g.sum(dim='time',skipna=True,min_count=1) if product == 'rainfall' else g.mean(dim='time',skipna=True)


def summarize(points: xr.DataArray, product: str, hydro=False) -> dict:
    """Aggregate per grid first, then cosine-latitude-weighted regional means.

    Complete means every grid has a valid observation on every expected day.
    Coverage is valid grid-days / expected grid-days, so gaps remain visible.
    """
    if not points.sizes['time']:
        raise ValueError('No observations in the selected years.')
    dates = pd.DatetimeIndex(points.time.values)
    weights = xr.DataArray(np.cos(np.deg2rad(points.latitude.values)),dims='point',coords={'point':points.point})
    daily_values = points.weighted(weights).mean('point').values
    daily = pd.DataFrame({'date':dates, 'value':daily_values, 'valid_cells':points.count('point').values})
    daily['coverage'] = daily.valid_cells / points.sizes['point']
    # Reindex the displayed daily line to expose gaps instead of connecting them.
    daily = daily.set_index('date').reindex(pd.date_range(dates.min(),dates.max(),freq='D')).rename_axis('date').reset_index()
    daily['coverage'] = daily.coverage.fillna(0.)
    rows = {}
    grids = {}
    for kind in ['monthly','seasonal','annual']:
        if kind == 'monthly':
            labels = dates.strftime('%Y-%m')
        elif kind == 'seasonal':
            labels = np.array([f'{d.year}-{next(i for i,s in enumerate(SEASONS) if d.month in SEASON_MONTHS[s])}' for d in dates])
        else:
            labels = (dates.year - ((dates.month < 6) if hydro else 0)).astype(str)
        group = xr.DataArray(labels,dims='time',coords={'time':points.time},name='period')
        agg = _aggregate_points(points, group, product)
        means = agg.weighted(weights).mean('point')
        period_rows = []
        for label in agg.period.values:
            year = int(str(label)[:4])
            if kind == 'monthly':
                month = int(str(label)[5:])
                expected = calendar.monthrange(year,month)[1]
                extra = {'month':month}
            elif kind == 'seasonal':
                season = SEASONS[int(str(label)[5:])]
                expected = sum(calendar.monthrange(year,m)[1] for m in SEASON_MONTHS[season])
                extra = {'season':season}
            else:
                start = pd.Timestamp(year,6 if hydro else 1,1)
                end = pd.Timestamp(year+1,6 if hydro else 1,1)
                expected = (end-start).days
                extra = {}
            sub = points.isel(time=np.flatnonzero(labels == label))
            valid_count = int(sub.count().item())
            expected_count = expected*points.sizes['point']
            coverage = valid_count / expected_count
            period_rows.append({'period':str(label),'year':year, **extra, 'value':float(means.sel(period=label)), 'days':sub.sizes['time'], 'expected_days':expected, 'coverage':coverage, 'complete':valid_count == expected_count})
        rows[kind] = pd.DataFrame(period_rows)
        grids[kind] = agg
    return {'daily':daily, **rows, 'grids':grids, 'points':points, 'product':product, 'hydro':hydro}


def trend_table(annual: pd.DataFrame) -> pd.DataFrame:
    """MK and Theil–Sen on complete years only; slope uses actual year spacing."""
    import pymannkendall as mk
    from scipy.stats import theilslopes
    valid = annual.loc[annual.complete & annual.value.notna()].sort_values('year')
    if len(valid) < 3:
        return pd.DataFrame([{'trend':'Insufficient data (3 complete years required)','years':len(valid),'p_value':np.nan,'slope_per_year':np.nan}])
    if valid.value.nunique() == 1:
        return pd.DataFrame([{'trend':'no trend','years':len(valid),'p_value':1.,'slope_per_year':0.}])
    result = mk.original_test(valid.value.to_numpy())
    slope = theilslopes(valid.value.to_numpy(),valid.year.to_numpy()).slope
    return pd.DataFrame([{'trend':result.trend,'years':len(valid),'p_value':result.p,'slope_per_year':float(slope)}])


def download_rainfall(year: int, folder='imd_netcdf_files') -> Path:
    """Validate NetCDF before publishing cache; HTML/error pages never become .nc."""
    root = Path(folder)
    root.mkdir(parents=True,exist_ok=True)
    target = root / f'RF25_{int(year)}.nc'
    def validate(path):
        with xr.open_dataset(path) as ds:
            a = normalize_dataset(ds,'rainfall')
            if set(a.time.dt.year.values) != {year}:
                raise ValueError(f'Downloaded dataset does not contain only the requested year {year}.')
    if target.exists():
        validate(target)
        return target
    part = None
    try:
        with tempfile.NamedTemporaryFile(dir=root,suffix='.part',delete=False) as f:
            part = Path(f.name)
            with requests.post('https://www.imdpune.gov.in/cmpg/Griddata/RF25.php',data={'RF25':str(year)},stream=True,timeout=(15,180)) as response:
                response.raise_for_status()
                for chunk in response.iter_content(1024*1024):
                    f.write(chunk)
                length = response.headers.get('content-length')
            if length and f.tell() != int(length):
                raise ValueError('Download size mismatch; retry the year.')
        validate(part)
        part.replace(target)
        return target
    finally:
        if part is not None:
            part.unlink(missing_ok=True)


def demo_dataset(product: str) -> xr.DataArray:
    """Small deterministic synthetic grid for an offline tour; never IMD observations."""
    dates = pd.date_range('2020-01-01','2024-12-31')
    lat,lon = np.arange(8.5,12.6,.5),np.arange(74.5,77.6,.5)
    rng = np.random.default_rng(42)
    day = dates.dayofyear.to_numpy()[:,None,None]
    shape = (len(dates),len(lat),len(lon))
    if product == 'rainfall':
        seasonal = 1 + 15*np.maximum(0,np.sin(2*np.pi*(day-135)/366))
        values = rng.gamma(1.1,1.8,shape)*seasonal
        values[rng.random(shape)<.4] = 0
    else:
        seasonal = 4*np.sin(2*np.pi*(day-20)/366)
        values = (29 if product == 'tmax' else 21)+seasonal+rng.normal(0,1.4,shape)
    return xr.DataArray(values,dims=('time','latitude','longitude'),coords={'time':dates,'latitude':lat,'longitude':lon},name=product,attrs={'units':'mm' if product=='rainfall' else 'degC'})


# Re-export the temperature downloader alongside the existing rainfall helper.
from imd_sources import download_temperature


def idw_surface(longitudes, latitudes, values, bounds, geometry=None,
                power=2., resolution=120, neighbors=12):
    """Finite-only nearest-neighbor IDW using spherical great-circle distances.

    Exact sample matches retain their values. The target is masked by the full
    polygon (including holes); this surface never changes analysis statistics.
    """
    from scipy.spatial import cKDTree
    if not 0 < power <= 8 or not 2 <= resolution <= 400 or neighbors < 1:
        raise ValueError('Use IDW power (0, 8], resolution 2–400 and at least one neighbor.')
    west,south,east,north = bounds
    if not (-180<=west<east<=180 and -90<=south<north<=90):
        raise ValueError('Invalid interpolation bounds.')
    lon,lat,val = np.asarray(longitudes,float),np.asarray(latitudes,float),np.asarray(values,float)
    if lon.ndim!=1 or lat.shape!=lon.shape or val.shape!=lon.shape:
        raise ValueError('IDW coordinates and values must be equal-length 1D arrays.')
    x,y = np.meshgrid(np.linspace(west,east,resolution),np.linspace(south,north,resolution))
    z = np.full(x.shape,np.nan)
    finite = np.isfinite(lon)&np.isfinite(lat)&np.isfinite(val)
    if not finite.any(): return x,y,z
    lon,lat,val=lon[finite],lat[finite],val[finite]
    def unit_sphere(lons,lats):
        lons,lats=np.deg2rad(lons),np.deg2rad(lats)
        return np.column_stack((np.cos(lats)*np.cos(lons),np.cos(lats)*np.sin(lons),np.sin(lats)))
    sample_xyz=unit_sphere(lon,lat)
    target_xyz=unit_sphere(x.ravel(),y.ravel())
    k=min(int(neighbors),len(val))
    distances,indices=cKDTree(sample_xyz).query(target_xyz,k=k)
    distances,indices=distances.reshape(-1,k),indices.reshape(-1,k)
    distances=2*np.arcsin(np.clip(distances/2,0,1))
    exact=distances[:,0]<1e-12
    output=np.empty(x.size)
    output[exact]=val[indices[exact,0]]
    remaining=~exact
    # Normalize by the closest distance before exponentiation to avoid overflow.
    weights=(distances[remaining,:1]/distances[remaining])**power
    output[remaining]=(weights*val[indices[remaining]]).sum(axis=1)/weights.sum(axis=1)
    z=output.reshape(x.shape)
    if geometry is not None:
        z=np.where(intersects_xy(geometry,x,y),z,np.nan)
    return x,y,z
