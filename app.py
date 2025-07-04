import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv
import os
import plotly.express as px

load_dotenv(".env.local")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --------- Fetching Helpers ----------
def get_latest_trade_date():
    res = supabase.table("psx_stocks").select("trade_date").order("trade_date", desc=True).limit(1).execute()
    return res.data[0]["trade_date"] if res.data else None

def get_data_for_date(date):
    res = supabase.table("psx_stocks").select("*").eq("trade_date", date).execute()
    df = pd.DataFrame(res.data)
    return preprocess_df(df)

def get_data_in_range(start, end):
    res = supabase.table("psx_stocks").select("*").gte("trade_date", start).lte("trade_date", end).execute()
    df = pd.DataFrame(res.data)
    return preprocess_df(df)

def preprocess_df(df):
    if df.empty: return df
    df = df.rename(columns={
        "symbol": "SYMBOL", "ldcp": "LDCP", "open_price": "OPEN", "high": "HIGH",
        "low": "LOW", "close_price": "CLOSE", "volume": "VOLUME"
    })
    df["SYMBOL"] = df["SYMBOL"].str.upper()
    return df

# --------- Analysis Functions ----------
def get_counts(df, col):
    return {
        "Breakout": df[df[col].str.contains("▲▲", na=False)].shape[0],
        "Breakdown": df[df[col].str.contains("▼▼", na=False)].shape[0],
        "Within Range": df[df[col].str.contains("–", na=False)].shape[0],
    }

def create_pie(counts, title):
    df = pd.DataFrame({"Status": counts.keys(), "Count": counts.values()})
    return px.pie(df, values="Count", names="Status", title=title)

def is_weekend(date):
    return date.weekday() >= 5

def is_valid_symbol(symbol):
    return not any(m in symbol for m in ['-JAN','-FEB','-MAR','-APR','-MAY','-JUN','-JUL','-AUG','-SEP','-OCT','-NOV','-DEC'])

def analyze(df_today, df_prev, df_week, df_month):
    results = []
    for _, row in df_today.iterrows():
        symbol = row["SYMBOL"]
        if not is_valid_symbol(symbol): continue

        close, high, low, ldcp, volume = map(float, [row["CLOSE"], row["HIGH"], row["LOW"], row["LDCP"], row["VOLUME"]])
        daily = weekly = monthly = "N/A"

        prev = df_prev[df_prev["SYMBOL"] == symbol]
        if not prev.empty:
            ph, pl = float(prev["HIGH"].iloc[0]), float(prev["LOW"].iloc[0])
            daily = "▲▲ Daily Breakout" if close > ph else "▼▼ Daily Breakdown" if close < pl else "– Daily Within Range"

        week = df_week[df_week["SYMBOL"] == symbol]
        if not week.empty:
            wh, wl = week["HIGH"].astype(float).max(), week["LOW"].astype(float).min()
            weekly = "▲▲ Weekly Breakout" if close > wh else "▼▼ Weekly Breakdown" if close < wl else "– Weekly Within Range"

        month = df_month[df_month["SYMBOL"] == symbol]
        if not month.empty:
            mh, ml = month["HIGH"].astype(float).max(), month["LOW"].astype(float).min()
            monthly = "▲▲ Monthly Breakout" if close > mh else "▼▼ Monthly Breakdown" if close < ml else "– Monthly Within Range"

        results.append({
            "SYMBOL": symbol, "CLOSE": close, "LDCP": ldcp, "HIGH": high, "LOW": low,
            "VOLUME": int(volume), "DAILY_STATUS": daily, "WEEKLY_STATUS": weekly, "MONTHLY_STATUS": monthly
        })
    return pd.DataFrame(results)

# --------- UI Layout ----------
with gr.Blocks(css="""
    .styled-table td, .styled-table th { text-align:center; padding:8px; }
    .styled-table th { background-color:#4F81BD; color:white; }
    .styled-table tr:nth-child(even) { background-color:#f2f2f2; }
    .styled-table { border-collapse:collapse; width:100%; border:1px solid #ddd; font-family:Arial,sans-serif; font-size:14px; }
""") as app:
    gr.Markdown("## 📈 PSX Breakout Scanner")
    run_btn = gr.Button("Run Analysis")
    table_html = gr.HTML()
    daily_chart = gr.Plot()
    weekly_chart = gr.Plot()
    monthly_chart = gr.Plot()

    def run():
        latest_date = get_latest_trade_date()
        if not latest_date: return "❌ No data found", None, None, None

        today = datetime.strptime(latest_date, "%Y-%m-%d")
        df_today = get_data_for_date(latest_date)

        df_prev = pd.DataFrame()
        for i in range(1, 6):
            prev_day = today - timedelta(days=i)
            if not is_weekend(prev_day):
                df_prev = get_data_for_date(prev_day.strftime("%Y-%m-%d"))
                if not df_prev.empty: break

        prev_mon = today - timedelta(days=today.weekday() + 7)
        prev_fri = prev_mon + timedelta(days=4)
        df_week = get_data_in_range(prev_mon.strftime("%Y-%m-%d"), prev_fri.strftime("%Y-%m-%d"))

        first_prev_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_prev_month = today.replace(day=1) - timedelta(days=1)
        df_month = get_data_in_range(first_prev_month.strftime("%Y-%m-%d"), last_prev_month.strftime("%Y-%m-%d"))

        result_df = analyze(df_today, df_prev, df_week, df_month)
        html = "<table class='styled-table'><thead><tr>" + "".join(f"<th>{col}</th>" for col in result_df.columns) + "</tr></thead><tbody>"
        for _, row in result_df.iterrows():
            html += "<tr>" + "".join(f"<td>{val}</td>" for val in row.values) + "</tr>"
        html += "</tbody></table>"

        return (
            html,
            create_pie(get_counts(result_df, "DAILY_STATUS"), "Daily"),
            create_pie(get_counts(result_df, "WEEKLY_STATUS"), "Weekly"),
            create_pie(get_counts(result_df, "MONTHLY_STATUS"), "Monthly"),
        )

    run_btn.click(fn=run, outputs=[table_html, daily_chart, weekly_chart, monthly_chart])

if __name__ == "__main__":
    app.launch()
