import gradio as gr
from data_loader import fetch_psx
from screener_utils import open_gt_prev_close, volume_increasing
from query_parser import parse_query

def chat_fn(query: str):
    parsed = parse_query(query)
    results = []
    symbols = ["HBL", "UBL", "TRG"]  # can expand or load complete list

    for sym in symbols:
        df = fetch_psx(sym)
        if parsed["type"] == "open_gt_prev_close":
            df2 = open_gt_prev_close(df, parsed["days"])
            if not df2.empty:
                results.append(f"{sym}: {len(df2)} matches (most recent: {df2.iloc[-1]['Date'].strftime('%Y-%m-%d')})")
        elif parsed["type"] == "volume_increasing":
            if volume_increasing(fetch_psx(sym)):
                results.append(f"{sym}: volume ↑ over last {parsed['window']} days")
    if not results:
        return "No matching stocks found."
    return "\n".join(results)

with gr.Blocks() as demo:
    chatbot = gr.Chatbot()
    msg = gr.Textbox(placeholder="Ask about PSX screeners…")
    msg.submit(lambda q, history: (history + [(q, chat_fn(q))]), [msg, chatbot], [chatbot])

if __name__ == "__main__":
    demo.launch()
