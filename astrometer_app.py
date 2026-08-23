import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime, date
import pytz
from timezonefinder import TimezoneFinder
from astral.sun import sun
from astral import LocationInfo
from supabase import create_client, Client
import time

# ====================== CONFIG ======================
st.set_page_config(page_title="AstroMeter Pro", page_icon="🌠", layout="wide")

# Load secrets
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
API_KEY = st.secrets["api"]["key"]
BASE_URL = "https://json.freeastrologyapi.com"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====================== AUTH HELPERS ======================

def init_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = init_supabase()

def sign_up(email: str, password: str):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        return res
    except Exception as e:
        st.error(f"Signup error: {str(e)}")
        return None

def sign_in(email: str, password: str):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res
    except Exception as e:
        st.error(f"Login error: {str(e)}")
        return None

def sign_out():
    try:
        supabase.auth.sign_out()
    except:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ====================== MAIN APP ======================

st.title("🌠 AstroMeter Pro")

# Initialize session state
if "user" not in st.session_state:
    st.session_state.user = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------- LOGIN / SIGNUP UI ----------
if not st.session_state.logged_in:

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        st.subheader("Login to your account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", type="primary", use_container_width=True):
            with st.spinner("Logging in..."):
                res = sign_in(email, password)
                if res and res.user:
                    st.session_state.user = res.user
                    st.session_state.logged_in = True
                    st.success("Login successful!")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    st.error("Invalid email or password")

    with tab2:
        st.subheader("Create a new account")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        password2 = st.text_input("Confirm Password", type="password", key="signup_password2")

        if st.button("Create Account", use_container_width=True):
            if password != password2:
                st.error("Passwords do not match")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            else:
                res = sign_up(email, password)
                if res and res.user:
                    st.success("Account created successfully! You can now login.")
                    st.info("If email confirmation is enabled, please check your inbox.")
                else:
                    st.error("Could not create account. Email may already be registered.")

# ---------- LOGGED IN UI ----------
else:
    user = st.session_state.user

    # Sidebar
    with st.sidebar:
        st.success(f"Logged in as:\n**{user.email}**")
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            sign_out()

    st.header("Welcome to AstroMeter Pro")
    st.write("You are successfully logged in.")

    # ---- Your main app content starts here ----
    st.info("Main application content will appear here (Birth Profiles, Calculate Luck, etc.)")

    # Temporary test
    st.write("User ID:", user.id)
# ====================== DATABASE HELPERS ======================

def get_user_profiles(user_id):
    res = supabase.table("birth_profiles").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return res.data

def save_profile(user_id, data):
    res = supabase.table("birth_profiles").insert({
        "user_id": user_id,
        **data
    }).execute()
    return res.data[0] if res.data else None

def get_natal_cache(profile_id):
    res = supabase.table("natal_cache").select("*").eq("profile_id", profile_id).execute()
    return res.data[0] if res.data else None

def save_natal_cache(profile_id, natal_json, maha_json):
    supabase.table("natal_cache").upsert({
        "profile_id": profile_id,
        "natal_json": natal_json,
        "maha_dasha_json": maha_json,
        "updated_at": datetime.utcnow().isoformat()
    }).execute()

# ====================== ASTROLOGY HELPERS ======================

def get_timezone(lat, lon):
    tf = TimezoneFinder()
    return tf.timezone_at(lng=lon, lat=lat) or "Asia/Kolkata"

@st.cache_data(ttl=60*30)
def get_planets_extended(year, month, day, hour, minute, second, lat, lon, tz_offset):
    url = f"{BASE_URL}/planets/extended"
    payload = {
        "year": year, "month": month, "date": day,
        "hours": hour, "minutes": minute, "seconds": second,
        "latitude": lat, "longitude": lon, "timezone": tz_offset,
        "settings": {"observation_point": "topocentric", "ayanamsha": "lahiri"}
    }
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}

    for attempt in range(3):
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code == 429:
            time.sleep((attempt + 1) * 8)
            continue
        r.raise_for_status()
        return r.json().get("output", {})
    raise Exception("API rate limit exceeded")

