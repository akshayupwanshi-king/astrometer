import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder
from supabase import create_client
import time

# ====================== PAGE CONFIG ======================
st.set_page_config(page_title="AstroMeter Pro", page_icon="🌠", layout="wide")

# ====================== SECRETS ======================
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
API_KEY = st.secrets["api"]["key"]
BASE_URL = "https://json.freeastrologyapi.com"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# Restore session if tokens exist
if "access_token" in st.session_state and "refresh_token" in st.session_state:
    try:
        supabase.auth.set_session(
            st.session_state["access_token"],
            st.session_state["refresh_token"]
        )
    except:
        pass

# ====================== AUTH FUNCTIONS ======================
def sign_up(email, password):
    try:
        return supabase.auth.sign_up({"email": email, "password": password})
    except Exception as e:
        st.error(f"Signup failed: {e}")
        return None

def sign_in(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res and res.session:
            # Save tokens in session_state
            st.session_state["access_token"] = res.session.access_token
            st.session_state["refresh_token"] = res.session.refresh_token
            supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
        return res
    except Exception as e:
        st.error(f"Login failed: {e}")
        return None

def sign_out():
    try:
        supabase.auth.sign_out()
    except:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ====================== DATABASE FUNCTIONS ======================
def get_user_profiles(user_id):
    res = supabase.table("birth_profiles").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return res.data

def save_profile(user_id, data):
    res = supabase.table("birth_profiles").insert({"user_id": user_id, **data}).execute()
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

# ====================== ASTROLOGY FUNCTIONS ======================
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

    for attempt in range(4):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=25)
            
            if r.status_code == 429:
                wait_time = (attempt + 1) * 10
                st.warning(f"API rate limit hit. Waiting {wait_time} seconds... (try {attempt+1}/4)")
                time.sleep(wait_time)
                continue
                
            r.raise_for_status()
            return json.loads(r.json().get("output", "{}"))
            
        except Exception as e:
            if attempt == 3:
                raise e
            time.sleep(5)
    
    raise Exception("Failed to get Maha-Dasha after multiple retries due to rate limiting.")

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

signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

good_houses = {1: 30, 5: 20, 9: 20, 2: 10, 4: 10, 7: 10, 11: 10}

def get_house_from_sign(curr_sign, ref_sign):
    try:
        return (signs.index(curr_sign) - signs.index(ref_sign)) % 12 + 1
    except:
        return 6

def calculate_luck_score(natal_df, transit_df, current_maha):
    try:
        moon_sign = natal_df[natal_df['Planet'] == 'Moon']['Zodiac_Sign'].values[0]
        asc_sign  = natal_df[natal_df['Planet'] == 'Ascendant']['Zodiac_Sign'].values[0]

        # Jupiter
        jup_sign = transit_df[transit_df['Planet'] == 'Jupiter']['Zodiac_Sign'].values[0]
        jup_h = get_house_from_sign(jup_sign, moon_sign)
        jup_score = good_houses.get(jup_h, 5)

        # Venus
        ven_sign = transit_df[transit_df['Planet'] == 'Venus']['Zodiac_Sign'].values[0]
        ven_h = get_house_from_sign(ven_sign, moon_sign)
        ven_score = good_houses.get(ven_h, 5)

        # Moon
        moon_sign_t = transit_df[transit_df['Planet'] == 'Moon']['Zodiac_Sign'].values[0]
        moon_h = get_house_from_sign(moon_sign_t, asc_sign)
        moon_score = good_houses.get(moon_h, 5)

        # Saturn malefic
        sat_sign = transit_df[transit_df['Planet'] == 'Saturn']['Zodiac_Sign'].values[0]
        sat_h = get_house_from_sign(sat_sign, moon_sign)
        malefic = -15 if sat_h in [1, 5, 9] else 0

        # Dasha bonus
        dasha_bonus = 18 if current_maha in ['Jupiter', 'Venus', 'Mercury', 'Moon'] else 8

        total = min(max(jup_score + ven_score + moon_score + malefic + dasha_bonus, 5), 100)
        return total, jup_h, ven_h, moon_h
    except Exception as e:
        return 40, 6, 6, 6

# ====================== SESSION STATE ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

# ====================== APP START ======================
st.title("🌠 AstroMeter Pro")

