import pandas as pd
from imd_charts import seasonal_chart


def test_seasonal_lines_preserve_absent_seasons():
    frame = pd.DataFrame({'year':[2024,2024],'season':['Winter','Monsoon'],'value':[10,20],'coverage':[1.,1.]})
    fig = seasonal_chart({'seasonal':frame},'rainfall')
    trace = fig.data[0]
    assert len(trace.x) == 4
    assert pd.isna(trace.y[1])
    assert not trace.connectgaps


def test_spatial_chart_defaults_to_idw_surface():
    from imd_data import demo_dataset,select_region,summarize
    from imd_charts import spatial_chart
    a=demo_dataset('tmax').isel(time=slice(0,3))
    r=summarize(select_region(a,(74.5,8.5,77.5,12.5)),'tmax')
    fig=spatial_chart(r,'tmax','2020',bounds=(74.5,8.5,77.5,12.5))
    assert fig.data[0].type=='heatmap'
    assert len(fig.data[0].z)==120
    assert 'IDW' in fig.layout.title.text