def get_maha_dashas(year, month, day, hour, minute, second, lat, lon, tz_offset):
    url = f"{BASE_URL}/vimsottari/maha-dasas"
    payload = {
        "year": year, "month": month, "date": day,
        "hours": hour, "minutes": minute, "seconds": second,
        "latitude": lat, "longitude": lon, "timezone": tz_offset,
        "config": {"observation_point": "topocentric", "ayanamsha": "lahiri"}
    }
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    r = requests.post(url, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    return json.loads(r.json().get("output", "{}"))

def planets_to_df(data):
    rows = []
    for name, info in data.items():
        rows.append({
            "Planet": name,
            "House": info.get("house_number"),
            "Zodiac_Sign": info.get("zodiac_sign_name"),
            "Nakshatra": info.get("nakshatra_name"),
            "Dasha_Lord": info.get("nakshatra_vimsottari_lord"),
            "FullDeg": info.get("fullDegree"),
            "Retro": info.get("isRetro")
        })
    return pd.DataFrame(rows)

# ====================== UI ======================

st.title("🌠 AstroMeter Pro")

# ---------- AUTH SECTION ----------
if "user" not in st.session_state:
    st.session_state.user = None

user = get_current_user()
if user and user.user:
    st.session_state.user = user.user
else:
    st.session_state.user = None

if st.session_state.user is None:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", type="primary"):
            res = sign_in(email, password)
            if res and res.user:
                st.session_state.user = res.user
                st.success("Logged in successfully!")
                st.rerun()

    with tab2:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_pass")
        if st.button("Create Account"):
            res = sign_up(email, password)
            if res and res.user:
                st.success("Account created! Please check your email to confirm, then login.")
else:
    # ---------- LOGGED IN ----------
    st.sidebar.success(f"Logged in as: {st.session_state.user.email}")
    if st.sidebar.button("Logout"):
        sign_out()

    user_id = st.session_state.user.id
    profiles = get_user_profiles(user_id)

    st.subheader("Your Birth Profiles")

    if profiles:
        profile_names = [f"{p['name']} ({p['year']}-{p['month']:02d}-{p['day']:02d})" for p in profiles]
        selected = st.selectbox("Select a profile", profile_names)
        selected_profile = profiles[profile_names.index(selected)]
    else:
        st.info("No profiles yet. Add one below.")
        selected_profile = None

    with st.expander("➕ Add New Birth Profile", expanded=not profiles):
        with st.form("new_profile"):
            name = st.text_input("Profile Name (e.g. Myself, Mom, Client)")
            c1, c2, c3 = st.columns(3)
            year = c1.number_input("Year", 1900, 2100, 1996)
            month = c2.number_input("Month", 1, 12, 9)
            day = c3.number_input("Day", 1, 31, 25)
            c4, c5, c6 = st.columns(3)
            hour = c4.number_input("Hour", 0, 23, 7)
            minute = c5.number_input("Minute", 0, 59, 15)
            second = c6.number_input("Second", 0, 59, 0)
            lat = st.number_input("Latitude", value=21.146633, format="%.6f")
            lon = st.number_input("Longitude", value=79.088860, format="%.6f")
            place = st.text_input("Place Name (optional)")

            if st.form_submit_button("Save Profile"):
                data = {
                    "name": name,
                    "year": year, "month": month, "day": day,
                    "hour": hour, "minute": minute, "second": second,
                    "latitude": lat, "longitude": lon,
                    "place_name": place
                }
                save_profile(user_id, data)
                st.success("Profile saved!")
                st.rerun()

    # ---------- CALCULATE ----------
    if selected_profile and st.button("🔮 Calculate Current Luck", type="primary"):
        with st.spinner("Consulting the cosmos..."):
            p = selected_profile
            tz_str = get_timezone(p["latitude"], p["longitude"])
            tz = pytz.timezone(tz_str)
            now = datetime.now(tz)
            utc_offset = now.utcoffset().total_seconds() / 3600

            # Try cache first
            cache = get_natal_cache(p["id"])
            if cache:
                natal_raw = cache["natal_json"]
                maha_dict = cache["maha_dasha_json"]
                st.toast("Using cached natal data ⚡")
            else:
                natal_raw = get_planets_extended(
                    p["year"], p["month"], p["day"],
                    p["hour"], p["minute"], p["second"],
                    p["latitude"], p["longitude"], utc_offset
                )
                maha_dict = get_maha_dashas(
                    p["year"], p["month"], p["day"],
                    p["hour"], p["minute"], p["second"],
                    p["latitude"], p["longitude"], utc_offset
                )
                save_natal_cache(p["id"], natal_raw, maha_dict)

            natal_df = planets_to_df(natal_raw)

            # Live transit
            transit_raw = get_planets_extended(
                now.year, now.month, now.day,
                now.hour, now.minute, now.second,
                p["latitude"], p["longitude"], utc_offset
            )
            transit_df = planets_to_df(transit_raw)

            # Current Maha Dasha
            current_maha = "Unknown"
            for info in maha_dict.values():
                start = datetime.fromisoformat(info["start_time"].replace(" ", "T"))
                end = datetime.fromisoformat(info["end_time"].replace(" ", "T"))
                if start.tzinfo is None:
                    start = tz.localize(start)
                    end = tz.localize(end)
                if start <= now <= end:
                    current_maha = info["Lord"]
                    break

            st.success(f"**Current Maha-Dasha:** {current_maha}")
            st.dataframe(natal_df, use_container_width=True)
            st.dataframe(transit_df, use_container_width=True)