# ---------- LOGIN / SIGNUP ----------
if not st.session_state.logged_in:

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login", type="primary", use_container_width=True):
            res = sign_in(email, password)
            if res and res.user:
                st.session_state.user = res.user
                st.session_state.logged_in = True
                st.success("Login successful!")
                time.sleep(0.6)
                st.rerun()

    with tab2:
        st.subheader("Create Account")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_pass")
        password2 = st.text_input("Confirm Password", type="password", key="signup_pass2")

        if st.button("Create Account", use_container_width=True):
            if password != password2:
                st.error("Passwords do not match")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            else:
                res = sign_up(email, password)
                if res and res.user:
                    st.success("Account created successfully! You can now login.")
                else:
                    st.error("Could not create account.")

# ---------- LOGGED IN ----------
else:
    user = st.session_state.user
    user_id = user.id

    with st.sidebar:
        st.success(f"Logged in as:\n**{user.email}**")
        if st.button("Logout", use_container_width=True):
            sign_out()

    st.header("Your Birth Profiles")

    profiles = get_user_profiles(user_id)

    if profiles:
        profile_names = [f"{p['name']} ({p['year']}-{p['month']:02d}-{p['day']:02d})" for p in profiles]
        selected = st.selectbox("Select a profile", profile_names)
        selected_profile = profiles[profile_names.index(selected)]
    else:
        st.info("No profiles yet. Please add one below.")
        selected_profile = None

    with st.expander("➕ Add New Birth Profile", expanded=not bool(profiles)):
        with st.form("new_profile"):
            name = st.text_input("Profile Name (e.g. Myself, Mom)")
            c1, c2, c3 = st.columns(3)
            year = c1.number_input("Year", 1900, 2100, 1996)
            month = c2.number_input("Month", 1, 12, 9)
            day = c3.number_input("Day", 1, 31, 25)
            c4, c5, c6 = st.columns(3)
            hour = c4.number_input("Hour (24h)", 0, 23, 7)
            minute = c5.number_input("Minute", 0, 59, 15)
            second = c6.number_input("Second", 0, 59, 0)
            lat = st.number_input("Latitude", value=21.146633, format="%.6f")
            lon = st.number_input("Longitude", value=79.088860, format="%.6f")
            place = st.text_input("Place Name (optional)")

            if st.form_submit_button("Save Profile"):
                data = {
                    "name": name,
                    "year": int(year), "month": int(month), "day": int(day),
                    "hour": int(hour), "minute": int(minute), "second": int(second),
                    "latitude": float(lat), "longitude": float(lon),
                    "place_name": place
                }
                save_profile(user_id, data)
                st.success("Profile saved successfully!")
                time.sleep(0.8)
                st.rerun()

    # ---------- CALCULATE LUCK ----------
    if selected_profile and st.button("🔮 Calculate Current Luck", type="primary", use_container_width=True):
        with st.spinner("Consulting the cosmos..."):
            try:
                p = selected_profile
                tz_str = get_timezone(p["latitude"], p["longitude"])
                tz = pytz.timezone(tz_str)
                now = datetime.now(tz)
                utc_offset = now.utcoffset().total_seconds() / 3600

                # Check cache first
                cache = get_natal_cache(p["id"])
                if cache:
                    natal_raw = cache["natal_json"]
                    maha_dict = cache["maha_dasha_json"]
                    st.toast("Using cached natal data ⚡", icon="⚡")
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

                # Current transit
                transit_raw = get_planets_extended(
                    now.year, now.month, now.day,
                    now.hour, now.minute, now.second,
                    p["latitude"], p["longitude"], utc_offset
                )
                transit_df = planets_to_df(transit_raw)

                # Find current Maha Dasha
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

                # ---- Luck Meter ----
                score, jup_h, ven_h, moon_h = calculate_luck_score(natal_df, transit_df, current_maha)

                if score >= 67:
                    zone = "🟢 High"
                    color = "green"
                    message = "Excellent time for important actions!"
                elif score >= 34:
                    zone = "🟡 Moderate"
                    color = "orange"
                    message = "Steady progress. Avoid major risks."
                else:
                    zone = "🔴 Low"
                    color = "red"
                    message = "Low energy period. Better to wait."

                st.markdown(f"### Luck Score: **{score}/100**  —  {zone}")
                st.progress(score / 100)
                st.info(f"**{message}**")

                st.caption(f"Jupiter in {jup_h}th from Moon • Venus in {ven_h}th from Moon • Moon in {moon_h}th from Ascendant")

                # Charts
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Natal Chart")
                    st.dataframe(natal_df, use_container_width=True)
                with col2:
                    st.subheader("Current Transit")
                    st.dataframe(transit_df, use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Natal Chart")
                    st.dataframe(natal_df, use_container_width=True)
                with col2:
                    st.subheader("Current Transit")
                    st.dataframe(transit_df, use_container_width=True)

            except Exception as e:
                st.error(f"Error during calculation: {str(e)}")
