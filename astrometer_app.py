import streamlit as st
import time
from datetime import datetime
import pytz
from supabase import create_client
import streamlit.components.v1 as components
import pandas as pd

from astro_engine import (
    get_timezone,
    get_planets_extended,
    get_maha_dashas,
    planets_to_df,
    calculate_luck_score,
    get_current_maha
)

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="AstroMeter Pro",
    page_icon="🌠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== COSMIC THEME ======================
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(ellipse at bottom, #1B2735 0%, #090A0F 100%);
        color: #E0E6F0;
    }
    h1, h2, h3 {
        color: #E0D4FF !important;
        text-shadow: 0 0 12px rgba(180, 140, 255, 0.4);
    }
    .stButton > button {
        background: linear-gradient(135deg, #6B4EFF, #9B6DFF);
        color: white;
        border: none;
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(107, 78, 255, 0.5);
    }
    section[data-testid="stSidebar"] {
        background: rgba(10, 12, 25, 0.95);
        border-right: 1px solid rgba(140, 100, 255, 0.15);
    }
    .stSuccess, .stInfo {
        background: rgba(30, 20, 60, 0.6);
        border: 1px solid rgba(140, 100, 255, 0.3);
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ====================== LOAD CITIES ======================
@st.cache_data
def load_cities():
    df = pd.read_csv("worldcities.csv")
    df = df[["city_ascii", "lat", "lng", "country"]].dropna()
    df["display"] = df["city_ascii"] + ", " + df["country"]
    return df.reset_index(drop=True)

cities_df = load_cities()

# ====================== SECRETS ======================
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
API_KEY = st.secrets["api"]["key"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Restore session
if "access_token" in st.session_state and "refresh_token" in st.session_state:
    try:
        supabase.auth.set_session(
            st.session_state["access_token"],
            st.session_state["refresh_token"]
        )
    except:
        pass

# ====================== AUTH ======================
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

# ====================== DATABASE ======================
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

# ====================== SESSION ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "view" not in st.session_state:
    st.session_state.view = "meter"
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ====================== APP ======================
st.markdown("<h1 style='text-align:center;'>🌠 AstroMeter Pro</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#A78BFA; margin-top:-10px;'>Cosmic Luck Intelligence</p>", unsafe_allow_html=True)

# ---------- LOGIN ----------
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["✦ Login", "✦ Create Account"])

        with tab1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Enter the Cosmos", type="primary", use_container_width=True):
                res = sign_in(email, password)
                if res and res.user:
                    st.session_state.user = res.user
                    st.session_state.logged_in = True
                    st.success("Welcome back, traveler")
                    time.sleep(0.7)
                    st.rerun()

        with tab2:
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_pass")
            password2 = st.text_input("Confirm Password", type="password", key="signup_pass2")
            if st.button("Begin Your Journey", use_container_width=True):
                if password != password2:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    res = sign_up(email, password)
                    if res and res.user:
                        st.success("Account created! You can now login.")
                    else:
                        st.error("Could not create account.")

# ---------- LOGGED IN ----------
else:
    user = st.session_state.user
    user_id = user.id

    # Sidebar
    with st.sidebar:
        st.markdown("### 🪐 Navigation")
        if st.button("🎯 Luck Meter", use_container_width=True):
            st.session_state.view = "meter"
            st.rerun()
        if st.button("📜 Birth Charts", use_container_width=True):
            st.session_state.view = "charts"
            st.rerun()
        st.markdown("---")
        st.success(f"**{user.email}**")
        if st.button("Logout", use_container_width=True):
            sign_out()

    # ====================== METER AT THE TOP ======================
    if st.session_state.last_result and st.session_state.view == "meter":
        result = st.session_state.last_result
        score = result["score"]
        current_maha = result["current_maha"]

        if score >= 67:
            zone, zone_color, message = "High", "#00E676", "The cosmos favors bold action"
        elif score >= 34:
            zone, zone_color, message = "Moderate", "#FFD600", "Steady energy — move with care"
        else:
            zone, zone_color, message = "Low", "#FF1744", "The stars advise patience"

        final_angle = (score / 100) * 180

        meter_html = f"""
        <div style="display:flex; flex-direction:column; align-items:center; padding: 5px 0 15px 0; font-family: 'Segoe UI', system-ui, sans-serif;">
          
          <div style="font-size:13px; color:#A78BFA; letter-spacing:3px; margin-bottom:6px; opacity:0.9;">
            CURRENT MAHA-DASHA • {current_maha.upper()}
          </div>

          <div style="position:relative; width:320px; height:180px;">
            <svg width="320" height="180" viewBox="0 0 320 180">
              <path d="M 30 160 A 130 130 0 0 1 290 160" fill="none" stroke="#2A2A3A" stroke-width="22" stroke-linecap="round"/>
              <path d="M 30 160 A 130 130 0 0 1 110 48" fill="none" stroke="#FF1744" stroke-width="22" stroke-linecap="round"/>
              <path d="M 110 48 A 130 130 0 0 1 210 48" fill="none" stroke="#FFD600" stroke-width="22" stroke-linecap="round"/>
              <path d="M 210 48 A 130 130 0 0 1 290 160" fill="none" stroke="#00E676" stroke-width="22" stroke-linecap="round"/>
            </svg>

            <div id="needle" style="
              position:absolute; bottom:18px; left:50%; width:5px; height:125px;
              background: linear-gradient(to top, #E0D4FF, #ffffff);
              transform-origin: bottom center;
              transform: translateX(-50%) rotate(-90deg);
              border-radius: 4px; z-index: 10;
              box-shadow: 0 0 15px rgba(224, 212, 255, 0.7);
            "></div>

            <div style="
              position:absolute; bottom:8px; left:50%; transform: translateX(-50%);
              width:24px; height:24px; background: #E0D4FF; border-radius: 50%;
              border: 3px solid #0f0f1a; box-shadow: 0 0 18px rgba(224,212,255,0.8); z-index: 20;
            "></div>
          </div>

          <div id="score" style="
            font-size: 78px; font-weight: 800; color: {zone_color};
            margin-top: -20px; line-height: 1;
            text-shadow: 0 0 40px {zone_color}66;
          ">0</div>

          <div style="font-size: 20px; font-weight: 600; color: {zone_color}; letter-spacing: 5px; margin-top: 2px;">
            {zone.upper()}
          </div>

          <div style="margin-top: 14px; font-size: 15px; color: #C4B5FD; text-align: center; max-width: 340px;">
            {message}
          </div>
        </div>

        <script>
          const needle = document.getElementById('needle');
          const scoreEl = document.getElementById('score');
          const targetAngle = {final_angle - 90};
          const targetScore = {score};

          setTimeout(() => {{
            needle.style.transition = 'transform 1.8s cubic-bezier(0.22, 1, 0.36, 1)';
            needle.style.transform = `translateX(-50%) rotate(${{targetAngle}}deg)`;
          }}, 80);

          let current = 0;
          const duration = 1800;
          const start = performance.now();

          function animateScore(time) {{
            const progress = Math.min((time - start) / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3);
            current = Math.floor(ease * targetScore);
            scoreEl.innerText = current;
            if (progress < 1) requestAnimationFrame(animateScore);
          }}
          requestAnimationFrame(animateScore);
        </script>
        """
        components.html(meter_html, height=400)

        st.caption(f"Jupiter → {result['jup_h']}th from Moon  •  Venus → {result['ven_h']}th from Moon  •  Moon → {result['moon_h']}th from Ascendant")
        st.markdown("---")

    # ====================== PROFILE SECTION ======================
    profiles = get_user_profiles(user_id)

    if profiles:
        profile_names = [f"{p['name']} ({p['year']}-{p['month']:02d}-{p['day']:02d})" for p in profiles]
        selected = st.selectbox("Select Birth Profile", profile_names)
        selected_profile = profiles[profile_names.index(selected)]

        col_edit, col_del = st.columns(2)
        with col_edit:
            if st.button("✏️ Edit Profile", use_container_width=True):
                st.session_state.edit_profile = selected_profile
        with col_del:
            if st.button("🗑️ Delete Profile", use_container_width=True):
                supabase.table("birth_profiles").delete().eq("id", selected_profile["id"]).execute()
                st.success("Profile deleted")
                time.sleep(0.6)
                st.rerun()
    else:
        st.info("No birth profiles yet.")
        selected_profile = None

    # ====================== ADD / EDIT PROFILE ======================
    edit_mode = "edit_profile" in st.session_state and st.session_state.edit_profile is not None

    with st.expander("➕ Add / Edit Birth Profile", expanded=edit_mode or not profiles):
        st.markdown("**Search City**")
        city_query = st.text_input("Type city name", placeholder="e.g. Nagpur, Tokyo, Mumbai...", key="city_search")

        selected_city = None
        lat = lon = None

        if city_query and len(city_query.strip()) >= 2:
            mask = cities_df["city_ascii"].str.contains(city_query.strip(), case=False, na=False)
            matches = cities_df[mask].head(15)

            if not matches.empty:
                options = matches["display"].tolist()
                chosen = st.selectbox("Select from suggestions", options, key="city_choice")
                selected_city = matches[matches["display"] == chosen].iloc[0]
                lat = float(selected_city["lat"])
                lon = float(selected_city["lng"])
                st.success(f"📍 Selected: **{selected_city['display']}** → `{lat:.4f}, {lon:.4f}`")
            else:
                st.warning("No cities found. Try a different spelling.")

        with st.form("profile_form"):
            default = st.session_state.get("edit_profile", {})

            name = st.text_input("Profile Name", value=default.get("name", ""))
            c1, c2, c3 = st.columns(3)
            year = c1.number_input("Year", 1900, 2100, value=default.get("year", 1996))
            month = c2.number_input("Month", 1, 12, value=default.get("month", 9))
            day = c3.number_input("Day", 1, 31, value=default.get("day", 25))
            c4, c5, c6 = st.columns(3)
            hour = c4.number_input("Hour (24h)", 0, 23, value=default.get("hour", 7))
            minute = c5.number_input("Minute", 0, 59, value=default.get("minute", 15))
            second = c6.number_input("Second", 0, 59, value=default.get("second", 0))
            place_name = st.text_input("Place Name (optional)", value=default.get("place_name", ""))

            if lat is None and default:
                lat = default.get("latitude")
                lon = default.get("longitude")

            submitted = st.form_submit_button("💾 Save Profile", type="primary")

            if submitted:
                if not name:
                    st.error("Please enter a profile name")
                elif lat is None or lon is None:
                    st.error("Please select a city from the suggestions above")
                else:
                    data = {
                        "name": name,
                        "year": int(year), "month": int(month), "day": int(day),
                        "hour": int(hour), "minute": int(minute), "second": int(second),
                        "latitude": float(lat), "longitude": float(lon),
                        "place_name": place_name or (selected_city["display"] if selected_city is not None else "")
                    }

                    if edit_mode:
                        supabase.table("birth_profiles").update(data).eq("id", default["id"]).execute()
                        supabase.table("natal_cache").delete().eq("profile_id", default["id"]).execute()
                        if "last_result" in st.session_state:
                            del st.session_state.last_result
                        st.success("Profile updated! Please calculate again.")
                        del st.session_state.edit_profile
                    else:
                        save_profile(user_id, data)
                        st.success("Profile saved!")

                    time.sleep(0.8)
                    st.rerun()

    # ====================== CALCULATE BUTTON ======================
    if selected_profile and st.button("🔮 Calculate Current Luck", type="primary", use_container_width=True):
        with st.spinner("Aligning with the stars..."):
            try:
                p = selected_profile
                tz_str = get_timezone(p["latitude"], p["longitude"])
                tz = pytz.timezone(tz_str)
                now = datetime.now(tz)
                utc_offset = now.utcoffset().total_seconds() / 3600

                cache = get_natal_cache(p["id"])
                if cache:
                    natal_raw = cache["natal_json"]
                    maha_dict = cache["maha_dasha_json"]
                else:
                    natal_raw = get_planets_extended(
                        p["year"], p["month"], p["day"],
                        p["hour"], p["minute"], p["second"],
                        p["latitude"], p["longitude"], utc_offset, API_KEY
                    )
                    maha_dict = get_maha_dashas(
                        p["year"], p["month"], p["day"],
                        p["hour"], p["minute"], p["second"],
                        p["latitude"], p["longitude"], utc_offset, API_KEY
                    )
                    save_natal_cache(p["id"], natal_raw, maha_dict)

                natal_df = planets_to_df(natal_raw)
                transit_raw = get_planets_extended(
                    now.year, now.month, now.day,
                    now.hour, now.minute, now.second,
                    p["latitude"], p["longitude"], utc_offset, API_KEY
                )
                transit_df = planets_to_df(transit_raw)

                current_maha = get_current_maha(maha_dict, now, tz)
                score, jup_h, ven_h, moon_h = calculate_luck_score(natal_df, transit_df, current_maha)

                st.session_state.last_result = {
                    "score": score,
                    "jup_h": jup_h,
                    "ven_h": ven_h,
                    "moon_h": moon_h,
                    "current_maha": current_maha,
                    "natal_df": natal_df,
                    "transit_df": transit_df
                }
                st.session_state.view = "meter"
                st.rerun()

            except Exception as e:
                st.error(f"Error: {str(e)}")

    # ====================== CHARTS VIEW ======================
    if st.session_state.last_result and st.session_state.view == "charts":
        result = st.session_state.last_result
        st.markdown("### 📜 Planetary Positions")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Natal Chart")
            st.dataframe(result["natal_df"], use_container_width=True, height=420)
        with col2:
            st.markdown("#### Current Transit")
            st.dataframe(result["transit_df"], use_container_width=True, height=420)
