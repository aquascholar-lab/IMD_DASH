import io
import zipfile
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import Polygon
from imd_data import normalize_dataset, combine_arrays, select_region, summarize, read_binary, read_region


def dataset(name='RAINFALL', dates=None, value=1., units='mm', descending=False):
    dates = pd.date_range('2024-01-01', '2024-12-31') if dates is None else pd.to_datetime(dates)
    return xr.Dataset({name: (('TIME','LATITUDE','LONGITUDE'), np.full((len(dates),2,2), value), {'units':units})}, coords={'TIME':dates, 'LATITUDE':[11.,10.] if descending else [10.,11.], 'LONGITUDE':[75.,76.]})


def test_schema_is_inferred_not_guessed_from_year():
    a = normalize_dataset(dataset(dates=['2032-02-28','2032-02-29']), 'rainfall')
    b = normalize_dataset(dataset('rf',dates=['2032-03-01']), 'rainfall')
    result = combine_arrays([a,b])
    assert result.sizes['time'] == 3
    assert result.time.dt.year.values.tolist() == [2032]*3


def test_descending_coords_and_default_rectangle():
    a = normalize_dataset(dataset(descending=True), 'rainfall')
    selected = select_region(a, (75,10,76,11))
    assert selected.sizes['point'] == 4
    assert selected.latitude.values.tolist() == [10,10,11,11]


def test_temperature_kelvin_and_mean_not_sum():
    a = normalize_dataset(dataset('tmax',value=300,units='K'), 'tmax')
    r = summarize(select_region(a,(75,10,76,11)), 'tmax')
    assert r['annual'].value.iloc[0] == pytest.approx(26.85)
    assert r['annual'].complete.iloc[0]
    assert r['monthly'].value.iloc[0] == pytest.approx(26.85)


def test_missing_rain_is_not_zero_and_partial_year_is_flagged():
    ds = dataset(dates=['2023-01-01','2023-01-02'])
    ds['RAINFALL'].values[:] = np.nan
    r = summarize(select_region(normalize_dataset(ds,'rainfall'),(75,10,76,11)), 'rainfall')
    assert np.isnan(r['annual'].value.iloc[0])
    assert not r['annual'].complete.iloc[0]
    assert r['annual'].coverage.iloc[0] == 0


def test_hydrological_year_starts_june_and_labels_start_year():
    a = normalize_dataset(dataset(dates=pd.date_range('2023-06-01','2024-05-31')), 'rainfall')
    r = summarize(select_region(a,(75,10,76,11)), 'rainfall', hydro=True)
    assert r['annual'].year.tolist() == [2023]
    assert r['annual'].value.iloc[0] == 366
    assert r['annual'].complete.iloc[0]


def test_polygon_holes_and_boundary_are_respected():
    a = normalize_dataset(dataset(dates=['2024-01-01']), 'rainfall')
    poly = Polygon([(75,10),(77,10),(77,12),(75,12)], holes=[[(75.8,10.8),(76.2,10.8),(76.2,11.2),(75.8,11.2)]])
    selected = select_region(a,(75,10,76,11),poly)
    assert selected.sizes['point'] == 3


def test_duplicate_dates_rejected():
    a = normalize_dataset(dataset(dates=['2024-01-01']), 'rainfall')
    with pytest.raises(ValueError, match='[Oo]verlap|[Dd]uplicate'):
        combine_arrays([a,a])


def test_different_grids_rejected():
    a = normalize_dataset(dataset(dates=['2024-01-01']), 'rainfall')
    b = normalize_dataset(dataset(dates=['2024-01-02']), 'rainfall').assign_coords(latitude=[12,13])
    with pytest.raises(ValueError, match='grid'):
        combine_arrays([a,b])


def test_ambiguous_variable_requires_explicit_selection():
    ds = dataset('a')
    ds['b'] = ds.a
    with pytest.raises(ValueError, match='variable'):
        normalize_dataset(ds,'rainfall')
    assert normalize_dataset(ds,'rainfall',variable='a').name == 'rainfall'


def test_non_date_time_rejected():
    ds = dataset(dates=['2024-01-01']).assign_coords(TIME=[0])
    with pytest.raises(ValueError,match='time|date'):
        normalize_dataset(ds,'rainfall')


def test_binary_length_validation_and_leap_year():
    with pytest.raises(ValueError, match='bytes|size'):
        read_binary(b'1234','tmin',2024)
    raw = np.full((366,31,31),22,dtype='<f4').tobytes()
    a = read_binary(raw,'tmin',2024)
    assert a.sizes['time'] == 366
    assert str(a.time.values[59])[:10] == '2024-02-29'
    assert a.latitude.values[0] == 7.5


def test_zip_traversal_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('../evil.shp','x')
    with pytest.raises(ValueError, match='[Uu]nsafe'):
        read_region(buf.getvalue(),'region.zip')


def test_rainfall_sentinel_masked_and_temperature_negative_preserved():
    r = normalize_dataset(dataset(value=-999), 'rainfall')
    assert np.isnan(r.values).all()
    t = normalize_dataset(dataset('tmin',value=-5,units='degC'), 'tmin')
    assert (t.values == -5).all()


