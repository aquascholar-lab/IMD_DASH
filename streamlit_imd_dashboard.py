"""Launch: streamlit run streamlit_imd_dashboard.py"""
from __future__ import annotations

import hashlib
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from imd_data import (PRODUCTS, combine_arrays, demo_dataset, download_rainfall, download_temperature,
                      read_binary, read_netcdf, read_region, select_region, summarize, trend_table)
from imd_sources import TEMPERATURE_PAGES
from map_region import rectangle_selector
from imd_charts import annual_chart, daily_chart, monthly_heatmap, seasonal_chart, spatial_chart

st.set_page_config(page_title='IMD Climate Atlas',page_icon='🌦️',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.stApp {background: #f5f8fa;}
.block-container {padding-top: 2rem; max-width: 1500px;}
[data-testid="stSidebar"] {background: #eaf0f4; border-right: 1px solid #d5e0e7;}
h1,h2,h3 {color: #142c40; letter-spacing: -.025em;}
[data-testid="stMetric"] {background: white; padding: 18px; border: 1px solid #dce7ec;
 border-radius: 12px; border-top: 3px solid #00828b; min-height: 125px;}
[data-testid="stMetricLabel"] {color: #486071;}
[data-testid="stMetricValue"] {color: #142c40; font-size: 1.8rem;}
.hero {background: linear-gradient(115deg,#122c40,#14515e); color: white;
 padding: 28px 32px; border-radius: 16px; margin-bottom: 24px;}
.hero h1 {color: white; font-size: 2.4rem; margin: 4px 0; padding: 0;}
.hero p {color: #d5e8ed; max-width: 780px; margin: 8px 0 0;}
.eyebrow {color:#83d9d5; font-size: .75rem; letter-spacing: .18em; font-weight: 700;}
[data-baseweb="tab-list"] {gap: 16px;}
[data-baseweb="tab"] {min-height: 48px;}
.stDownloadButton button, .stButton button {min-height: 44px; border-radius: 8px;}
@media(max-width: 650px) {.hero {padding: 20px;} .hero h1 {font-size: 1.9rem;}}
</style>''',unsafe_allow_html=True)


@st.cache_data(show_spinner=False,max_entries=8)
def load_uploads(files,product,variable,units,binary_year,byte_order,bounds):
    arrays = []
    for filename,raw in files:
        if Path(filename).suffix.lower() in {'.grd','.bin'}:
            # Raw annual binaries have no timestamp metadata: require explicit year.
            a = read_binary(raw,product,binary_year,byte_order)
            west,south,east,north = bounds
            a = a.sel(latitude=slice(south,north),longitude=slice(west,east))
        else:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'input.nc'
                path.write_bytes(raw)
                a = read_netcdf(path,product,variable or None,units,bounds)
        arrays.append(a)
    return combine_arrays(arrays)


@st.cache_data(show_spinner=False,max_entries=8)
def load_downloads(paths,bounds,product='rainfall',byte_order='<'):
    if product == 'rainfall':
        return combine_arrays([read_netcdf(path,product,bounds=bounds) for path in paths])
    arrays=[]
    west,south,east,north=bounds
    for path in paths:
        year=int(Path(path).stem.rsplit('_',1)[1])
        a=read_binary(Path(path).read_bytes(),product,year,byte_order)
        arrays.append(a.sel(latitude=slice(south,north),longitude=slice(west,east)))
    return combine_arrays(arrays)


@st.cache_data(show_spinner=False,max_entries=3)
def load_demo(product):
    return demo_dataset(product)


def plot(fig,key):
    st.plotly_chart(fig,width="stretch",key=key,config={'displaylogo':False,'toImageButtonOptions':{'format':'png','scale':2}})


def csv_download(label,df,name):
    st.download_button(label,df.to_csv(index=False).encode('utf-8'),name,'text/csv',key='download_'+name)


def main():
    st.markdown('''<div class="hero"><div class="eyebrow">INDIA · GRIDDED CLIMATE EXPLORER</div>
    <h1>IMD Climate Atlas</h1><p>Explore rainfall and temperature across space, seasons and years.
    Bring your IMD datasets, choose a region, and follow the evidence.</p></div>''',unsafe_allow_html=True)
    # Clear at the beginning of every rerun, including invalid inputs and empty uploads.
    st.session_state.pop('analysis',None)
    with st.sidebar:
        st.title('Climate workspace')
        label = st.selectbox('Climate variable',[v['label'] for v in PRODUCTS.values()],key='product')
        product = next(k for k,v in PRODUCTS.items() if v['label']==label)
        meta = PRODUCTS[product]
        if product=='rainfall':
            st.markdown('[IMD rainfall · 0.25° NetCDF source](https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html)')
        if product in TEMPERATURE_PAGES:
            st.markdown(f'[IMD {meta["label"].lower()} · 1° binary source]({TEMPERATURE_PAGES[product]})')
            st.caption('Choose Download from IMD for built-in annual retrieval, or upload files you already have.')
        source = st.radio('Data source',['Demo · synthetic','Upload files','Download from IMD'],key='source')
        st.divider()
        st.subheader('Study region')
        region_mode = st.radio('Region method',['Bounding box','Draw rectangle','Upload polygon'],key='region_method')
        previous_region_mode=st.session_state.get('previous_region_method')
        if region_mode=='Draw rectangle' and previous_region_mode!=region_mode:
            st.session_state['rectangle_draft']=st.session_state.get('rectangle_applied')
            st.session_state['rectangle_epoch']=st.session_state.get('rectangle_epoch',0)+1
        st.session_state['previous_region_method']=region_mode
        geometry = None
        region_name = 'Kerala bounds'
        if region_mode == 'Upload polygon':
            region_file = st.file_uploader('GeoJSON, KML or zipped shapefile',type=['geojson','json','kml','zip'],key='polygon')
            if region_file is None:
                st.info('Upload a polygon to set the study area.')
                return
            try:
                region = read_region(region_file.getvalue(),region_file.name)
                geometry = region.geometry.union_all()
                bounds = tuple(region.total_bounds)
                region_name = Path(region_file.name).stem
            except Exception as exc:
                st.error(f'Cannot read region: {exc}')
                return
        elif region_mode == 'Bounding box':
            left,right = st.columns(2)
            west = left.number_input('West longitude',-180.,180.,74.5,step=.25)
            east = right.number_input('East longitude',-180.,180.,77.5,step=.25)
            south = left.number_input('South latitude',-90.,90.,8.5,step=.25)
            north = right.number_input('North latitude',-90.,90.,12.5,step=.25)
            bounds = (west,south,east,north)
            if bounds != (74.5,8.5,77.5,12.5):
                region_name = 'Custom bounds'
        else:
            bounds=None
            region_name='Drawn rectangle'
        if bounds is not None and not (bounds[0]<bounds[2] and bounds[1]<bounds[3]):
            st.error('Use west < east and south < north.')
            return
        st.caption('Grid centers on the polygon boundary are included; holes are excluded.')

    if region_mode=='Draw rectangle':
        bounds=rectangle_selector()
        if bounds is None:
            return

    try:
        if source == 'Demo · synthetic':
            data = load_demo(product)
            st.info('SYNTHETIC DEMO · 2020–2024 · These generated values demonstrate the app; they are not IMD observations.')
            source_id = 'demo-'+product
        elif source == 'Upload files':
            with st.sidebar:
                uploads = st.file_uploader('Daily gridded datasets',type=['nc','nc4','netcdf','grd','bin'],accept_multiple_files=True,key='datasets')
                with st.expander('NetCDF / binary settings'):
                    variable = st.text_input('NetCDF variable name (optional)',help='Leave blank for automatic detection; enter a name if the file has multiple candidates.')
                    unit_label = st.selectbox('Source units',['From file metadata','mm/day','°C','K'])
                    units = {'From file metadata':None,'mm/day':'mm/day','°C':'degC','K':'K'}[unit_label]
                    binary_year = int(st.number_input('Binary file year',1678,2260,date.today().year-1))
                    byte_order = '<' if st.selectbox('Binary byte order',['Little endian','Big endian'])=='Little endian' else '>'
                    st.caption('Binary: one complete annual file at a time. RF: 135 × 129 at 0.25°. Tmax/Tmin: 31 × 31 at 1°. Day, latitude, longitude order; float32.')
            if not uploads:
                st.subheader('Start with your climate data')
                st.write('Upload daily IMD NetCDF files from any year, or a complete annual IMD binary grid. Select rainfall, Tmax or Tmin in the sidebar.')
                st.caption('NetCDF dates and coordinate names are detected from the dataset. Files must share one grid and must not overlap in time.')
                return
            if any(Path(f.name).suffix.lower() in {'.grd','.bin'} for f in uploads) and len(uploads)>1:
                st.error('Upload one binary annual file at a time; use multiple NetCDF files for multi-year analysis.')
                return
            files = tuple((f.name,f.getvalue()) for f in uploads)
            source_id = hashlib.sha256(repr(([(n,hashlib.sha256(b).hexdigest()) for n,b in files],product,variable,units,binary_year,byte_order)).encode()).hexdigest()
            with st.spinner('Validating dates, units and grid coordinates…'):
                data = load_uploads(files,product,variable,units,binary_year,byte_order,tuple(bounds))
            st.caption(f'Uploaded data · {len(files)} file(s) · {meta["label"]}')
        else:
            with st.sidebar:
                st.caption('Requests the selected years from IMD. Availability depends on IMD publication, not this app’s year selector.')
                current = date.today().year
                minimum_year = 1901 if product == 'rainfall' else 1951
                start = int(st.number_input('First download year',minimum_year,current,current-2))
                end = int(st.number_input('Last download year',minimum_year,current,current-1))
                byte_order = '<'
                if product != 'rainfall':
                    byte_order = '<' if st.selectbox('Download binary byte order',['Little endian','Big endian'],key='download_byte_order')=='Little endian' else '>'
                download_key = (product,start,end,byte_order)
                if st.button('Download selected years',type='primary',disabled=start>end):
                    paths,failures = [],[]
                    progress = st.progress(0.)
                    for i,year in enumerate(range(start,end+1)):
                        try:
                            path = download_rainfall(year) if product=='rainfall' else download_temperature(year,product,byte_order=byte_order)
                            paths.append(str(path))
                        except Exception as exc:
                            failures.append(f'{year}: {exc}')
                        progress.progress((i+1)/(end-start+1))
                    st.session_state['download_batch'] = (download_key,paths,failures)
            batch = st.session_state.get('download_batch')
            if not batch or batch[0]!=download_key:
                st.info('Choose download years and click Download selected years. You can also upload files already saved from IMD.')
                return
            _,paths,failures = batch
            if failures:
                st.warning('Some years could not be downloaded. Results include successful files only.')
                with st.expander('Download details'):
                    st.write('\n\n'.join(failures))
            if not paths:
                st.error('No valid datasets downloaded. Upload local NetCDF files to continue.')
                return
            data = load_downloads(tuple(paths),tuple(bounds),product,byte_order)
            source_id = repr((paths,product,byte_order))

        # Reset date widgets only when the source's available dates actually change.
        available = sorted(set(data.time.dt.year.values.tolist()))
        if not available:
            raise ValueError('No dated observations loaded.')
        year_token = repr((source_id,available))
        if st.session_state.get('year_token') != year_token:
            st.session_state.pop('years',None)
            st.session_state['year_token'] = year_token
        with st.sidebar:
            st.divider()
            st.subheader('Analysis period')
            if len(available)>1:
                start_year,end_year = st.select_slider('Years',options=available,value=(available[0],available[-1]),key='years')
            else:
                start_year=end_year=available[0]
                st.caption(f'Available year: {start_year}')
            basis = st.selectbox('Annual grouping',['Calendar year','June–May hydrological year'],key='year_basis')
            window = st.selectbox('Rolling mean (days)',[7,14,30],key='rolling')
        selected = data.where((data.time.dt.year>=start_year)&(data.time.dt.year<=end_year),drop=True)
        analysis_token=repr((source_id,start_year,end_year,tuple(bounds),basis,geometry.wkb_hex if geometry is not None else None))
        cached=st.session_state.get('last_analysis')
        if cached and cached[0]==analysis_token:
            result=cached[1]
            points=result['points']
        else:
            with st.spinner('Calculating regional statistics…'):
                points = select_region(selected,bounds,geometry)
                result = summarize(points,product,hydro=basis!='Calendar year')
            st.session_state['last_analysis']=(analysis_token,result)
        st.session_state['analysis'] = result
    except Exception as exc:
        st.error(f'Data could not be analyzed: {exc}')
        st.caption('Check the product, variable name, units, region, dates and grid consistency, then adjust the sidebar settings.')
        return

    daily,annual = result['daily'],result['annual']
    finite = daily.value.dropna()
    dates = pd.DatetimeIndex(points.time.values)
    full_days = (pd.Timestamp(end_year+1,1,1)-pd.Timestamp(start_year,1,1)).days
    coverage = float(points.count().item())/(full_days*points.sizes['point'])
    st.subheader(f'{meta["label"]} · {region_name}')
    st.caption(f'{dates.min():%d %b %Y} – {dates.max():%d %b %Y}  ·  {points.sizes["point"]:,} grid cells  ·  {basis}  ·  {meta["unit"]}')
    a,b,c,d = st.columns(4)
    a.metric('Mean daily rainfall' if product=='rainfall' else 'Mean daily temperature',f'{finite.mean():,.2f} {meta["unit"]}' if len(finite) else 'No data')
    b.metric('Peak regional daily value',f'{finite.max():,.2f} {meta["unit"]}' if len(finite) else 'No data')
    c.metric('Observation coverage',f'{coverage:.1%}',help='Valid grid-days divided by all expected grid-days in the selected calendar years.')
    d.metric('Complete annual periods',f'{annual.complete.sum()} / {len(annual)}',help='Every selected cell must have every expected day to count as complete.')
    if not annual.complete.all():
        st.warning('Partial annual periods are shown with a pattern. Rainfall totals are observed totals, not estimates for missing days. Trend tests exclude incomplete periods.')
    if len(available) != available[-1]-available[0]+1:
        st.warning('The uploaded files omit one or more calendar years; missing years are not inferred.')
    if not len(finite):
        st.warning('All selected observations are missing. Expand the region or inspect the input values.')

    overview,seasonal,spatial,trends,exports = st.tabs(['Overview','Seasons & months','Spatial explorer','Trends','Data & exports'])
    with overview:
        plot(daily_chart(result,product,window),'daily-chart')
        plot(annual_chart(result,product),'annual-chart')
        st.caption('Regional values use cosine-latitude area weights. Temporal totals/means are calculated per grid cell before regional averaging. Daily rolling means require a full window.')
    with seasonal:
        plot(monthly_heatmap(result,product),'monthly-chart')
        plot(seasonal_chart(result,product),'seasonal-chart')
        st.caption('Winter: Jan–Feb · Pre-monsoon: Mar–May · Monsoon: Jun–Sep · Post-monsoon: Oct–Dec. Seasons and months use calendar years regardless of annual grouping. Hover to inspect coverage.')
    with spatial:
        periods = result['annual'].period.tolist()
        map_token = repr((source_id,periods,basis))
        if st.session_state.get('map_token') != map_token:
            st.session_state.pop('map_period',None)
            st.session_state['map_token'] = map_token
        period = st.selectbox('Annual period',periods,key='map_period')
        if result['hydro']:
            st.caption(f'June {period} – May {int(period)+1}; only selected input dates are included.')
        left,middle,right=st.columns(3)
        mode=left.selectbox('Map style',['IDW surface','Grid centers'],key='map_style')
        power=middle.select_slider('IDW power',options=[1.,1.5,2.,3.,4.],value=2.,key='idw_power',disabled=mode!='IDW surface')
        resolution=right.selectbox('Surface resolution',[80,120,200],index=1,key='idw_resolution',disabled=mode!='IDW surface')
        show_points=st.checkbox('Overlay original grid centers',value=False,key='idw_points',disabled=mode!='IDW surface')
        plot(spatial_chart(result,product,period,geometry,bounds=tuple(bounds),mode=mode,power=power,resolution=resolution,show_points=show_points),'spatial-chart')
        st.caption('IDW estimates use up to 12 nearest valid grid centers and great-circle distances. The surface is clipped to the region, including polygon holes. Interpolation can extend beyond sample coverage inside the region and does not add observations. Statistics and exports use original grid values. Colors share one scale across selected years; partial data may vary between cells.')
    with trends:
        st.subheader('Annual trend evidence')
        table = trend_table(annual)
        st.dataframe(table,width="stretch",hide_index=True)
        st.caption('Mann–Kendall test (α = 0.05), with Theil–Sen slope per actual elapsed year. Only complete annual periods are used; at least 3 are required. The test does not correct for autocorrelation; short records provide limited evidence.')
        complete = annual[annual.complete & annual.value.notna()]
        if len(complete)>=3:
            import plotly.express as px
            from imd_charts import polish
            fig = px.scatter(complete,x='year',y='value',labels={'value':meta['unit'],'year':'Year'})
            slope = table.slope_per_year.iloc[0]
            intercept = np.median(complete.value-slope*complete.year)
            fig.add_scatter(x=complete.year,y=intercept+slope*complete.year,mode='lines',name='Theil–Sen',line=dict(color=meta['color']))
            plot(polish(fig,'Complete annual periods & robust trend'),'trend-chart')
    with exports:
        st.subheader('Inspect & download')
        frequency = st.selectbox('Table',['daily','monthly','seasonal','annual'],format_func=str.title)
        frame = result[frequency]
        st.dataframe(frame,width="stretch",hide_index=True)
        prefix = f'{product}_{start_year}_{end_year}'
        csv_download('Download displayed table (CSV)',frame,f'{prefix}_{frequency}.csv')
        left,right = st.columns(2)
        with left:
            if st.button('Prepare selected grid data (NetCDF)'):
                # Export a rectilinear grid, preserving excluded polygon cells as NaN.
                out = points.unstack('point')
                payload = out.to_dataset(name=product).to_netcdf(engine='scipy')
                st.session_state['grid_export'] = (repr((source_id,start_year,end_year,bounds,geometry.wkb_hex if geometry is not None else None)),bytes(payload))
            export_token = repr((source_id,start_year,end_year,bounds,geometry.wkb_hex if geometry is not None else None))
            ready = st.session_state.get('grid_export')
            if ready and ready[0]==export_token:
                st.download_button('Download selected grids',ready[1],f'{prefix}.nc','application/x-netcdf')
        with right:
            if st.button('Prepare annual grid points (GeoJSON)'):
                import geopandas as gpd
                grid = result['grids']['annual']
                frame = pd.DataFrame({str(p):grid.sel(period=p).values for p in grid.period.values})
                gdf = gpd.GeoDataFrame(frame,geometry=gpd.points_from_xy(points.longitude.values,points.latitude.values),crs=4326)
                token = repr((source_id,start_year,end_year,bounds,basis,geometry.wkb_hex if geometry is not None else None))
                st.session_state['geo_export']=(token,gdf.to_json(na='null'))
            token = repr((source_id,start_year,end_year,bounds,basis,geometry.wkb_hex if geometry is not None else None))
            geo = st.session_state.get('geo_export')
            if geo and geo[0]==token:
                st.download_button('Download annual grid points',geo[1],f'{prefix}_annual.geojson','application/geo+json')
        st.caption('CSV includes coverage and completeness. NetCDF preserves missing values and the selected spatial mask. GeoJSON avoids shapefile field-name and column-count limits.')
        with st.expander('Dataset & calculation notes'):
            st.write({'product':product,'source':'synthetic demonstration' if source.startswith('Demo') else source,'variable':data.attrs.get('source_variable',data.name),'units':meta['unit'],'dimensions':dict(data.sizes),'annual_grouping':basis,'calendar_year_selection':[start_year,end_year]})
            st.write('No missing values are filled with zero. Annual rainfall is the sum of valid daily amounts; temperatures are the mean of valid daily values. Coverage is valid grid-days / expected grid-days. Complete requires 100% coverage at every selected grid center. Hydrological years are labeled by their June start year. Data sources must have Gregorian daily time coordinates and identical rectilinear grids.')


def run_app():
    dashboard,guide=st.tabs(['Dashboard','How to use this app'])
    with dashboard:
        main()
    with guide:
        st.markdown((Path(__file__).parent/'docs'/'HOW_TO_USE.md').read_text(encoding='utf-8'))
    st.divider()
    st.markdown('**Data credit:** India Meteorological Department (IMD), Ministry of Earth Sciences, Government of India, for the gridded rainfall and temperature datasets.')
    st.markdown('[Rainfall · 0.25° NetCDF](https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html) · [Maximum temperature · 1° binary](https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html) · [Minimum temperature · 1° binary](https://www.imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html)')
    with st.expander('Dataset citations (papers and presentations)'):
        st.markdown((Path(__file__).parent/'docs'/'CITATIONS.md').read_text(encoding='utf-8'))
    st.markdown('Webapp Prepared by Dr Sachchidanand Singh, Assistant Professor, IIT Mandi')


if __name__ == '__main__':
    run_app()
