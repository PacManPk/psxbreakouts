def filter_data(filter_breakout, filter_sector, filter_kmi, filter_circuit_breaker, filter_symbols):
    """Filter data based on user selections"""
    global loaded_data

    if loaded_data is None:
        return gr.HTML("No data available")

    df = loaded_data.copy()

    if filter_breakout:
        df = df[(df['DAILY_STATUS'].str.contains("▲▲")) &
                (df['WEEKLY_STATUS'].str.contains("▲▲")) &
                (df['MONTHLY_STATUS'].str.contains("▲▼"))]

    if filter_sector != "All":
        df = df[df['SECTOR'] == filter_sector]

    if filter_kmi != "All":
        df = df[df['KMI_COMPLIANT'] == filter_kmi]

    if filter_circuit_breaker != "All":
        if filter_circuit_breaker == "Upper Circuit Breaker":
            df = df[df['CIRCUIT_BREAKER_STATUS'] == "Upper Circuit Breaker"]
        elif filter_circuit_breaker == "Lower Circuit Breaker":
            df = df[df['CIRCUIT_BREAKER_STATUS'] == "Lower Circuit Breaker"]

    if filter_symbols:
        symbols = [symbol.strip().upper() for symbol in filter_symbols.split(',')]
        df = df[df['SYMBOL'].isin(symbols)]

    # Apply styling
    styled_df = df.style.map(highlight_status, subset=['DAILY_STATUS', 'WEEKLY_STATUS', 'MONTHLY_STATUS', 'CIRCUIT_BREAKER_STATUS'])

    # Convert the DataFrame to HTML
    df_html = df.to_html(escape=False, index=False)

    # Create HTML with frozen first column
    html = f"""
    <div style="width:100%; overflow-x:auto;">
        <div style="display:flex;">
            <div style="flex: none; width: 150px; background: white; position: sticky; left: 0; z-index: 1;">
                <table style="width:150px; border-collapse: collapse;">
                    <tr><th style="background-color: #f2f2f2; position: sticky; left: 0;">{df.columns[0]}</th></tr>
                    {''.join(f'<tr><td style="background: white;">{row}</td></tr>' for row in df[df.columns[0]])}
                </table>
            </div>
            <div style="flex: auto; overflow-x: auto;">
                <table style="border-collapse: collapse; width: 100%;">
                    {df_html}
                </table>
            </div>
        </div>
    </div>
    <style>
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid black; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
    """
    return gr.HTML(html)
