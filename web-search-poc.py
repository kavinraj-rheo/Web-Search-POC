import os
import streamlit as st
from st_chat_message import message
from openai import OpenAI
from dotenv import load_dotenv
from urllib.parse import urlparse
import yaml

# Load .env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

# Load config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

SEARCH_MODE = config.get("search_mode", "manual").lower()  # always, auto, manual

st.markdown("""
<style>
div[data-testid="column"] { display: flex; align-items: center; }
.stButton > button { height: 40px; margin-top: 28px; }
div[data-baseweb="select"] { min-height: 48px; }
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="AI Search Assistant", page_icon="🔍", layout="centered")
st.title("🔍 AI Search Assistant")

DEFAULT_WEB_SEARCH_SETTINGS = {
    "reference_urls": [],
    "location": {"country": "India", "region": "", "city": "", "timezone": "Asia/Kolkata"},
    "context_size": "Medium",
}

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "loading" not in st.session_state:
    st.session_state.loading = False
if "web_search_enabled" not in st.session_state:
    st.session_state.web_search_enabled = SEARCH_MODE == "auto"
if "web_search_settings" not in st.session_state:
    st.session_state.web_search_settings = DEFAULT_WEB_SEARCH_SETTINGS.copy()

# ---------------- Helper: make URLs clickable ----------------
import re
def make_links_clickable(text):
    # Only convert plain URLs to clickable links
    url_pattern = re.compile(r"(https?://[^\s]+)")
    return url_pattern.sub(r'<a href="\1" target="_blank">\1</a>', text)

# ---------------- Web Search Configuration ----------------
@st.dialog("⚙️ Web Search Configuration")
def web_search_modal():
    settings = st.session_state.web_search_settings

    st.markdown("### 🌐 Reference URLs (optional)")
    reference_urls = st.text_area(
        label="Reference URLs",
        value="\n".join(settings["reference_urls"]),
        placeholder="https://openai.com/research"
    )

    st.markdown("### 📍 User Location")
    col1, col2 = st.columns(2)
    country = col1.selectbox("Country", options=["India", "USA", "UK"], index=0)
    region = col2.text_input("Region / State", value=settings["location"]["region"])
    city = st.text_input("City", value=settings["location"]["city"])
    timezone = st.selectbox("Timezone", options=["Asia/Kolkata", "UTC", "America/New_York"], index=0)

    st.markdown("### 🧠 Web Context Size")
    context_label = st.selectbox("How much web content should be used?", options=["Low", "Medium", "High"],
                                 index=["Low", "Medium", "High"].index(settings.get("context_size", "Medium")))

    st.divider()
    if st.button("💾 Save Configuration", use_container_width=True):
        st.session_state.web_search_settings = {
            "reference_urls": [u.strip() for u in reference_urls.splitlines() if u.strip()],
            "location": {"country": country, "region": region, "city": city, "timezone": timezone},
            "context_size": context_label  # Keep as camel case; lowercase only for prompt
        }
        st.rerun()

# ---------------- Layout ----------------
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    model = st.selectbox(label="Select Model", options=["gpt-4.1", "gpt-5"], index=0)
with col2:
    if st.button("⚙️ Configure"):
        web_search_modal()
with col3:
    if SEARCH_MODE == "manual":
        if st.button("🛑 Search ON" if st.session_state.web_search_enabled else "▶️ Search OFF"):
            st.session_state.web_search_enabled = not st.session_state.web_search_enabled
            st.rerun()

# ---------------- Display chat ----------------
for i, chat in enumerate(st.session_state.chat_history):
    # Only convert plain URLs to clickable links if not already HTML
    if "<a " not in chat["text"]:
        chat_text = make_links_clickable(chat["text"])
    else:
        chat_text = chat["text"]
    st.markdown(chat_text, unsafe_allow_html=True)

# ---------------- Handle user input ----------------
def handle_submit():
    query = st.session_state.user_input.strip()
    if not query:
        return

    st.session_state.chat_history.append({"text": query, "is_user": True})
    st.session_state.chat_history.append({
        "text": "🔎 Searching the web..." if st.session_state.web_search_enabled else "Thinking...",
        "is_user": False
    })
    st.session_state.loading = True
    st.session_state.user_input = ""

st.text_input("Type your message and press Enter", key="user_input", on_change=handle_submit)

# ---------------- Query OpenAI ----------------
if st.session_state.loading:
    try:
        user_query = next(m["text"] for m in reversed(st.session_state.chat_history) if m["is_user"])
        tools = None
        settings = st.session_state.web_search_settings

        # Build reference text
        ref_text = ""
        if settings["reference_urls"]:
            ref_text = "Prioritize these sources if relevant:\n" + "\n".join(settings["reference_urls"]) + "\n\n"

        # Build prompt based on search mode
        context_size_lower = settings.get("context_size", "Medium").lower()
        if SEARCH_MODE == "always" or (SEARCH_MODE == "manual" and st.session_state.web_search_enabled):
            prompt = f"Check the internet and answer the following:\nUser location:\n{settings['location']}\n\n{ref_text}Context size: {context_size_lower}\nQuery:\n{user_query}"
        elif SEARCH_MODE == "auto":
            prompt = f"You may search the web if required:\nUser location:\n{settings['location']}\n\n{ref_text}Context size: {context_size_lower}\nQuery:\n{user_query}"
        else:  # manual off
            prompt = f"{user_query}"  # just send query; web_search tool is off

        # Trusted domains
        if st.session_state.web_search_enabled:
            domains = []
            for url in settings["reference_urls"]:
                parsed = urlparse(url if url.startswith("http") else f"https://{url}")
                if parsed.netloc:
                    domains.append(parsed.netloc)

            if domains:
                tools = [{"type": "web_search", "filters": {"allowed_domains": list(set(domains))}}]
            else:
                tools = [{"type": "web_search"}]

        # Call OpenAI
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

        # Format citations with proper <a target="_blank">
        if citations:
            citation_html = "\n\n📚 **Citations**\n"
            for title, url in citations.items():
                citation_html += f'- <a href="{url}" target="_blank">{title}</a>\n'
            answer += citation_html

        # Make remaining plain URLs clickable
        if "<a " not in answer:
            answer = make_links_clickable(answer)

        st.session_state.chat_history[-1] = {"text": answer, "is_user": False}

    except Exception as e:
        st.session_state.chat_history[-1] = {"text": f"❌ API error: {e}", "is_user": False}
    finally:
        st.session_state.loading = False
        st.rerun()
