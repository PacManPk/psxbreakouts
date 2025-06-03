import gradio as gr
import pandas as pd
import plotly.express as px
import requests
from io import StringIO

PSX_CSV_URL = "https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv"
KMI_CSV_URL = "https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB"

def fetch_csv(url):
    response = requests.get(url)
    return pd.read_csv(StringIO(response.text))

def process_data():
    df = fetch_csv(PSX_CSV_URL)
    kmi_df = fetch_csv(KMI_CSV_URL)

    # Basic cleaning
    df.columns = df.columns.str.strip()
    df["Symbol"] = df["Symbol"].str.strip().str.upper()
    kmi_df["Symbol"] = kmi_df["Symbol"].str.strip().str.upper()

    # Ensure required columns
    required_columns = [
        "Symbol", "Revenue", "Interest", "Other Haram Income"
    ]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        return f"<p style='color:red;'>Missing column(s): {', '.join(missing)}</p>", None

    # Mark KMI status
    df["KMI"] = df["Symbol"].apply(lambda x: "Yes" if x in kmi_df["Symbol"].values else "No")

    # Calculate fields
    df["Total Income"] = df["Revenue"]
    df["Haram Income"] = df["Interest"] + df["Other Haram Income"]
    df["Haram %"] = (df["Haram Income"] / df["Total Income"]) * 100
    df["Haram %"] = df["Haram %"].round(2)

    # Purification amount (1 share basis)
    df["Purification / Share"] = df["Haram Income"] / df["Total Income"] * df["Revenue"]
    df["Purification / Share"] = df["Purification / Share"].fillna(0).round(2)

    # Filter for KMI
    filtered_df = df[df["KMI"] == "Yes"].copy()
    filtered_df = filtered_df.sort_values(by="Haram %", ascending=False)

    # Plot
    fig = px.bar(filtered_df, x="Symbol", y="Haram %", title="Haram Income % of KMI Stocks", text="Haram %")
    fig.update_traces(textposition='outside')
    fig.update_layout(yaxis=dict(title="Haram %"), xaxis=dict(title="Symbol"))

    # Display table
    display_cols = [
        "Symbol", "Revenue", "Interest", "Other Haram Income", "Haram Income", "Haram %", "Purification / Share"
    ]
    table_html = filtered_df[display_cols].to_html(index=False, classes="table table-striped", border=0)

    return table_html, fig


# Gradio UI
with gr.Blocks(title="PSX Halal Screening (KMI)") as demo:
    gr.Markdown("## PSX Halal Screening Report - KMI 30 Index")
    gr.Markdown("Click below to analyze and display haram income percentages and purification data.")

    with gr.Row():
        generate_button = gr.Button("🔍 Generate Report")

    output_html = gr.HTML()
    chart_output = gr.Plot()

    generate_button.click(fn=process_data, inputs=[], outputs=[output_html, chart_output])

if __name__ == "__main__":
    print("===== Application Startup =====")
    demo.launch()
