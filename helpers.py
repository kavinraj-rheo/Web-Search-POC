import pycountry #type:ignore
import pytz 



# -------------------- HELPERS --------------------
def country_to_alpha2(name: str) -> str | None:
    try:
        return pycountry.countries.lookup(name).alpha_2
    except LookupError:
        return None

def get_timezones_for_country(country_name: str) -> list[str]:
    code = country_to_alpha2(country_name)
    if not code:
        return pytz.all_timezones
    return pytz.country_timezones.get(code, pytz.all_timezones)

def is_web_search_enabled(SEARCH_MODE, st):
    if SEARCH_MODE == "always":
        return True
    elif SEARCH_MODE == "auto":
        return True
    elif SEARCH_MODE == "manual":
        return st.session_state.web_search_enabled
    return False
