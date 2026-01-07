import os
import streamlit as st
from st_chat_message import message
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_KEY"))


st.markdown("""
<style>
/* Align selectbox and buttons */
div[data-testid="column"] {
    display: flex;
    align-items: center;
}

/* Make buttons same height as selectbox */
.stButton > button {
    height: 40px;
    margin-top: 28px;
}

/* Selectbox height tweak */
div[data-baseweb="select"] {
    min-height: 48px;
}
</style>
""", unsafe_allow_html=True)


st.set_page_config(
    page_title="AI Search Assistant",
    page_icon="🔍",
    layout="centered"
)

st.title("🔍 AI Search Assistant")

DEFAULT_WEB_SEARCH_SETTINGS = {
    "reference_urls": [],
    "location": {
        "country": "India",
        "region": "",
        "city": "",
        "timezone": "Asia/Kolkata",
    },
    "context_size": 5,
}

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "loading" not in st.session_state:
    st.session_state.loading = False

if "web_search_enabled" not in st.session_state:
    st.session_state.web_search_enabled = False

if "web_search_settings" not in st.session_state:
    st.session_state.web_search_settings = DEFAULT_WEB_SEARCH_SETTINGS.copy()

@st.dialog("⚙️ Web Search Configuration")
def web_search_modal():
    settings = st.session_state.web_search_settings

    st.markdown("### 🌐 Reference URLs (optional)")
    reference_urls = st.text_area(
        "One URL per line",
        value="\n".join(settings["reference_urls"]),
        placeholder="https://openai.com/research"
    )

    st.markdown("### 📍 User Location")
    col1, col2 = st.columns(2)
    country = col1.text_input("Country", value=settings["location"]["country"])
    region = col2.text_input("Region / State", value=settings["location"]["region"])

    city = st.text_input("City", value=settings["location"]["city"])
    timezone = st.text_input(
        "Timezone",
        value=settings["location"]["timezone"]
    )

    context_size = st.slider(
        "Search Context Size",
        1, 10,
        value=settings["context_size"]
    )

    st.divider()

    if st.button("💾 Save Configuration", use_container_width=True):
        st.session_state.web_search_settings = {
            "reference_urls": [
                u.strip() for u in reference_urls.splitlines() if u.strip()
            ],
            "location": {
                "country": country,
                "region": region,
                "city": city,
                "timezone": timezone,
            },
            "context_size": context_size,
        }
        st.rerun()

col1, col2, col3 = st.columns([3, 1, 1])

with col1:
    model = st.selectbox(
        "",
        ["gpt-5", "gpt-4.1"],
        index=0
    )

with col2:
    if st.button("⚙️ Configure"):
        web_search_modal()

with col3:
    if st.button(
        "🛑 Search ON" if st.session_state.web_search_enabled else "▶️ Search OFF"
    ):
        st.session_state.web_search_enabled = not st.session_state.web_search_enabled
        st.rerun()

for i, chat in enumerate(st.session_state.chat_history):
    message(chat["text"], is_user=chat["is_user"], key=f"chat_{i}")

def handle_submit():
    query = st.session_state.user_input.strip()
    if not query:
        return

    st.session_state.chat_history.append(
        {"text": query, "is_user": True}
    )

    st.session_state.chat_history.append(
        {
            "text": "🔎 Searching the web..."
            if st.session_state.web_search_enabled
            else "Thinking...",
            "is_user": False
        }
    )

    st.session_state.loading = True
    st.session_state.user_input = ""

st.text_input(
    "Type your message and press Enter",
    key="user_input",
    on_change=handle_submit
)

if st.session_state.loading:
    try:
        user_query = next(
            m["text"]
            for m in reversed(st.session_state.chat_history)
            if m["is_user"]
        )

        tools = None
        prompt = user_query

        settings = st.session_state.web_search_settings

        ref_text = ""
        if settings["reference_urls"]:
            ref_text = (
                "Prioritize these sources if relevant:\n"
                + "\n".join(settings["reference_urls"])
                + "\n\n"
            )

        prompt = (
            "You may search the web to find the following information if required:\n"
            f"User location:\n{settings['location']}\n\n"
            f"{ref_text}"
            f"Query:\n{user_query}"
        )

        tools = [{"type": "web_search"}]

        response = client.responses.create(
            model=model,
            tools=tools if st.session_state.web_search_enabled else None,
            input=prompt,
        )

        answer = response.output_text
        citations = {}

        for out in response.output:
            if out.type == "message":
                for item in out.content:
                    for ann in item.annotations:
                        citations[ann.title] = ann.url

        if citations:
            answer += "\n\n📚 **Citations**\n"
            for title, url in citations.items():
                answer += f"- [{title}]({url})\n"

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
