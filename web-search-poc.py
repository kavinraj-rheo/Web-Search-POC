import os
import yaml # type: ignore
import pycountry # type: ignore
import pytz # type: ignore
import streamlit as st # type: ignore
from st_chat_message import message # type: ignore
from openai import OpenAI # type: ignore
from dotenv import load_dotenv # type: ignore
from urllib.parse import urlparse

from helpers import country_to_alpha2, get_timezones_for_country, is_web_search_enabled

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

# -------------------- MODEL SUPPORT --------------------
ALL_MODELS = config.get("all_models")
WEB_SEARCH_SUPPORTED_MODELS = config.get("web_search_supported_models")
# -------------------- STREAMLIT STYLING --------------------
MANUAL_CSS = """
<style>
div[data-testid="column"] {
    display: flex;
    align-items: center;
}
.stButton > button {
    height: 40px;
    margin-top: 28px;
}
div[data-baseweb="select"] {
    min-height: 48px;
}
</style>
"""

ENABLED_SEARCH_CSS = """
<style>
div[data-testid="column"] {
    display: flex;
    align-items: center;
}
.stButton > button {
    height: 40px;
    margin-top: 28px;
    min-width: 274px;
}
div[data-baseweb="select"] {
    min-height: 48px;
}
</style>
"""

if SEARCH_MODE == "manual":
    st.markdown(MANUAL_CSS, unsafe_allow_html=True)
else:
    st.markdown(ENABLED_SEARCH_CSS, unsafe_allow_html=True)

st.set_page_config(
    page_title="O-Rheo Search Assistant",
    page_icon="🔍",
    layout="centered",
)

st.title("🔍 O-Rheo Search Assistant")

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
@st.dialog("⚙️ Configure Web Search Tool")
def web_search_modal():
    settings = st.session_state.web_search_settings

    st.markdown("### 🌐 Reference URLs (optional)")
    reference_urls = st.text_area(
        "Reference URLs",
        value="\n".join(settings["reference_urls"]),
        placeholder="https://openai.com/research",
    )

    st.markdown("### 📍 User Location")
    col1, col2 = st.columns(2)

    countries = sorted([c.name for c in pycountry.countries])
    country = col1.selectbox(
        "Country",
        options=countries,
        index=countries.index(settings["location"].get("country", "India")),
    )

    region = col2.text_input(
        "Region / State",
        value=settings["location"].get("region", ""),
    )

    city = st.text_input(
        "City",
        value=settings["location"].get("city", ""),
    )

    available_timezones = sorted(get_timezones_for_country(country))
    default_tz = settings["location"].get("timezone", "Asia/Kolkata")
    if default_tz not in available_timezones:
        default_tz = available_timezones[0]

    timezone = st.selectbox(
        "Timezone",
        options=available_timezones,
        index=available_timezones.index(default_tz),
    )

    st.markdown("### 🧠 Web Context Size")
    context_label = st.selectbox(
        "How much web content should be used?",
        options=["Low", "Medium", "High"],
        index=["Low", "Medium", "High"].index(
            settings.get("context_size", "medium").capitalize()
        ),
    )

    if st.button("💾 Save Configuration", use_container_width=True):
        st.session_state.web_search_settings = {
            "reference_urls": [u.strip() for u in reference_urls.splitlines() if u.strip()],
            "location": {
                "country": country,
                "region": region,
                "city": city,
                "timezone": timezone,
            },
            "context_size": context_label.lower(),
        }
        st.rerun()

# -------------------- TOP BAR --------------------
col1, col2, col3 = st.columns([3, 1, 1])

with col1:
    model = st.selectbox(
        "Select Model",
        options=ALL_MODELS,
        index=ALL_MODELS.index("gpt-4.1"),
    )

with col2:
    if st.button("⚙️  Configure"):
        web_search_modal()

with col3:
    if SEARCH_MODE == "manual":
        if st.button("🛑 Search ON" if st.session_state.web_search_enabled else "▶️ Search OFF"):
            st.session_state.web_search_enabled = not st.session_state.web_search_enabled
            st.rerun()

