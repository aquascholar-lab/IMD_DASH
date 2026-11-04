"""Interactive figures; map colors represent measured grid aggregates, without IDW."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from imd_data import PRODUCTS, SEASONS


def polish(fig, title, height=380):
    fig.update_layout(title=dict(text=title,font=dict(size=17)),template='plotly_white',height=height,
                      margin=dict(l=20,r=20,t=60,b=30),font=dict(family='Arial, sans-serif',color='#23394c'),
                      paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
                      hoverlabel=dict(bgcolor='#142c40',font_color='white'),legend_title_text='')
    fig.update_xaxes(showgrid=False,zeroline=False)
    fig.update_yaxes(gridcolor='#e5ecef',zeroline=False)
    return fig


def daily_chart(result, product, window=7):
    df = result['daily']
    meta = PRODUCTS[product]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.date,y=df.value,name='Daily',mode='lines',line=dict(color=meta['color'],width=1),opacity=.4,
                             connectgaps=False,hovertemplate='%{x|%d %b %Y}<br>%{y:.2f} '+meta['unit']+'<extra>Daily</extra>'))
    smooth = df.value.rolling(window,min_periods=window).mean()
    fig.add_trace(go.Scatter(x=df.date,y=smooth,name=f'{window}-day mean',line=dict(color=meta['color'],width=2.5),connectgaps=False))
    fig.update_yaxes(title=meta['unit'])
    fig.update_layout(hovermode='x unified',legend=dict(orientation='h',y=1.12))
    return polish(fig,'Daily observations & rolling mean',420)


def annual_chart(result,product):
    df = result['annual'].copy()
    df['Status'] = np.where(df.complete,'Complete','Partial')
    fig = px.bar(df,x='year',y='value',color='Status',pattern_shape='Status',
                 color_discrete_map={'Complete':PRODUCTS[product]['color'],'Partial':'#aebfc8'},
                 hover_data={'coverage':':.1%','days':True,'expected_days':True,'year':True},
                 labels={'value':PRODUCTS[product]['unit'],'year':'Start year' if result['hydro'] else 'Year'})
    fig.update_xaxes(dtick=1 if len(df)<=20 else None,tickformat='d')
    return polish(fig,'Annual totals' if product=='rainfall' else 'Annual mean temperature')


def monthly_heatmap(result,product):
    df = result['monthly']
    pivot = df.pivot(index='year',columns='month',values='value').reindex(columns=range(1,13))
    coverage = df.pivot(index='year',columns='month',values='coverage').reindex(index=pivot.index,columns=pivot.columns)
    fig = go.Figure(go.Heatmap(z=pivot.values,x=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
                              y=[str(y) for y in pivot.index],colorscale=PRODUCTS[product]['scale'],
                              customdata=coverage.values,colorbar=dict(title=PRODUCTS[product]['unit']),
                              hovertemplate='%{x} %{y}<br>%{z:.2f} '+PRODUCTS[product]['unit']+'<br>Coverage %{customdata:.1%}<extra></extra>',
                              hoverongaps=False))
    fig.update_yaxes(type='category')
    return polish(fig,'Monthly rainfall totals' if product=='rainfall' else 'Monthly mean temperature',max(310,min(700,50*len(pivot)+140)))


def seasonal_chart(result,product):
    df = result['seasonal'].copy()
    full_index = pd.MultiIndex.from_product([sorted(df.year.unique()), SEASONS],names=['year','season'])
    df = df.set_index(['year','season']).reindex(full_index).reset_index()
    df['Year'] = df.year.astype(str)
    fig = px.line(df,x='season',y='value',color='Year',markers=True,category_orders={'season':SEASONS},
                  hover_data={'coverage':':.1%'},labels={'value':PRODUCTS[product]['unit'],'season':''},
                  color_discrete_sequence=px.colors.qualitative.Safe)
    fig.update_traces(connectgaps=False)
    return polish(fig,'Compare the four IMD seasons')


def spatial_chart(result,product,period,geometry=None):
    grid = result['grids']['annual'].sel(period=period)
    df = pd.DataFrame({'Longitude':grid.longitude.values,'Latitude':grid.latitude.values,'Value':grid.values})
    fig = px.scatter(df,x='Longitude',y='Latitude',color='Value',color_continuous_scale=PRODUCTS[product]['scale'],
                     labels={'Value':PRODUCTS[product]['unit']},hover_data={'Value':':.2f'})
    fig.update_traces(marker=dict(size=12,symbol='square',line=dict(width=.5,color='white')))
    if geometry is not None:
        polygons = list(geometry.geoms) if geometry.geom_type=='MultiPolygon' else [geometry]
        for polygon in polygons:
            for ring in [polygon.exterior,*polygon.interiors]:
                x,y = ring.xy
                fig.add_trace(go.Scatter(x=list(x),y=list(y),mode='lines',line=dict(color='#23394c',width=1.5),showlegend=False,hoverinfo='skip'))
    fig.update_yaxes(scaleanchor='x',scaleratio=1)
    return polish(fig,f'{period} · actual grid values',530)
