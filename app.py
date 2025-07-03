import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv
import os
import plotly.express as px

# === Load Env ===
load_dotenv(".env.local")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# === Supabase Queries ===
def get_latest_trading_date():
    res = supabase.table("psx_data").select("date").order("date", desc=True).limit(1).execute()
    if res.data:
        return res.data[0]["date"]
    return None

def get_data_by_date(target_date: str):
    res = supabase.table("psx_data").select("*").eq("date", target_date).execute()
    df = pd.DataFrame(res.data)
    df.columns = [col.upper() for col in df.columns]
    return df

def get_data_between(start_date: str, end_date: str):
    res = supabase.table("psx_data").select("*").gte("date", start_date).lte("date", end_date).execute()
    df = pd.DataFrame(res.data)
    df.columns = [col.upper() for col in df.columns]
    return df

# === Helper Functions ===
def get_counts(df, col):
    return {
        "Breakout": df[df[col].str.contains("▲▲", na=False)].shape[0],
        "Breakdown": df[df[col].str.contains("▼▼", na=False)].shape[0],
        "Within Range": df[df[col].str.contains("–", na=False)].shape[0],
    }

def create_pie_chart(counts, title):
    df = pd.DataFrame({"Status": counts.keys(), "Count": counts.values()})
    return px.pie(df, values='Count', names='Status', title=title)

# === Core Analysis ===
def calculate_breakout(df_today, df_prev_day, df_week, df_month):
    results = []
    for _, row in df_today.iterrows():
        symbol = row["SYMBOL"]
        close = float(row["CLOSE"])
        high = float(row["HIGH"])
        low = float(row["LOW"])
        ldcp = float(row["LDCP"])
        daily = weekly = monthly = "N/A"

        # Daily
        if not df_prev_day.empty:
            prev = df_prev_day[df_prev_day["SYMBOL"] == symbol]
            if not prev.empty:
                prev_high = float(prev["HIGH"].iloc[0])
                prev_low = float(prev["LOW"].iloc[0])
                if close > prev_high:
                    daily = "▲▲ Daily Breakout"
                elif close < prev_low:
                    daily = "▼▼ Daily Breakdown"
                else:
                    daily = "– Daily Within Range"

        # Weekly
        if not df_week.empty:
            week = df_week[df_week["SYMBOL"] == symbol]
            if not week.empty:
                w_high = week["HIGH"].astype(float).max()
                w_low = week["LOW"].astype(float).min()
                if close > w_high:
                    weekly = "▲▲ Weekly Breakout"
                elif close < w_low:
                    weekly = "▼▼ Weekly Breakdown"
                else:
                    weekly = "– Weekly Within Range"

        # Monthly
        if not df_month.empty:
            month = df_month[df_month["SYMBOL"] == symbol]
            if not month.empty:
                m_high = month["HIGH"].astype(float).max()
                m_low = month["LOW"].astype(float).min()
                if close > m_high:
                    monthly = "▲▲ Monthly Breakout"
                elif close < m_low:
                    monthly = "▼▼ Monthly Breakdown"
                else:
                    monthly = "– Monthly Within Range"

        results.append({
            "SYMBOL": symbol,
            "CLOSE": close,
            "LDCP": ldcp,
            "HIGH": high,
            "LOW": low,
            "VOLUME": row.get("VOLUME", ""),
            "DAILY_STATUS": daily,
            "WEEKLY_STATUS": weekly,
            "MONTHLY_STATUS": monthly
        })
    return pd.DataFrame(results)

# === Gradio UI ===
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
""") as demo:
    gr.Markdown("### 📈 PSX Breakout Analysis (via Supabase)")

    run_btn = gr.Button("Run Analysis")
    preview_html = gr.HTML()
    daily_plot = gr.Plot()
    weekly_plot = gr.Plot()
    monthly_plot = gr.Plot()

    def run():
        latest = get_latest_trading_date()
        if not latest:
            return "❌ No data found", None, None, None

        today = datetime.strptime(latest, "%Y-%m-%d")
        df_today = get_data_by_date(latest)

        # Previous day
        df_prev = pd.DataFrame()
        for i in range(1, 6):
            prev_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            df_prev = get_data_by_date(prev_date)
            if not df_prev.empty:
                break

        # Previous week
        week_start = (today - timedelta(days=today.weekday() + 7)).strftime("%Y-%m-%d")
        week_end = (today - timedelta(days=today.weekday() + 3)).strftime("%Y-%m-%d")
        df_week = get_data_between(week_start, week_end)

        # Previous month
        first_prev_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
        last_prev_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        df_month = get_data_between(first_prev_month, last_prev_month)

        # Compute
        results = calculate_breakout(df_today, df_prev, df_week, df_month)

        # HTML Preview
        html = "<table class='styled-table'>"
        html += "<thead><tr>" + "".join(f"<th>{col}</th>" for col in results.columns) + "</tr></thead><tbody>"
        for _, row in results.iterrows():
            html += "<tr>" + "".join(f"<td>{val}</td>" for val in row.values) + "</tr>"
        html += "</tbody></table>"

        # Charts
        daily_counts = get_counts(results, "DAILY_STATUS")
        weekly_counts = get_counts(results, "WEEKLY_STATUS")
        monthly_counts = get_counts(results, "MONTHLY_STATUS")

        return html, create_pie_chart(daily_counts, "Daily Breakout"), create_pie_chart(weekly_counts, "Weekly Breakout"), create_pie_chart(monthly_counts, "Monthly Breakout")

    run_btn.click(fn=run, outputs=[preview_html, daily_plot, weekly_plot, monthly_plot])

if __name__ == "__main__":
    demo.launch()
