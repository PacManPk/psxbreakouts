import gradio as gr
import pandas as pd

def scan_psx_file(file):
    try:
        df = pd.read_excel(file.name) if file.name.endswith('.xlsx') else pd.read_csv(file.name)

        # --- Begin Core Logic Placeholder ---
        # Example: calculate fake halal/haram split for demonstration
        total_income = df['Income'].sum()
        haram_income = df[df['Type'] == 'Haram']['Income'].sum()
        halal_income = total_income - haram_income

        result = f"""
        ✅ Total Income: {total_income:,.2f}
        🟩 Halal Income: {halal_income:,.2f}
        🟥 Haram Income: {haram_income:,.2f}
        🔁 Halal %: {100 * halal_income / total_income:.2f}%
        """
        return result.strip()
        # --- End Core Logic Placeholder ---

    except Exception as e:
        return f"Error: {str(e)}"

iface = gr.Interface(
    fn=scan_psx_file,
    inputs=gr.File(label="Upload PSX Excel/CSV", file_types=[".csv", ".xlsx"]),
    outputs=gr.Textbox(label="Breakdown"),
    title="📊 PSX Income Halal Scanner",
    description="Uploads PSX data and gives a halal/haram income breakdown. File must contain 'Income' and 'Type' columns."
)

if __name__ == "__main__":
    iface.launch(share=True)
