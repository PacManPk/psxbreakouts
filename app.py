import gradio as gr
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import tempfile
import plotly.express as px
from pytz import timezone

# [All your existing functions EXCEPT main() - get_symbols_data(), fetch_market_data(), 
#  calculate_breakout_stats(), etc. would go here]

# Gradio-specific functions
def generate_report():
    """Adapted main function for Gradio"""
    # [Same logic as your main() function until result_df is generated]
    
    # Generate formatted Excel
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        EXCEL_FILE = tmp.name
        save_to_excel(result_df, today_date)  # Your existing function
        
        # Create visualizations
        daily_counts = get_counts(result_df, 'DAILY_STATUS')
        weekly_counts = get_counts(result_df, 'WEEKLY_STATUS')
        monthly_counts = get_counts(result_df, 'MONTHLY_STATUS')
        
        fig_daily = create_pie_chart(daily_counts, "Daily Breakout Distribution")
        fig_weekly = create_pie_chart(weekly_counts, "Weekly Breakout Distribution")
        fig_monthly = create_pie_chart(monthly_counts, "Monthly Breakout Distribution")
        
        return (
            EXCEL_FILE,
            result_df,
            fig_daily,
            fig_weekly,
            fig_monthly,
            pd.DataFrame.from_dict(daily_counts, orient='index').reset_index(),
            pd.DataFrame.from_dict(weekly_counts, orient='index').reset_index(),
            pd.DataFrame.from_dict(monthly_counts, orient='index').reset_index()
        )

def get_counts(df, status_col):
    """Count breakout statuses for visualization"""
    return {
        "Breakout": len(df[df[status_col].str.contains("▲▲")]),
        "Breakdown": len(df[df[status_col].str.contains("▼▼")]),
        "Within Range": len(df[df[status_col].str.contains("–")])
    }

def create_pie_chart(counts, title):
    """Create Plotly pie chart"""
    df = pd.DataFrame({
        'Status': list(counts.keys()),
        'Count': list(counts.values())
    })
    fig = px.pie(df, values='Count', names='Status', title=title)
    return fig

# Gradio Interface
with gr.Blocks(title="PSX Breakout Scanner", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 📈 PSX Breakout Scanner")
    gr.Markdown("Identifies breakout/breakdown signals in Pakistan Stock Exchange")
    
    with gr.Row():
        run_btn = gr.Button("Run Analysis", variant="primary")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Download Full Report")
            download = gr.File(label="Excel Report")
        
        with gr.Column():
            gr.Markdown("### Preview Data")
            dataframe = gr.Dataframe(interactive=False, wrap=True)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Daily Analysis")
            daily_plot = gr.Plot()
            daily_table = gr.Dataframe(headers=["Status", "Count"])
        
        with gr.Column():
            gr.Markdown("### Weekly Analysis")
            weekly_plot = gr.Plot()
            weekly_table = gr.Dataframe(headers=["Status", "Count"])
        
        with gr.Column():
            gr.Markdown("### Monthly Analysis")
            monthly_plot = gr.Plot()
            monthly_table = gr.Dataframe(headers=["Status", "Count"])
    
    run_btn.click(
        fn=generate_report,
        outputs=[
            download,
            dataframe,
            daily_plot,
            weekly_plot,
            monthly_plot,
            daily_table,
            weekly_table,
            monthly_table
        ]
    )

if __name__ == "__main__":
    app.launch(server_port=7860, share=True)