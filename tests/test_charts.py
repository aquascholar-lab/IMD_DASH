import pandas as pd
from imd_charts import seasonal_chart


def test_seasonal_lines_preserve_absent_seasons():
    frame = pd.DataFrame({'year':[2024,2024],'season':['Winter','Monsoon'],'value':[10,20],'coverage':[1.,1.]})
    fig = seasonal_chart({'seasonal':frame},'rainfall')
    trace = fig.data[0]
    assert len(trace.x) == 4
    assert pd.isna(trace.y[1])
    assert not trace.connectgaps
