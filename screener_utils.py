import pandas as pd
import plotly.graph_objects as go

def open_gt_prev_close(df: pd.DataFrame, days: int = 1):
    df = df.sort_values("Date")
    df["PrevClose"] = df["Close"].shift(1)
    return df[df["Open"] > df["PrevClose"]].tail(days)

def volume_increasing(df: pd.DataFrame, window: int = 3):
    df = df.sort_values("Date")
    df["VolDelta"] = df["Volume"].diff()
    return (df["VolDelta"].tail(window) > 0).all()

def plot_price_volume(df: pd.DataFrame, title: str = "Stock Price & Volume"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode="lines", name="Close Price"))
    fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="Volume", yaxis="y2", marker_color="lightblue"))

    fig.update_layout(
        title=title,
        xaxis=dict(title="Date"),
        yaxis=dict(title="Price"),
        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
        legend=dict(x=0, y=1.1, orientation="h"),
        height=400,
    )
    return fig

# Define preset screener logic (can be extended)
screener_templates = {
    "Open > Previous Close (5 days)": lambda df: open_gt_prev_close(df, days=5),
    "Volume Increasing (3 days)": lambda df: df if volume_increasing(df, window=3) else pd.DataFrame(),
}
