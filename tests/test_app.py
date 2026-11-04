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
    assert len(app.tabs) == 5
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
