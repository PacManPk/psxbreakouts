import gradio as gr
from data_loader import fetch_psx
from screener_utils import open_gt_prev_close, volume_increasing
from query_parser import parse_query

# Main chatbot logic
def chat_fn(query: str):
    parsed = parse_query(query)
    results = []
    symbols = ["HBL", "UBL", "TRG"]  # Replace with your full PSX symbol list later

    for sym in symbols:
        try:
            df = fetch_psx(sym)
            if parsed["type"] == "open_gt_prev_close":
                df2 = open_gt_prev_close(df, parsed["days"])
                if not df2.empty:
                    results.append(f"{sym}: {len(df2)} matches (latest: {df2.iloc[-1]['Date'].strftime('%Y-%m-%d')})")
            elif parsed["type"] == "volume_increasing":
                if volume_increasing(df):
                    results.append(f"{sym}: volume ↑ over last {parsed['window']} days")
        except Exception as e:
            results.append(f"{sym}: failed to load data ({e})")

    if not results:
        return "No matching stocks found."
    return "\n".join(results)

# Gradio app
with gr.Blocks() as demo:
    chatbot = gr.Chatbot(type="messages")
    msg = gr.Textbox(placeholder="Ask about PSX screeners…")

    def respond(user_message, history):
        bot_reply = chat_fn(user_message)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": bot_reply})
        return history

    msg.submit(respond, [msg, chatbot], [chatbot])

if __name__ == "__main__":
    demo.launch()
