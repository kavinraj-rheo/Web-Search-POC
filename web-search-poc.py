import streamlit as st
from st_chat_message import message
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

st.set_page_config(page_title="AI Search Assistant")

st.title("🔍 AI Search Assistant")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Web search toggle
web_search_enabled = st.toggle("Enable Web Search", value=False)

# Model lists
WEB_SEARCH_MODELS = ["gpt-5", "gpt-4.1"]
NON_WEB_MODELS = ["gpt-4.1", "gpt-4.1-mini"]
ALL_MODELS = list(dict.fromkeys(WEB_SEARCH_MODELS + NON_WEB_MODELS))

# Model dropdown
selected_model = st.selectbox(
    "Select model",
    ALL_MODELS,
    index=ALL_MODELS.index("gpt-4.1")
)

# Model capability hint
if web_search_enabled and selected_model not in WEB_SEARCH_MODELS:
    st.warning(
        "⚠️ This model does not support web search.\n\n"
        "Please switch to **gpt-5** or **gpt-4.1**."
    )

# Display chat history
for chat in st.session_state.chat_history:
    message(chat["text"], is_user=chat["is_user"])

# Callback to handle Enter press
def handle_submit():
    query = st.session_state.user_input.strip()
    if not query:
        return

    # Check web search compatibility
    if web_search_enabled and selected_model not in WEB_SEARCH_MODELS:
        st.warning("Cannot proceed: Selected model does not support web search.")
        st.session_state.user_input = ""  # clear input
        return

    # Append user message
    st.session_state.chat_history.append({"text": query, "is_user": True})

    try:
        if web_search_enabled:
            response = client.responses.create(
                model=selected_model,
                tools=[{"type": "web_search"}],
                input=query
            )
        else:
            response = client.responses.create(
                model=selected_model,
                input=query
            )
        answer = response.output_text
        st.session_state.chat_history.append({"text": answer, "is_user": False})
    except Exception as e:
        st.error(f"API error: {e}")
    # Clear input
    st.session_state.user_input = ""

# User input box
st.text_input(
    "Type your message and press Enter",
    key="user_input",
    on_change=handle_submit
)