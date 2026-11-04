from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / 'streamlit_imd_dashboard.py')

@pytest.mark.parametrize('product',['Rainfall','Maximum temperature','Minimum temperature'])
def test_demo_all_products_and_year_selection(product):
    app = AppTest.from_file(APP,default_timeout=30).run()
    assert not app.exception
    app.sidebar.selectbox(key='product').select(product).run()
    assert not app.exception
    assert {'Overview','Seasons & months','Spatial explorer','Trends','Data & exports'} <= {tab.label for tab in app.tabs}
    assert len(app.metric) >= 4
    app.sidebar.select_slider(key='years').set_value((2024,2024)).run()
    assert not app.exception
    assert app.session_state['analysis']['annual'].year.tolist() == [2024]
    if product != 'Rainfall':
        assert app.session_state['analysis']['annual'].value.max() < 40
    app.sidebar.selectbox(key='year_basis').select('June–May hydrological year').run()
    assert not app.exception
    assert not app.session_state['analysis']['annual'].complete.any()


def test_upload_empty_state_has_no_stale_results():
    app = AppTest.from_file(APP,default_timeout=30).run()
    app.sidebar.radio(key='source').set_value('Upload files').run()
    assert not app.exception
    assert 'analysis' not in app.session_state
    assert len(app.metric) == 0


def test_export_buttons_prepare_files_without_resetting_results():
    app = AppTest.from_file(APP,default_timeout=30).run()
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state['grid_export'][1][:3] == b'CDF'
    app.button[1].click().run()
    assert not app.exception
    import json
    geo = json.loads(app.session_state['geo_export'][1])
    assert geo['type'] == 'FeatureCollection'
    assert len(geo['features']) == 63
    assert 'analysis' in app.session_state


def test_official_tmax_binary_source_is_shown_for_temperature():
    app = AppTest.from_file(APP,default_timeout=30).run()
    app.sidebar.selectbox(key='product').select('Maximum temperature').run()
    assert not app.exception
    assert any('https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html' in item.value for item in app.sidebar.markdown)


@pytest.mark.parametrize('product',['Maximum temperature','Minimum temperature'])
def test_builtin_temperature_download_and_product_state(tmp_path,monkeypatch,product):
    import numpy as np
    calls=[]
    def fetch(year,kind,folder='imd_netcdf_files',byte_order='<'):
        calls.append((year,kind))
        import calendar
        count=366 if calendar.isleap(year) else 365
        path=tmp_path/f'{kind.upper()}_{year}.grd'
        path.write_bytes(np.full((count,31,31),25,dtype='<f4').tobytes())
        return path
    monkeypatch.setattr('imd_data.download_temperature',fetch)
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.sidebar.selectbox(key='product').select(product).run()
    app.sidebar.radio(key='source').set_value('Download from IMD').run()
    assert not app.exception
    next(b for b in app.sidebar.button if b.label=='Download selected years').click().run()
    assert not app.exception
    assert len(calls)==2
    assert all(kind==('tmax' if product=='Maximum temperature' else 'tmin') for _,kind in calls)
    assert app.session_state['analysis']['annual'].value.iloc[0]==pytest.approx(25)
    # A batch for one product must never appear as another product's observations.
    other='Minimum temperature' if product=='Maximum temperature' else 'Maximum temperature'
    app.sidebar.selectbox(key='product').select(other).run()
    assert 'analysis' not in app.session_state


def test_draw_rectangle_apply_edit_clear_and_analysis_bounds(monkeypatch):
    current={'all_drawings':None}
    monkeypatch.setattr('map_region.st_folium',lambda *args,**kwargs:current)
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.sidebar.radio(key='region_method').set_value('Draw rectangle').run()
    assert not app.exception
    assert 'analysis' not in app.session_state
    assert app.button(key='apply_rectangle').disabled
    def rectangle(w,s,e,n):
        return {'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[w,s],[e,s],[e,n],[w,n],[w,s]]]},'properties':{}}
    current['all_drawings']=[rectangle(75,10,76,11)]
    app.run()
    assert 'analysis' not in app.session_state
    app.button(key='apply_rectangle').click().run()
    assert not app.exception
    assert app.session_state['rectangle_applied']==(75,10,76,11)
    assert app.button(key='apply_rectangle').disabled
    assert app.session_state['analysis']['points'].sizes['point']==9
    # An edit remains a draft until explicitly applied.
    current['all_drawings']=[rectangle(75,10,75.5,10.5)]
    app.run()
    assert app.session_state['analysis']['points'].sizes['point']==9
    app.button(key='apply_rectangle').click().run()
    assert app.session_state['analysis']['points'].sizes['point']==4
    # The selection survives product changes.
    app.sidebar.selectbox(key='product').select('Minimum temperature').run()
    assert app.session_state['analysis']['points'].sizes['point']==4
    current['all_drawings']=None
    app.button(key='clear_rectangle').click().run()
    assert 'analysis' not in app.session_state
    assert 'rectangle_applied' not in app.session_state


def test_rectangle_draft_edits_reuse_applied_analysis(monkeypatch):
    import imd_data
    original=imd_data.summarize
    calls=[]
    def summarize(*args,**kwargs):
        calls.append(1)
        return original(*args,**kwargs)
    monkeypatch.setattr('imd_data.summarize',summarize)
    drawn={'all_drawings':[{'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[75,10],[76,10],[76,11],[75,11],[75,10]]]},'properties':{}}]}
    monkeypatch.setattr('map_region.st_folium',lambda *args,**kwargs:drawn)
    app=AppTest.from_file(APP,default_timeout=30).run()
    app.sidebar.radio(key='region_method').set_value('Draw rectangle').run()
    app.button(key='apply_rectangle').click().run()
    before=len(calls)
    drawn['all_drawings'][0]['geometry']['coordinates']=[[[75,10],[75.5,10],[75.5,10.5],[75,10.5],[75,10]]]
    app.run()
    assert len(calls)==before


def test_usage_guide_and_attribution_available_in_empty_state():
    app=AppTest.from_file(APP,default_timeout=30).run()
    assert 'How to use this app' in [tab.label for tab in app.tabs]
    guide=next(tab for tab in app.tabs if tab.label=='How to use this app')
    content='\n'.join(item.value for item in guide.markdown)
    assert 'Apply rectangle' in content
    assert 'Download from IMD' in content
    assert 'IDW' in content
    assert 'NetCDF' in content
    attribution='Webapp Prepared by Dr Sachchidanand Singh, Assistant Professor, IIT Mandi'
    assert app.markdown[-1].value==attribution
    app.sidebar.radio(key='source').set_value('Upload files').run()
    assert not app.exception
    assert app.markdown[-1].value==attribution
    assert 'How to use this app' in [tab.label for tab in app.tabs]
