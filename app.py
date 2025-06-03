import pandas as pd
import requests
import gradio as gr
import plotly.express as px
from io import StringIO

PSX_CSV_URL = "https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv"
KMI_CSV_URL = "https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB"

REQUIRED_COLUMNS = ["Symbol", "Name", "Revenue", "Interest", "Other Haram Income"]

def fetch_csv(url):
    response = requests.get(url)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))

def process_data():
    df = fetch_csv(PSX_CSV_URL)
    kmi_df = fetch_csv(KMI_CSV_URL)

    # Ensure required columns exist
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            return f"<p style='color:red;'>Missing column in PSX data: {col}</p>", None

    df["Symbol"] = df["Symbol"].str.strip().str.upper()
    kmi_df["Symbol"] = kmi_df["Symbol"].str.strip().str.upper()
    df["KMI"] = df["Symbol"].apply(lambda x: "Yes" if x in kmi_df["Symbol"].values else "No")

    df["Total Income"] = df["Revenue"]  # Only using Revenue, since Other Income is not present
    df["Haram Income"] = df["Interest"] + df["Other Haram Income"]
    df["Haram %"] = (df["Haram Income"] / df["Total Income"]) * 100

    filtered_df = df[df["KMI"] == "Yes"].copy()
    filtered_df = filtered_df.sort_values(by="Haram %", ascending=False)

    fig = px.bar(filtered_df, x="Symbol", y="Haram %", title="Haram Income % of KMI Stocks")
    html_table = filtered_df[["Symbol", "Name", "Revenue", "Interest", "Other Haram Income", "Total Income", "Haram Income", "Haram %"]].to_html(index=False, classes="table table-striped")

    return html_table, fig

demo = gr.Interface(
    fn=process_data,
    inputs=[],
    outputs=[gr.HTML(label="Detailed Halal-Haram Analysis"), gr.Plot(label="Haram Income % Chart")],
    title="PSX Halal-Haram Breakup Scanner (KMI Stocks)"
)

if __name__ == "__main__":
    demo.launch()
