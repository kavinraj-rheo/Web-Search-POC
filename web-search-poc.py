import os
import streamlit as st
from st_chat_message import message
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ----------------------------
# OpenAI setup
# ----------------------------
OPENAI_KEY = os.getenv("OPENAI_KEY")
client = OpenAI(api_key=OPENAI_KEY)

# ----------------------------
# Streamlit config
# ----------------------------
st.set_page_config(page_title="AI Search Assistant")
st.title("🔍 AI Search Assistant")

# ----------------------------
# Session state
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "loading" not in st.session_state:
    st.session_state.loading = False

# ----------------------------
# Controls
# ----------------------------
web_search_enabled = st.toggle("Enable Web Search", value=False)
force_web_search = False

if web_search_enabled:
    force_web_search = st.toggle("Force Web Search", value=False)

WEB_SEARCH_MODELS = ["gpt-5", "gpt-4.1"]
NON_WEB_MODELS = ["gpt-4.1", "gpt-4.1-mini"]
ALL_MODELS = list(dict.fromkeys(WEB_SEARCH_MODELS + NON_WEB_MODELS))

selected_model = st.selectbox(
    "Select model",
    ALL_MODELS,
    index=ALL_MODELS.index("gpt-4.1")
)

if web_search_enabled and selected_model not in WEB_SEARCH_MODELS:
    st.warning(
        "⚠️ This model does not support web search.\n\n"
        "Please switch to **gpt-5** or **gpt-4.1**."
    )

# ----------------------------
# Render chat history
# ----------------------------
for idx, chat in enumerate(st.session_state.chat_history):
    message(
        chat["text"],
        is_user=chat["is_user"],
        key=f"chat_{idx}"
    )

# ----------------------------
# Handle submit
# ----------------------------
def handle_submit():
    query = st.session_state.user_input.strip()
    if not query:
        return

    if web_search_enabled and selected_model not in WEB_SEARCH_MODELS:
        st.warning("Cannot proceed: Selected model does not support web search.")
        st.session_state.user_input = ""
        return

    # User message
    st.session_state.chat_history.append(
        {"text": query, "is_user": True}
    )

    # Loading message
    loading_text = (
        "🔎 Searching the web..."
        if web_search_enabled or force_web_search
        else "⚙️ Fetching results..."
    )

    st.session_state.chat_history.append(
        {"text": loading_text, "is_user": False}
    )

    st.session_state.loading = True
    st.session_state.user_input = ""

# ----------------------------
# Input
# ----------------------------
st.text_input(
    "Type your message and press Enter",
    key="user_input",
    on_change=handle_submit
)

# ----------------------------
# Execute API after render
# ----------------------------
if st.session_state.loading:
    try:
        last_user_message = next(
            m["text"]
            for m in reversed(st.session_state.chat_history)
            if m["is_user"]
        )

        # 🔹 Force web search prompt prefix
        query_for_model = last_user_message
        if force_web_search:
            query_for_model = (
                "Search the internet for the following:\n\n"
                + last_user_message
            )

        if web_search_enabled or force_web_search:
            response = client.responses.create(
                model=selected_model,
                tools=[{"type": "web_search"}],
                input=query_for_model
            )
        else:
            response = client.responses.create(
                model=selected_model,
                input=query_for_model
            )

        answer = response.output_text

        # Replace loading message
        st.session_state.chat_history[-1] = {
            "text": answer,
            "is_user": False
        }

    except Exception as e:
        st.session_state.chat_history[-1] = {
            "text": f"❌ API error: {e}",
            "is_user": False
        }

    finally:
        st.session_state.loading = False
        st.rerun()
