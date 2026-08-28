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

# ====================== MODERN GLASSMORPHISM THEME ======================
st.markdown("""
<style>
    :root {
        --bg-gradient: radial-gradient(circle at top right, #1E1B4B, #0F172A, #020617);
        --accent-purple: #8B5CF6;
        --accent-glow: rgba(139, 92, 246, 0.25);
        --glass-bg: rgba(30, 41, 59, 0.7);
        --glass-border: rgba(255, 255, 255, 0.08);
        --text-primary: #F8FAFC;
        --text-secondary: #94A3B8;
    }

    .stApp {
        background: var(--bg-gradient);
        color: var(--text-primary);
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }

    /* Modern Glass Cards */
    div[data-testid="stExpander"], .custom-card {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }

    /* Headings */
    h1, h2, h3 {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }
    
    .stApp h1 {
        background: linear-gradient(135deg, #C084FC 0%, #E879F9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.2rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px 0 var(--accent-glow) !important;
        transition: all 0.2s ease-in-out !important;
    }

    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px 0 rgba(139, 92, 246, 0.4) !important;
    }

    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox > div > div {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.85) !important;
        backdrop-filter: blur(16px);
        border-right: 1px solid var(--glass-border);
    }

    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ====================== DATA LOADERS & AUTH ======================
@st.cache_data
def load_cities():
    df = pd.read_csv("worldcities.csv")
    df = df[["city_ascii", "lat", "lng", "country"]].dropna()
    df["display"] = df["city_ascii"] + ", " + df["country"]
    return df.reset_index(drop=True)

cities_df = load_cities()

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
API_KEY = st.secrets["api"]["key"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Restore session smoothly
if "access_token" in st.session_state and "refresh_token" in st.session_state:
    try:
        supabase.auth.set_session(
            st.session_state["access_token"],
            st.session_state["refresh_token"]
        )
    except Exception:
        st.session_state.clear()

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
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()

# ====================== DATABASE HELPERS ======================
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

# ====================== STATE INITIALIZATION ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "view" not in st.session_state:
    st.session_state.view = "meter"
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ====================== APPLICATION HEADER ======================
st.markdown("<h1 style='text-align:center; margin-bottom: 0px;'>🌠 AstroMeter Pro</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#94A3B8; font-size: 1.1rem; margin-bottom: 30px;'>Cosmic Intelligence Engine</p>", unsafe_allow_html=True)

# ====================== AUTHENTICATION VIEW ======================
if not st.session_state.logged_in:
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        tab1, tab2 = st.tabs(["✦ Sign In", "✦ Create Account"])

        with tab1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Enter the Cosmos", type="primary", use_container_width=True):
                res = sign_in(email, password)
                if res and res.user:
                    st.session_state.user = res.user
                    st.session_state.logged_in = True
                    st.success("Authenticated successfully.")
                    time.sleep(0.5)
                    st.rerun()

        with tab2:
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_pass")
            password2 = st.text_input("Confirm Password", type="password", key="signup_pass2")
            if st.button("Begin Your Journey", use_container_width=True):
                if password != password2:
                    st.error("Passwords do not match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    res = sign_up(email, password)
                    if res and res.user:
                        st.success("Account created! Proceed to Sign In.")
                    else:
                        st.error("Failed to create account.")

# ====================== MAIN DASHBOARD ======================
else:
    user = st.session_state.user
    user_id = user.id

    # Sidebar Navigation
    with st.sidebar:
        st.markdown("### 🪐 Workspace")
        if st.button("🎯 Luck Meter", use_container_width=True):
            st.session_state.view = "meter"
            st.rerun()
        if st.button("📜 Planetary Positions", use_container_width=True):
            st.session_state.view = "charts"
            st.rerun()
        
        st.markdown("---")
        st.caption("Active Session")
        st.markdown(f"**{user.email}**")
        if st.button("Sign Out", use_container_width=True):
            sign_out()

    # ---------- METER VISUALIZATION ----------
    if st.session_state.last_result and st.session_state.view == "meter":
        result = st.session_state.last_result
        score = result["score"]
        current_maha = result["current_maha"]

        if score >= 67:
            zone, zone_color, message = "High", "#10B981", "The cosmos favors bold action"
        elif score >= 34:
            zone, zone_color, message = "Moderate", "#F59E0B", "Steady energy — move with care"
        else:
            zone, zone_color, message = "Low", "#EF4444", "The stars advise patience"

        final_angle = (score / 100) * 180 - 90

        meter_html = f"""
        <div style="display:flex; flex-direction:column; align-items:center; font-family: system-ui, sans-serif;">
          <div style="font-size:12px; font-weight: 700; color:#8B5CF6; letter-spacing: 2px; margin-bottom: 8px;">
            CURRENT MAHA-DASHA • {current_maha.upper()}
          </div>

          <div style="position:relative; width:300px; height:160px;">
            <svg width="300" height="160" viewBox="0 0 320 180">
              <path d="M 30 160 A 130 130 0 0 1 290 160" fill="none" stroke="#1E293B" stroke-width="20" stroke-linecap="round"/>
              <path d="M 30 160 A 130 130 0 0 1 110 48" fill="none" stroke="#EF4444" stroke-width="20" stroke-linecap="round"/>
              <path d="M 110 48 A 130 130 0 0 1 210 48" fill="none" stroke="#F59E0B" stroke-width="20" stroke-linecap="round"/>
              <path d="M 210 48 A 130 130 0 0 1 290 160" fill="none" stroke="#10B981" stroke-width="20" stroke-linecap="round"/>
            </svg>

            <div id="needle" style="
              position:absolute; bottom:18px; left:50%; width:4px; height:110px;
              background: #F8FAFC; transform-origin: bottom center;
              transform: translateX(-50%) rotate(-90deg); border-radius: 4px; z-index: 10;
              box-shadow: 0 0 12px rgba(255, 255, 255, 0.5);
            "></div>

            <div style="
              position:absolute; bottom:10px; left:50%; transform: translateX(-50%);
              width:20px; height:20px; background: #F8FAFC; border-radius: 50%;
              border: 3px solid #0F172A; z-index: 20;
            "></div>
          </div>

          <div id="score" style="
            font-size: 64px; font-weight: 800; color: {zone_color};
            margin-top: -10px; line-height: 1;
          ">0</div>

          <div style="font-size: 16px; font-weight: 700; color: {zone_color}; letter-spacing: 3px; margin-top: 4px;">
            {zone.upper()}
          </div>

          <div style="margin-top: 8px; font-size: 14px; color: #94A3B8; text-align: center;">
            {message}
          </div>
        </div>

        <script>
          const needle = document.getElementById('needle');
          const scoreEl = document.getElementById('score');
          
          setTimeout(() => {{
            needle.style.transition = 'transform 1.5s cubic-bezier(0.2, 0.8, 0.2, 1)';
            needle.style.transform = `translateX(-50%) rotate({final_angle}deg)`;
          }}, 50);

          let current = 0;
          const duration = 1500;
          const start = performance.now();

          function animateScore(time) {{
            const progress = Math.min((time - start) / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3);
            current = Math.floor(ease * {score});
            scoreEl.innerText = current;
            if (progress < 1) requestAnimationFrame(animateScore);
          }}
          requestAnimationFrame(animateScore);
        </script>
        """
        components.html(meter_html, height=320)
        st.caption(f"Jupiter → {result['jup_h']}th from Moon  •  Venus → {result['ven_h']}th from Moon  •  Moon → {result['moon_h']}th from Ascendant")
        st.markdown("---")

    # ---------- PROFILE MANAGEMENT ----------
    profiles = get_user_profiles(user_id)
    selected_profile = None

    if profiles:
        profile_names = [f"{p['name']} ({p['year']}-{p['month']:02d}-{p['day']:02d})" for p in profiles]
        selected = st.selectbox("Active Profile", profile_names)
        selected_profile = profiles[profile_names.index(selected)]

        col_edit, col_del = st.columns(2)
        with col_edit:
            if st.button("✏️ Edit Selected Profile", use_container_width=True):
                st.session_state.edit_profile = selected_profile
        with col_del:
            if st.button("🗑️ Delete Selected Profile", use_container_width=True):
                supabase.table("birth_profiles").delete().eq("id", selected_profile["id"]).execute()
                if "last_result" in st.session_state:
                    del st.session_state.last_result
                st.success("Profile removed.")
                time.sleep(0.5)
                st.rerun()
    else:
        st.info("No birth profiles found. Add one below to begin.")

    # ---------- ADD / EDIT PROFILE EXPANDER ----------
    edit_mode = "edit_profile" in st.session_state and st.session_state.edit_profile is not None
    
    with st.expander("➕ Create / Modify Birth Profile", expanded=edit_mode or not profiles):
        city_query = st.text_input("Search Location", placeholder="Enter city name (e.g. London, Tokyo)...", key="city_search")

        selected_city = None
        lat = lon = None

        if city_query and len(city_query.strip()) >= 2:
            mask = cities_df["city_ascii"].str.contains(city_query.strip(), case=False, na=False)
            matches = cities_df[mask].head(10)

            if not matches.empty:
                chosen = st.selectbox("Select matching city", matches["display"].tolist(), key="city_choice")
                selected_city = matches[matches["display"] == chosen].iloc[0]
                lat, lon = float(selected_city["lat"]), float(selected_city["lng"])
                st.caption(f"Coordinates: `{lat:.4f}, {lon:.4f}`")
            else:
                st.warning("No location matches found.")

        with st.form("profile_form"):
            default = st.session_state.get("edit_profile", {})

            name = st.text_input("Full Name", value=default.get("name", ""))
            c1, c2, c3 = st.columns(3)
            year = c1.number_input("Year", 1900, 2100, value=default.get("year", 1996))
            month = c2.number_input("Month", 1, 12, value=default.get("month", 9))
            day = c3.number_input("Day", 1, 31, value=default.get("day", 25))

            c4, c5, c6 = st.columns(3)
            hour = c4.number_input("Hour (24h)", 0, 23, value=default.get("hour", 7))
            minute = c5.number_input("Minute", 0, 59, value=default.get("minute", 15))
            second = c6.number_input("Second", 0, 59, value=default.get("second", 0))

            if lat is None and default:
                lat = default.get("latitude")
                lon = default.get("longitude")

            submitted = st.form_submit_button("Save Profile Data", type="primary", use_container_width=True)

            if submitted:
                if not name:
                    st.error("Name is required.")
                elif lat is None or lon is None:
                    st.error("Select a valid city location.")
                else:
                    data = {
                        "name": name,
                        "year": int(year), "month": int(month), "day": int(day),
                        "hour": int(hour), "minute": int(minute), "second": int(second),
                        "latitude": float(lat), "longitude": float(lon),
                        "place_name": selected_city["display"] if selected_city is not None else default.get("place_name", "")
                    }

                    if edit_mode:
                        supabase.table("birth_profiles").update(data).eq("id", default["id"]).execute()
                        supabase.table("natal_cache").delete().eq("profile_id", default["id"]).execute()
                        st.session_state.pop("last_result", None)
                        st.session_state.pop("edit_profile", None)
                        st.success("Profile updated.")
                    else:
                        save_profile(user_id, data)
                        st.success("Profile saved.")

                    time.sleep(0.5)
                    st.rerun()

    # ---------- CALCULATION ENGINE ----------
    if selected_profile and st.button("🔮 Calculate Luck Metrics", type="primary", use_container_width=True):
        with st.spinner("Processing planetary transits..."):
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
                st.error(f"Calculation Error: {str(e)}")

    # ---------- CHARTS VIEW ----------
    if st.session_state.last_result and st.session_state.view == "charts":
        result = st.session_state.last_result
        st.markdown("### 📜 Planetary Positions")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Natal Positions")
            st.dataframe(result["natal_df"], use_container_width=True, height=400)
        with col2:
            st.markdown("#### Live Transits")
            st.dataframe(result["transit_df"], use_container_width=True, height=400)