# -------------------- MODEL / SEARCH VALIDATION --------------------
web_active = is_web_search_enabled(SEARCH_MODE, st)
model_supports_web = model in WEB_SEARCH_SUPPORTED_MODELS

if web_active and not model_supports_web:
    st.warning(
        "⚠️ The selected model does not support Web Search.\n\n"
        "Please turn off Web Search or choose a supported model."
    )

# -------------------- CHAT HISTORY --------------------
for i, chat in enumerate(st.session_state.chat_history):
    message(chat["text"], is_user=chat["is_user"], key=f"chat_{i}")

# -------------------- HANDLE SUBMIT --------------------
def handle_submit():
    query = st.session_state.user_input.strip()
    if not query:
        return

    st.session_state.chat_history.append({"text": query, "is_user": True})
    st.session_state.chat_history.append({"text": "Thinking...", "is_user": False})
    st.session_state.loading = True
    st.session_state.user_input = ""

st.text_input(
    "Type your message and press Enter",
    key="user_input",
    on_change=handle_submit,
    disabled=web_active and not model_supports_web,
)

# -------------------- PROCESS QUERY --------------------
if st.session_state.loading:
    try:
        user_query = next(
            m["text"] for m in reversed(st.session_state.chat_history) if m["is_user"]
        )
        settings = st.session_state.web_search_settings

        ref_text = ""
        if settings["reference_urls"]:
            ref_text = (
                "Prioritize these sources if relevant:\n"
                + "\n".join(settings["reference_urls"])
                + "\n\n"
            )

        if SEARCH_MODE == "always" or (
            SEARCH_MODE == "manual" and st.session_state.web_search_enabled
        ):
            prompt = (
                "Please check the internet to answer the following query:\n"
                f"User timezone:\n{settings['location']['timezone']}\n\n"
                f"{ref_text}"
                f"Query:\n{user_query}"
            )
        elif SEARCH_MODE == "auto":
            prompt = (
                "You may search the web if required:\n"
                f"User timezone:\n{settings['location']['timezone']}\n\n"
                f"{ref_text}"
                f"Query:\n{user_query}"
            )
        else:
            prompt = (
                "Answer using only your internal knowledge. "
                "Do NOT browse the internet.\n\n"
                f"Query:\n{user_query}"
            )

        tools = None
        if is_web_search_enabled(SEARCH_MODE, st):
            domains = []
            for url in settings["reference_urls"]:
                parsed = urlparse(url if url.startswith("http") else f"https://{url}")
                if parsed.netloc:
                    domains.append(parsed.netloc)

            tools = (
                [{"type": "web_search", "filters": {"allowed_domains": list(set(domains))}}]
                if domains
                else [{"type": "web_search"}]
            )

            loc = settings["location"].copy()
            loc["country"] = country_to_alpha2(loc["country"])
            loc["type"] = "approximate"
            loc.pop("timezone", None)

            tools[0]["user_location"] = loc

        response = client.responses.create(
            model=model,
            input=prompt,
            tools=tools if is_web_search_enabled(SEARCH_MODE, st) else None,
        )

        web_used = any(out.type == "web_search_call" for out in response.output)
        answer = response.output_text

        if web_used:
            answer = "🔎 _Searched the web for results._\n\n" + answer

        citations = {}
        for out in response.output:
            if out.type == "message":
                for item in out.content:
                    for ann in item.annotations:
                        citations[ann.title] = ann.url

        if citations:
            answer += "\n\n📚 **Citations**\n"
            for title, url in citations.items():
                answer += f'- <a href="{url}" target="_blank">{title}</a>\n'

        st.session_state.chat_history[-1] = {"text": answer, "is_user": False}

    except Exception as e:
        st.session_state.chat_history[-1] = {
            "text": f"❌ API error: {e}",
            "is_user": False,
        }
    finally:
        st.session_state.loading = False
        st.rerun()
