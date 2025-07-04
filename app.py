import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv
import os
import plotly.express as px

# Load Supabase credentials
load_dotenv(".env.local")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Table name and column mappings
TABLE_NAME = "psx_stocks"
COLUMN_MAP = {
    "symbol": "SYMBOL",
    "ldcp": "LDCP",
    "open_price": "OPEN",
    "high": "HIGH",
    "low": "LOW",
    "close_price": "CLOSE",
    "volume": "VOLUME"
}

def get_latest_date():
    res = supabase.table(TABLE_NAME).select("trade_date").order("trade_date", desc=True).limit(1).execute()
    if res.data:
        return res.data[0]["trade_date"]
    return None

def get_data_by_date(date_str):
    res = supabase.table(TABLE_NAME).select("*").eq("trade_date", date_str).execute()
    df = pd.DataFrame(res.data)
    return df.rename(columns=COLUMN_MAP)

def get_data_between(start_date, end_date):
    res = supabase.table(TABLE_NAME).select("*").gte("trade_date", start_date).lte("trade_date", end_date).execute()
    df = pd.DataFrame(res.data)
    return df.rename(columns=COLUMN_MAP)

def analyze_breakouts(df_today, df_prev, df_week, df_month):
    results = []
    for _, row in df_today.iterrows():
        symbol = row["SYMBOL"]
        close = float(row["CLOSE"])
        high = float(row["HIGH"])
        low = float(row["LOW"])
        ldcp = float(row["LDCP"])
        daily = weekly = monthly = "N/A"

        # Daily
        prev = df_prev[df_prev["SYMBOL"] == symbol]
        if not prev.empty:
            ph = float(prev["HIGH"].iloc[0])
            pl = float(prev["LOW"].iloc[0])
            if close > ph:
                daily = "▲▲ Daily Breakout"
            elif close < pl:
                daily = "▼▼ Daily Breakdown"
            else:
                daily = "– Daily Within Range"

        # Weekly
        week = df_week[df_week["SYMBOL"] == symbol]
        if not week.empty:
            wh = week["HIGH"].astype(float).max()
            wl = week["LOW"].astype(float).min()
            if close > wh:
                weekly = "▲▲ Weekly Breakout"
            elif close < wl:
                weekly = "▼▼ Weekly Breakdown"
            else:
                weekly = "– Weekly Within Range"

        # Monthly
        month = df_month[df_month["SYMBOL"] == symbol]
        if not month.empty:
            mh = month["HIGH"].astype(float).max()
            ml = month["LOW"].astype(float).min()
            if close > mh:
                monthly = "▲▲ Monthly Breakout"
            elif close < ml:
                monthly = "▼▼ Monthly Breakdown"
            else:
                monthly = "– Monthly Within Range"

        results.append({
            "SYMBOL": symbol,
            "CLOSE": close,
            "LDCP": ldcp,
            "HIGH": high,
            "LOW": low,
            "VOLUME": row["VOLUME"],
            "DAILY_STATUS": daily,
            "WEEKLY_STATUS": weekly,
            "MONTHLY_STATUS": monthly
        })

    return pd.DataFrame(results)

def get_counts(df, col):
    return {
        "Breakout": df[df[col].str.contains("▲▲", na=False)].shape[0],
        "Breakdown": df[df[col].str.contains("▼▼", na=False)].shape[0],
        "Within Range": df[df[col].str.contains("–", na=False)].shape[0],
    }

def create_pie(counts, title):
    df = pd.DataFrame({"Status": counts.keys(), "Count": counts.values()})
    return px.pie(df, values="Count", names="Status", title=title)

with gr.Blocks(css="""
    .styled-table td, .styled-table th {
        text-align: center;
        padding: 8px;
    }
    .styled-table th {
        background-color: #4F81BD;
        color: white;
    }
    .styled-table tr:nth-child(even) {
        background-color: #f2f2f2;
    }
    .styled-table {
        border-collapse: collapse;
        width: 100%;
        border: 1px solid #ddd;
        font-family: Arial, sans-serif;
        font-size: 14px;
    }
""") as app:
    gr.Markdown("## 📈 PSX Breakout Scanner (Supabase Powered)")
    run_btn = gr.Button("Run Analysis")
    table_html = gr.HTML()
    daily_chart = gr.Plot()
    weekly_chart = gr.Plot()
    monthly_chart = gr.Plot()

    def run():
        latest = get_latest_date()
        if not latest:
            return "❌ No data found", None, None, None

        today = datetime.strptime(latest, "%Y-%m-%d")
        df_today = get_data_by_date(latest)

        # Previous day
        df_prev = pd.DataFrame()
        for i in range(1, 6):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            df_prev = get_data_by_date(d)
            if not df_prev.empty:
                break

        # Weekly range: last Mon–Fri before this week
        monday = today - timedelta(days=today.weekday() + 7)
        friday = monday + timedelta(days=4)
        df_week = get_data_between(monday.strftime("%Y-%m-%d"), friday.strftime("%Y-%m-%d"))

        # Monthly: previous month range
        first_prev = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_prev = today.replace(day=1) - timedelta(days=1)
        df_month = get_data_between(first_prev.strftime("%Y-%m-%d"), last_prev.strftime("%Y-%m-%d"))

        result_df = analyze_breakouts(df_today, df_prev, df_week, df_month)

        html = "<table class='styled-table'>"
        html += "<thead><tr>" + "".join(f"<th>{col}</th>" for col in result_df.columns) + "</tr></thead><tbody>"
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
