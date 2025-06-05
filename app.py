import gradio as gr
import pandas as pd
import plotly.graph_objects as go
from utils import (load_and_process_data, plot_selected_stock, get_latest_data,
                   identify_breakouts, identify_breakdowns, highlight_table)

def scan_and_plot(selected_symbol, date_range):
    df = get_latest_data()
    filtered_df = df[df['Symbol'] == selected_symbol]
    breakout_df = identify_breakouts(df, date_range)
    breakdown_df = identify_breakdowns(df, date_range)

    fig = plot_selected_stock(filtered_df, selected_symbol)
    return fig, breakout_df, breakdown_df

def run_app():
    with gr.Blocks(css="""
        .download-button button {
            width: 100%;
            background-color: #0d6efd;
            color: white;
            border: none;
            padding: 0.75em;
            font-weight: bold;
            border-radius: 0.5em;
        }
        .gr-dataframe thead tr {
            background-color: #0d6efd;
            color: white;
        }
        .gr-dataframe tbody tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        .gr-dataframe tbody tr:hover {
            background-color: #e9ecef;
        }
    """) as app:
        gr.Markdown("# PSX Breakout Scanner")

        with gr.Row():
            with gr.Column():
                symbol_input = gr.Textbox(label="Enter Symbol (e.g. MLCF)", value="MLCF")
                date_range_input = gr.Slider(1, 30, value=10, step=1, label="Date Range (days)")
                run_button = gr.Button("Scan")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Download Data")
                download_btn = gr.File(label="Download Excel", interactive=False, elem_classes="download-button")

        with gr.Tabs():
            with gr.TabItem("Chart"):
                fig_output = gr.Plot(label="Price Chart")
            with gr.TabItem("Breakouts"):
                breakout_table = gr.Dataframe(label="Breakouts", wrap=True, render=False)
            with gr.TabItem("Breakdowns"):
                breakdown_table = gr.Dataframe(label="Breakdowns", wrap=True, render=False)

        def on_run(symbol, days):
            fig, breakout_df, breakdown_df = scan_and_plot(symbol, days)

            # Highlight and style
            styled_breakout = highlight_table(breakout_df)
            styled_breakdown = highlight_table(breakdown_df)

            # Save Excel
            excel_path = "output/breakout_breakdown_data.xlsx"
            with pd.ExcelWriter(excel_path) as writer:
                breakout_df.to_excel(writer, sheet_name="Breakouts", index=False)
                breakdown_df.to_excel(writer, sheet_name="Breakdowns", index=False)

            return fig, styled_breakout, styled_breakdown, excel_path

        run_button.click(fn=on_run,
                         inputs=[symbol_input, date_range_input],
                         outputs=[fig_output, breakout_table, breakdown_table, download_btn])

    app.launch()

if __name__ == '__main__':
    run_app()
