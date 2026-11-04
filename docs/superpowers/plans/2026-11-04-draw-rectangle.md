# Rectangle study-region selection

User requests an option to draw a rectangle on a map. Keep existing bounding-box
and uploaded-polygon modes; add Draw rectangle as a third mode. Use an interactive
Leaflet map via folium/streamlit-folium with rectangle-only drawing plus edit/delete.
Map appears in main content for usable drawing space. The latest drawn rectangle
sets west/south/east/north; an explicit Apply button commits selection so panning
and edits do not trigger expensive recalculations. Clear discards selection and
results. An unapplied draft never changes analysis. Store the applied rectangle
in session state and reuse it across product, year, chart and source changes.

- [x] Test rectangle coordinate parsing, reversed drawing direction, invalid/rotated
  shapes, antimeridian/coordinate limits, and deletion/empty drafts.
- [x] Implement reusable rectangle component and draft/apply/clear controls.
- [x] Add region mode; validate applied bounds through existing data/IDW/export flow.
- [x] Run full pytest, browser draw/apply/edit/clear/rerun checks, review and push.

A geographic basemap requires the browser to reach the tile provider. Drawing
coordinates remains functional if tiles fail; the application retains manual
bounds as an alternative. Download and IDW logic remain unchanged.
