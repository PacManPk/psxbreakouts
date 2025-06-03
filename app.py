import gradio as gr
import pandas as pd
import requests
from io import StringIO, BytesIO

# Hardcoded URLs from your notebook
PSX_STOCK_DATA_URL = "https://docs.google.com/spreadsheets/d/1wGpkG37p2GV4aCckLYdaznQ4FjlQog8E/export?format=csv"
KMI_SYMBOLS_FILE_URL = "https://drive.google.com/uc?export=download&id=1Lf24EnwxUV3l64Y6i_XO-JoP0CEY-tuB"

def fetch_and_process_data():
    # Fetch PSX stock data
    psx_data = requests.get(PSX_STOCK_DATA_URL)
    psx_df = pd.read_csv(StringIO(psx_data.text))
    
    # Fetch KMI symbols
    kmi_data = requests.get(KMI_SYMBOLS_FILE_URL)
    kmi_df = pd.read_csv(StringIO(kmi_data.text))
    kmi_symbols = kmi_df["Symbol"].str.strip().str.upper().tolist()

    # Standardize Symbol format
    psx_df["Symbol"] = psx_df["Symbol"].str.strip().str.upper()

    # Add KMI inclusion column
    psx_df["KMI"] = psx_df["Symbol"].apply(lambda x: "Yes" if x in kmi_symbols else "No")

    return psx_df

def scan_and_export():
    df = fetch_and_process_data()

    # Prepare Excel for download
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name="PSX_Scanner", index=False)
    output.seek(0)

    return df, ("psx_breakup_scanner_output.xlsx", output)

# Gradio app interface
with gr.Blocks(title="PSX Breakup Scanner") as demo:
    gr.Markdown("## 📈 PSX Breakup Scanner with KMI Filtering")
    gr.Markdown("Click the button below to scan the PSX and download results.")

    with gr.Row():
        scan_btn = gr.Button("🔍 Run Scanner")
    
    data_output = gr.Dataframe(label="Scanned Results", interactive=False)
    file_output = gr.File(label="Download Excel")

    scan_btn.click(fn=scan_and_export, outputs=[data_output, file_output])

demo.launch()
