import numpy as np
import plotly.graph_objects as go
from portfolio.research import categories_for
from portfolio.validation import CATEGORIES, COLOURS


def frontier_chart(run, point, quantiles=None):
    f = run.frontier
    x, y = f.volatilities * np.sqrt(12) * 100, f.returns * 1200
    fig = go.Figure()
    if quantiles is not None:
        fig.add_trace(go.Scatter(x=x, y=quantiles[:, 2] * 100, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=x, y=quantiles[:, 0] * 100, mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(100,110,120,.15)', name='68% horizon-average range', customdata=quantiles[:, [0, 2]] * 100,
                                hovertemplate='68% range: %{customdata[0]:.1f}% to %{customdata[1]:.1f}%<extra></extra>'))
    fig.add_trace(go.Scatter(x=x, y=y, mode='lines', name='Solved frontier', customdata=np.arange(len(x)), line=dict(color='#198577'), hovertemplate='Position %{customdata}/100<br>Annual volatility %{x:.2f}%<br>Arithmetic expected return %{y:.2f}%<extra></extra>'))
    fig.add_trace(go.Scatter(x=[x[point]], y=[y[point]], mode='markers', marker=dict(size=13, color='#182b35'), name='Selected portfolio'))
    for symbol, (label, ref) in zip(['circle', 'diamond', 'square', 'triangle-up', 'star'], run.benchmarks.items()):
        if ref['available']:
            fig.add_trace(go.Scatter(x=[ref['volatility'] * np.sqrt(12) * 100], y=[ref['mean'] * 1200], mode='markers', marker=dict(size=11, symbol=symbol), name=label + ' (fixed reference)'))
    fig.update_layout(height=355, margin=dict(l=5, r=5, t=15, b=5), xaxis_title='Annual volatility (%)', yaxis_title='Expected return, net (% p.a.)',
                      legend=dict(itemclick=False, itemdoubleclick=False, orientation='h'), template='plotly_white')
    return fig


def composition_chart(run):
    categories = np.array([categories_for(run, w).to_numpy() for w in run.frontier.weights])
    fig = go.Figure()
    for j, (label, colour) in enumerate(zip(CATEGORIES, COLOURS)):
        fig.add_trace(go.Scatter(x=np.arange(len(categories)), y=categories[:, j] * 100, stackgroup='allocation', mode='lines', line=dict(width=0, color=colour), name=label))
    fig.update_layout(height=115, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, yaxis=dict(range=[0, 100], title='%'), xaxis_title='Solved frontier position', template='plotly_white')
    return fig


def allocation_bar(weights):
    fig = go.Figure()
    for label, value, colour in zip(CATEGORIES, weights, COLOURS):
        fig.add_trace(go.Bar(y=['Allocation'], x=[value * 100], orientation='h', name=label, marker_color=colour, hovertemplate=label + ': %{x:.2f}%<extra></extra>'))
    fig.update_layout(barmode='stack', showlegend=False, height=65, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(range=[0, 100], visible=False), yaxis=dict(visible=False))
    return fig