def test_wrong_product_is_not_silently_relabelled():
    with pytest.raises(ValueError,match='product|variable'):
        normalize_dataset(dataset('tmax',units='degC'),'rainfall')


def test_even_one_missing_cell_day_makes_year_incomplete():
    dates = pd.date_range('2024-01-01','2024-12-31')
    vals = np.ones((366,20,20))
    vals[0,0,0] = np.nan
    a = xr.DataArray(vals,dims=('time','latitude','longitude'),coords={'time':dates,'latitude':np.linspace(10,11,20),'longitude':np.linspace(75,76,20)},name='rainfall')
    r = summarize(select_region(a,(75,10,76,11)),'rainfall')
    assert not r['annual'].complete.iloc[0]
    assert r['annual'].coverage.iloc[0] < 1


def test_unknown_units_require_override():
    with pytest.raises(ValueError,match='units'):
        normalize_dataset(dataset('tmin',units='mystery'),'tmin')
    a = normalize_dataset(dataset('tmin',value=300,units='mystery'),'tmin',units_override='K')
    assert float(a.mean()) == pytest.approx(26.85)


def test_netcdf_round_trip_and_spatial_subset(tmp_path):
    from imd_data import read_netcdf
    path = tmp_path/'arbitrary-file-name.nc'
    dataset('MAX_TEMP',dates=['2040-02-29'],value=25,units='degC',descending=True).to_netcdf(path)
    a = read_netcdf(path,'tmax',bounds=(75,10,75.5,11))
    assert a.sizes == {'time':1,'latitude':2,'longitude':1}
    assert str(a.time.values[0])[:10] == '2040-02-29'
    assert float(a.mean()) == 25


def test_irregular_year_trend_uses_elapsed_years():
    from imd_data import trend_table
    frame = pd.DataFrame({'year':[2000,2002,2004],'value':[10.,12.,14.],'complete':[True]*3})
    assert trend_table(frame).slope_per_year.iloc[0] == 1
    assert 'Insufficient' in trend_table(frame.iloc[:2]).trend.iloc[0]


def test_invalid_download_never_enters_cache(tmp_path,monkeypatch):
    from imd_data import download_rainfall
    class Response:
        headers = {}
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def raise_for_status(self): pass
        def iter_content(self,*args): yield b'<html>not published yet</html>'
    monkeypatch.setattr('imd_data.requests.post',lambda *args,**kwargs: Response())
    with pytest.raises((ValueError,OSError)):
        download_rainfall(2040,tmp_path)
    assert not list(tmp_path.iterdir())


def test_valid_download_is_dated_and_cached(tmp_path,monkeypatch):
    from imd_data import download_rainfall
    payload = bytes(dataset(dates=['2040-02-29']).to_netcdf(engine='scipy'))
    class Response:
        headers = {'content-length':str(len(payload))}
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def raise_for_status(self): pass
        def iter_content(self,*args): yield payload
    monkeypatch.setattr('imd_data.requests.post',lambda *args,**kwargs: Response())
    path = download_rainfall(2040,tmp_path)
    assert path.read_bytes() == payload
    monkeypatch.setattr('imd_data.requests.post',lambda *args,**kwargs: pytest.fail('cache should avoid a request'))
    assert download_rainfall(2040,tmp_path) == path


def test_geojson_region_and_crs():
    from shapely.geometry import mapping
    import json
    shape = Polygon([(75,10),(76,10),(76,11),(75,11)])
    raw = json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':mapping(shape)}]}).encode()
    region = read_region(raw,'region.geojson')
    assert region.crs.to_epsg() == 4326
    assert region.total_bounds.tolist() == [75,10,76,11]


def test_missing_daily_dates_are_visible_gaps():
    a = normalize_dataset(dataset(dates=['2024-01-01','2024-01-03']),'rainfall')
    r = summarize(select_region(a,(75,10,76,11)),'rainfall')
    assert r['daily'].shape[0] == 3
    assert np.isnan(r['daily'].value.iloc[1])
    assert r['daily'].coverage.iloc[1] == 0


def test_float32_temperature_sentinel_in_binary_is_missing():
    raw = np.full((365,31,31),-99.9,dtype='<f4').tobytes()
    a = read_binary(raw,'tmin',2023)
    assert a.count().item() == 0


def test_float32_temperature_sentinel_in_netcdf_is_missing(tmp_path):
    from imd_data import read_netcdf
    ds = dataset('tmin',dates=['2024-01-01'],value=-99.9,units='degC').astype('float32')
    ds['tmin'].attrs['units'] = 'degC'
    ds['tmin'].values[0,0,1] = -5
    path = tmp_path/'tmin.nc'
    ds.to_netcdf(path)
    a = read_netcdf(path,'tmin')
    assert a.count().item() == 1
    assert float(a.mean()) == -5


def test_unsigned_integer_rainfall_is_accepted():
    ds = dataset(dates=['2024-01-01'],value=3).astype('uint16')
    ds['RAINFALL'].attrs['units'] = 'mm'
    a = normalize_dataset(ds,'rainfall')
    assert float(a.mean()) == 3
