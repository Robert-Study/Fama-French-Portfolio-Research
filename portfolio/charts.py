import numpy as np
import plotly.graph_objects as go


TEAL = "#19675A"
INK = "#182B35"


def frontier_chart(run, point):
    fig = go.Figure()
    x = run.frontier.volatilities * np.sqrt(12)
    y = run.frontier.returns * 12
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Solved frontier",
                             line=dict(color=TEAL, width=2), marker=dict(size=3),
                             hovertemplate="Volatility %{x:.2%}<br>Return %{y:.2%}<extra></extra>"))
    etfs = run.etfs.loc[run.funds.index]
    fig.add_trace(go.Scatter(x=etfs["Annualised monthly volatility"], y=etfs["Annualised arithmetic return"],
                             text=etfs.index, mode="markers", name="Individual ETFs", marker=dict(color="#B3BCC2", size=7),
                             hovertemplate="%{text}<br>Volatility %{x:.2%}<br>Return %{y:.2%}<extra></extra>"))
    ref = run.reference
    fig.add_trace(go.Scatter(x=[ref["volatility"] * np.sqrt(12)], y=[ref["return"] * 12], name=ref["ETF_ID"] + " reference",
                             mode="markers", marker=dict(color="#C08733", size=11, symbol="diamond"),
                             hovertemplate="Volatility %{x:.2%}<br>Return %{y:.2%}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[x[point]], y=[y[point]], mode="markers", name="Selected portfolio",
                             marker=dict(color=INK, size=14, line=dict(color="white", width=2)),
                             hovertemplate="Volatility %{x:.2%}<br>Return %{y:.2%}<extra></extra>"))
    fig.update_layout(height=390, margin=dict(l=10, r=15, t=20, b=20), template="plotly_white",
                      legend=dict(orientation="h", y=1.13), xaxis_title="Annualised monthly volatility",
                      yaxis_title="Annualised arithmetic return", font=dict(color=INK))
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    return fig


def wealth_chart(frame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame.Year, y=frame.P20, name="P20", line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=frame.Year, y=frame.P80, name="P20–P80 (60% band)", fill="tonexty",
                             fillcolor="rgba(25,103,90,0.12)", line=dict(width=0)))
    fig.add_trace(go.Scatter(x=frame.Year, y=frame.Median, name="Approximate median", line=dict(color=TEAL)))
    fig.add_trace(go.Scatter(x=frame.Year, y=frame["Expected wealth"], name="Expected wealth",
                             line=dict(color=INK, dash="dot")))
    fig.update_layout(height=330, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h"), xaxis_title="Years", yaxis_title="Nominal GBP")
    fig.update_yaxes(tickprefix="£", tickformat=",.0f")
    return fig
