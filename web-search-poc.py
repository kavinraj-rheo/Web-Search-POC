import os
import yaml
import pycountry
import pytz
import streamlit as st
from st_chat_message import message
from openai import OpenAI
from dotenv import load_dotenv
from urllib.parse import urlparse

# -------------------- LOAD CONFIG --------------------
CONFIG_PATH = "config.yaml"
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
else:
    config = {"search_mode": "manual"}  # default
SEARCH_MODE = config.get("search_mode", "manual")  # "auto", "always", "manual"

# -------------------- LOAD OPENAI --------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

# -------------------- STREAMLIT STYLING --------------------
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

# -------------------- DEFAULT SETTINGS --------------------
DEFAULT_WEB_SEARCH_SETTINGS = {
    "reference_urls": [],
    "location": {
        "country": "India",
        "region": "",
        "city": "",
        "timezone": "Asia/Kolkata",
    },
    "context_size": "medium",  # low / medium / high
}

# -------------------- SESSION STATE --------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "loading" not in st.session_state:
    st.session_state.loading = False

if "web_search_enabled" not in st.session_state:
    # Only relevant in manual mode
    st.session_state.web_search_enabled = False

if "web_search_settings" not in st.session_state:
    st.session_state.web_search_settings = DEFAULT_WEB_SEARCH_SETTINGS.copy()

# -------------------- CONFIG MODAL --------------------
@st.dialog("⚙️ Web Search Configuration")
def web_search_modal():
    settings = st.session_state.web_search_settings

    # Reference URLs
    st.markdown("### 🌐 Reference URLs (optional)")
    reference_urls = st.text_area(
        label="Reference URLs",
        value="\n".join(settings["reference_urls"]),
        placeholder="https://openai.com/research"
    )

    # Location
    st.markdown("### 📍 User Location")
    col1, col2 = st.columns(2)

    countries = sorted([c.name for c in pycountry.countries])
    country = col1.selectbox("Country", options=countries, index=countries.index(settings["location"].get("country", "India")))

    regions = col2.text_input("Region / State", value=settings["location"].get("region", ""))

    cities = st.text_input("City", value=settings["location"].get("city", ""))
    timezones = sorted(pytz.all_timezones)
    timezone = st.selectbox("Timezone", options=timezones, index=timezones.index(settings["location"].get("timezone", "Asia/Kolkata")))

    # Context Size
    st.markdown("### 🧠 Web Context Size")
    context_label = st.selectbox(
        "How much web content should be used?",
        options=["Low", "Medium", "High"],
        index=["Low", "Medium", "High"].index(settings.get("context_size", "medium").capitalize())
    )

    if st.button("💾 Save Configuration", use_container_width=True):
        st.session_state.web_search_settings = {
            "reference_urls": [u.strip() for u in reference_urls.splitlines() if u.strip()],
            "location": {
                "country": country,
                "region": regions,
                "city": cities,
                "timezone": timezone,
            },
            "context_size": context_label.lower(),  # store as lowercase
        }
        st.rerun()

# -------------------- TOP BAR --------------------
col1, col2, col3 = st.columns([3, 1, 1])

with col1:
    model = st.selectbox(
        label="Select Model",
        options=["gpt-4.1", "gpt-5"],
        index=0,
    )

with col2:
    if st.button("⚙️ Configure"):
        web_search_modal()

with col3:
    if SEARCH_MODE == "manual":
        if st.button("🛑 Search ON" if st.session_state.web_search_enabled else "▶️ Search OFF"):
            st.session_state.web_search_enabled = not st.session_state.web_search_enabled
            st.rerun()

# -------------------- CHAT HISTORY --------------------
for i, chat in enumerate(st.session_state.chat_history):
    message(chat["text"], is_user=chat["is_user"], key=f"chat_{i}")

# -------------------- HANDLE SUBMIT --------------------
def handle_submit():
    query = st.session_state.user_input.strip()
    if not query:
        return

    st.session_state.chat_history.append({"text": query, "is_user": True})
    st.session_state.chat_history.append({
        "text": "🔎 Searching the web..." if is_web_search_enabled() else "Thinking...",
        "is_user": False
    })
    st.session_state.loading = True
    st.session_state.user_input = ""

st.text_input(
    "Type your message and press Enter",
    key="user_input",
    on_change=handle_submit
)

# -------------------- HELPERS --------------------
def is_web_search_enabled():
    if SEARCH_MODE == "always":
        return True
    elif SEARCH_MODE == "auto":
        return True  # model decides internally
    elif SEARCH_MODE == "manual":
        return st.session_state.web_search_enabled
    return False

# -------------------- PROCESS QUERY --------------------
if st.session_state.loading:
    try:
        user_query = next(m["text"] for m in reversed(st.session_state.chat_history) if m["is_user"])
        settings = st.session_state.web_search_settings

        # Reference URLs text for prompt
        ref_text = ""
        if settings["reference_urls"]:
            ref_text = "Prioritize these sources if relevant:\n" + "\n".join(settings["reference_urls"]) + "\n\n"

        # Prompt handling
        prompt = user_query
        if SEARCH_MODE == "always" or (SEARCH_MODE == "manual" and st.session_state.web_search_enabled):
            prompt = (
                "Please check the internet to answer the following query:\n"
                f"User location:\n{settings['location']}\n\n"
                f"{ref_text}"
                f"Query:\n{user_query}"
            )
        elif SEARCH_MODE == "auto" and is_web_search_enabled():
            prompt = (
                "Decide if web search is required and answer accordingly:\n"
                f"User location:\n{settings['location']}\n\n"
                f"{ref_text}"
                f"Query:\n{user_query}"
            )
        else:
            prompt = f"Answer the following using only your internal knowledge. Do NOT browse the internet.\n\nQuery:\n{user_query}"

        # -------------------- TOOLS --------------------
        tools = None
        if is_web_search_enabled():
            domains = []
            for url in settings["reference_urls"]:
                parsed = urlparse(url if url.startswith("http") else f"https://{url}")
                if parsed.netloc:
                    domains.append(parsed.netloc)
            tools = [{"type": "web_search", "filters": {"allowed_domains": list(set(domains))}}] if domains else [{"type": "web_search"}]

        # -------------------- OPENAI RESPONSE --------------------
        response = client.responses.create(
            model=model,
            tools=tools if is_web_search_enabled() else None,
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

        st.session_state.chat_history[-1] = {"text": answer, "is_user": False}

    except Exception as e:
        st.session_state.chat_history[-1] = {"text": f"❌ API error: {e}", "is_user": False}
    finally:
        st.session_state.loading = False
        st.rerun()
