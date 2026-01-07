import os
import streamlit as st
from st_chat_message import message
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

st.set_page_config(page_title="AI Search Assistant")
st.title("🔍 AI Search Assistant")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "loading" not in st.session_state:
    st.session_state.loading = False

WEB_SEARCH_MODELS = ["gpt-5", "gpt-4.1"]
ALL_MODELS = ["gpt-5", "gpt-4.1", "gpt-4.1-mini"]
WEB_SEARCH_MODES = ["Auto", "Manual", "Always"]

selected_model = st.selectbox("Select model", ALL_MODELS, index=ALL_MODELS.index("gpt-4.1"))
selected_mode = st.selectbox("Select web search mode", WEB_SEARCH_MODES, index=WEB_SEARCH_MODES.index("Auto"))

manual_toggle = st.toggle("Enable Web Search", value=False) if selected_mode == "Manual" else False

if selected_model not in WEB_SEARCH_MODELS and (selected_mode == "Always" or (selected_mode == "Manual" and manual_toggle)):
    st.warning("⚠️ This model does not support web search.\n\nPlease switch to **gpt-5** or **gpt-4.1**.")

for idx, chat in enumerate(st.session_state.chat_history):
    message(chat["text"], is_user=chat["is_user"], key=f"chat_{idx}")

def should_search(query: str) -> bool:
    return any(k in query.lower() for k in [ "latest", "today", "current", "news", "price", "update", "breaking", "trend", "announcement", "weather", "stocks", "score"])

def get_web_search_enabled(query: str) -> bool:
    if selected_mode == "Always":
        return True
    if selected_mode == "Manual":
        return manual_toggle
    # Auto mode
    return should_search(query)

def handle_submit():
    query = st.session_state.user_input.strip()
    if not query:
        return

    web_search = get_web_search_enabled(query)
    st.session_state._current_web_search = web_search

    st.session_state.chat_history.append({"text": query, "is_user": True})

    loading_text = "🔎 Searching the web..." if web_search and selected_mode != "Auto" else "Thinking..."
    st.session_state.chat_history.append({"text": loading_text, "is_user": False})

    st.session_state.loading = True
    st.session_state.user_input = ""


st.text_input("Type your message and press Enter", key="user_input", on_change=handle_submit)

if st.session_state.loading:
    try:
        last_user_message = next(m["text"] for m in reversed(st.session_state.chat_history) if m["is_user"])
        web_search_enabled = getattr(st.session_state, "_current_web_search", False)

        query_for_model = last_user_message
        if web_search_enabled:
            query_for_model = f"You may search the web to find the following information if required:\n\n{last_user_message}"

        response = client.responses.create(
            model=selected_model,
            tools=[{"type": "web_search"}] if web_search_enabled else None,
            input=query_for_model
        )

        citations = {}

        for out in response.output:
            print(out)
            if out.type == "message":
                for item in out.content:
                    for annotation in item.annotations:
                        citations[annotation.title] = annotation.url


        answer = response.output_text
        if any(msg.type == "web_search_call" for msg in response.output):
            answer = f"\n\n🔎 Web Search Results:\n\n{answer}"


        if citations:
            answer += "\n\n📚 Citations:\n"
            for title, url in citations.items():
                answer += f"- [{title}]({url})\n"

        st.session_state.chat_history[-1] = {"text": answer, "is_user": False}

    except Exception as e:
        st.session_state.chat_history[-1] = {"text": f"❌ API error: {e}", "is_user": False}

    finally:
        st.session_state.loading = False
        st.rerun()