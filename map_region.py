"""Draw/apply a rectangular study area without changing analysis on map panning."""
import numpy as np
import folium
from folium.plugins import Draw
from branca.element import MacroElement, Template
from shapely.geometry import Polygon
import streamlit as st
from streamlit_folium import st_folium


def rectangle_bounds(feature):
    """Validate a Leaflet rectangle GeoJSON and return west, south, east, north."""
    if feature is None:
        return None
    try:
        geometry=feature['geometry']
        if geometry['type']!='Polygon' or len(geometry['coordinates'])!=1:
            raise ValueError('Expected one rectangle.')
        ring=np.asarray(geometry['coordinates'][0],dtype=float)
        if ring.shape!=(5,2) or not np.isfinite(ring).all() or not np.array_equal(ring[0],ring[-1]):
            raise ValueError('Expected a closed rectangle with four corners.')
        west,south=ring.min(axis=0)
        east,north=ring.max(axis=0)
        if not (-180<=west<east<=180 and -90<=south<north<=90) or east-west>180:
            raise ValueError('Rectangle must use valid longitude/latitude and cannot cross the antimeridian.')
        corners={(west,south),(west,north),(east,south),(east,north)}
        if set(map(tuple,ring[:-1]))!=corners or not Polygon(ring).is_valid:
            raise ValueError('Use the rectangle tool to draw an axis-aligned rectangle.')
        return tuple(float(v) for v in (west,south,east,north))
    except (KeyError,TypeError,IndexError) as exc:
        raise ValueError('Invalid rectangle geometry returned by the map.') from exc


class _SingleRectangle(MacroElement):
    """Keep only the latest rectangle in Leaflet's editable feature group."""
    _template=Template('''{% macro script(this, kwargs) %}
    {{this._parent.get_name()}}.on('draw:created', function(event) {
        {{this.group.get_name()}}.clearLayers();
        {{this.group.get_name()}}.addLayer(event.layer);
    });
    {% endmacro %}''')

    def __init__(self, group):
        super().__init__()
        self._name='SingleRectangle'
        self.group=group


def rectangle_selector():
    """Return applied bounds; drawing/editing is a draft until Apply is clicked."""
    st.subheader('Draw your study area')
    st.write('Choose the rectangle tool on the left of the map, then drag across your area. Click **Apply rectangle** to analyze it. To resize or move it later, use the edit tool, click Save on the map, then Apply rectangle.')
    applied=st.session_state.get('rectangle_applied')
    m=folium.Map(location=[21,79],zoom_start=4,tiles='OpenStreetMap',control_scale=True,
                 min_zoom=2,max_bounds=True)
    # Keep dependencies on one CDN; no Bootstrap/jQuery is required for this map.
    m.default_js=[('leaflet','https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js')]
    m.default_css=[('leaflet_css','https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css')]
    group=folium.FeatureGroup(name='Study rectangle').add_to(m)
    if applied:
        west,south,east,north=applied
        folium.Rectangle([[south,west],[north,east]],color='#007f86',weight=2,fill=True,fill_opacity=.15).add_to(group)
        m.fit_bounds([[south,west],[north,east]],padding=(25,25),max_zoom=9)
    draw=Draw(feature_group=group,show_geometry_on_click=False,
              draw_options={'rectangle':{'shapeOptions':{'color':'#007f86','weight':2,'fillOpacity':.15}},
                            'polygon':False,'polyline':False,'circle':False,'circlemarker':False,'marker':False},
              edit_options={'edit':True,'remove':True})
    draw.default_js=[('leaflet_draw_js','https://cdn.jsdelivr.net/npm/leaflet-draw@1.0.4/dist/leaflet.draw.js')]
    draw.default_css=[('leaflet_draw_css','https://cdn.jsdelivr.net/npm/leaflet-draw@1.0.4/dist/leaflet.draw.css')]
    draw.add_to(m)
    _SingleRectangle(group).add_to(m)
    epoch=st.session_state.get('rectangle_epoch',0)
    output=st_folium(m,key=f'region_rectangle_{epoch}',height=440,use_container_width=True,
                     returned_objects=['all_drawings'],wrap_longitude=False)
    drawings=output.get('all_drawings') if output else None
    if drawings is not None:
        try:
            st.session_state['rectangle_draft']=rectangle_bounds(drawings[-1] if drawings else None)
        except ValueError as exc:
            st.session_state['rectangle_draft']=None
            st.error(str(exc))
    draft=st.session_state.get('rectangle_draft')
    pending=draft is not None and draft!=applied
    if pending:
        st.caption(f'Pending rectangle: west {draft[0]:.4f}°, south {draft[1]:.4f}°, east {draft[2]:.4f}°, north {draft[3]:.4f}°. Click Apply rectangle to use it.')
    left,right=st.columns(2)
    if left.button('Apply rectangle',type='primary',disabled=not pending,key='apply_rectangle'):
        st.session_state['rectangle_applied']=draft
        st.rerun()
    if right.button('Clear selection',disabled=applied is None and draft is None,key='clear_rectangle'):
        st.session_state.pop('rectangle_applied',None)
        st.session_state.pop('rectangle_draft',None)
        st.session_state['rectangle_epoch']=epoch+1
        st.rerun()
    if applied:
        st.caption(f'Applied region: west {applied[0]:.4f}°, south {applied[1]:.4f}°, east {applied[2]:.4f}°, north {applied[3]:.4f}°. Map edits take effect when you click Apply rectangle; Clear selection removes the applied region.')
    else:
        st.info('Draw a rectangle and click Apply rectangle to start analysis.')
    st.caption('Map tiles © OpenStreetMap contributors. Basemap tiles require internet access in your browser. Drawing coordinates are retained even if tiles are unavailable.')
    return applied
