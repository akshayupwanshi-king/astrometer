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
    /* Global Reset & Dark Theme */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #1a1636 0%, #0d0e15 100%);
        color: #e2e8f0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Headings */
    h1, h2, h3 {
        color: #f1f5f9 !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }

    /* Modern Card Layouts */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: #ffffff;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        box-shadow: 0 4px 14px 0 rgba(99, 102, 241, 0.39);
        transition: all 0.2s ease-in-out;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px 0 rgba(99, 102, 241, 0.55);
    }

    /* Inputs */
    .stTextInput > div > div > input, .stNumberInput > div > div > input {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
    }
    .stTextInput > div > div > input:focus, .stNumberInput > div > div > input:focus {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 0 1px #8b5cf6 !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: rgba(13, 14, 21, 0.85);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }

    /* Metric Badges */
    .metric-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        background: rgba(139, 92, 246, 0.15);
        color: #c4b5fd;
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ====================== DATA & AUTH INITIALIZATION ======================
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

# Session State Setup
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "view" not in st.session_state:
    st.session_state.view = "meter"
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# Restore Auth
if "access_token" in st.session_state and "refresh_token" in st.session_state:
    try:
        supabase.auth.set_session(
            st.session_state["access_token"],
            st.session_state["refresh_token"]
        )
    except Exception:
        pass

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
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Database Functions
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
        "updated_at": datetime.now(pytz.utc).isoformat()
    }).execute()

# ====================== HEADER ======================
st.markdown("""
    <div style='text-align: center; padding: 1rem 0 2rem 0;'>
        <h1 style='font-size: 2.5rem; margin-bottom: 0.2rem;'>🌠 AstroMeter Pro</h1>
        <p style='color: #94a3b8; font-size: 1rem;'>Cosmic Intelligence & Real-time Transit Alignment</p>
    </div>
""", unsafe_allow_html=True)

# ====================== AUTH VIEW ======================
if not st.session_state.logged_in:
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Sign In", "Create Account"])

        with tab1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Enter the Cosmos", type="primary", use_container_width=True):
                res = sign_in(email, password)
                if res and res.user:
                    st.session_state.user = res.user
                    st.session_state.logged_in = True
                    st.success("Welcome back!")
                    time.sleep(0.5)
                    st.rerun()

        with tab2:
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
                        st.success("Account created successfully! Please sign in.")
                    else:
                        st.error("Could not create account.")
        st.markdown('</div>', unsafe_allow_html=True)

# ====================== MAIN APP VIEW ======================
else:
    user = st.session_state.user
    user_id = user.id

    # Sidebar Navigation
    with st.sidebar:
        st.markdown(f"<span class='metric-badge'>{user.email}</span>", unsafe_allow_html=True)
        st.markdown("### Navigation")
        if st.button("🎯 Luck Meter", use_container_width=True):
            st.session_state.view = "meter"
            st.rerun()
        if st.button("📜 Planetary Positions", use_container_width=True):
            st.session_state.view = "charts"
            st.rerun()
        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            sign_out()

    # Gauge Component Display
    if st.session_state.last_result and st.session_state.view == "meter":
        result = st.session_state.last_result
        score = int(result["score"])
        current_maha = str(result["current_maha"])

        if score >= 67:
            zone, zone_color, message = "High", "#10B981", "The cosmos favors bold action"
        elif score >= 34:
            zone, zone_color, message = "Moderate", "#F59E0B", "Steady energy — move with care"
        else:
            zone, zone_color, message = "Low", "#EF4444", "The stars advise patience"

        final_angle = int((score / 100) * 180 - 90)

        meter_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            body {{
                margin: 0;
                background: transparent;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                color: #e2e8f0;
            }}
            .container {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }}
            .maha-badge {{
                font-size: 11px;
                letter-spacing: 2px;
                color: #a78bfa;
                text-transform: uppercase;
                margin-bottom: 12px;
                background: rgba(167, 139, 250, 0.1);
                padding: 4px 12px;
                border-radius: 12px;
                border: 1px solid rgba(167, 139, 250, 0.2);
            }}
            .score-val {{
                font-size: 72px;
                font-weight: 800;
                color: {zone_color};
                margin-top: -10px;
                line-height: 1;
            }}
            .status-text {{
                font-size: 16px;
                font-weight: 600;
                color: {zone_color};
                letter-spacing: 3px;
                margin-top: 4px;
            }}
            .sub-text {{
                margin-top: 8px;
                font-size: 14px;
                color: #94a3b8;
            }}
        </style>
        </head>
        <body>
            <div class="container">
                <div class="maha-badge">CURRENT MAHA-DASHA • {current_maha.upper()}</div>
                <div style="position:relative; width:300px; height:150px;">
                    <svg width="300" height="150" viewBox="0 0 300 150">
                        <path d="M 20 140 A 130 130 0 0 1 280 140" fill="none" stroke="#1e293b" stroke-width="18" stroke-linecap="round"/>
                        <path d="M 20 140 A 130 130 0 0 1 100 42" fill="none" stroke="#EF4444" stroke-width="18" stroke-linecap="round"/>
                        <path d="M 100 42 A 130 130 0 0 1 200 42" fill="none" stroke="#F59E0B" stroke-width="18" stroke-linecap="round"/>
                        <path d="M 200 42 A 130 130 0 0 1 280 140" fill="none" stroke="#10B981" stroke-width="18" stroke-linecap="round"/>
                    </svg>
                    <div id="needle" style="
                        position:absolute; bottom:10px; left:50%; width:4px; height:110px;
                        background: #f8fafc; transform-origin: bottom center;
                        transform: translateX(-50%) rotate(-90deg);
                        border-radius: 4px; z-index: 10;
                        transition: transform 1.5s cubic-bezier(0.2, 1, 0.3, 1);
                    "></div>
                </div>
                <div id="score" class="score-val">0</div>
                <div class="status-text">{zone.upper()}</div>
                <div class="sub-text">{message}</div>
            </div>
            <script>
                setTimeout(() => {{
                    document.getElementById('needle').style.transform = 'translateX(-50%) rotate({final_angle}deg)';
                }}, 100);

                let current = 0;
                const target = {score};
                const duration = 1500;
                const start = performance.now();

                function animate(time) {{
                    const progress = Math.min((time - start) / duration, 1);
                    const ease = 1 - Math.pow(1 - progress, 3);
                    document.getElementById('score').innerText = Math.floor(ease * target);
                    if (progress < 1) requestAnimationFrame(animate);
                }}
                requestAnimationFrame(animate);
            </script>
        </body>
        </html>
        """
        components.html(meter_html, height=340)

        # Planetary House Positions Summary
        c1, c2, c3 = st.columns(3)
        c1.metric("Jupiter Position", f"{result['jup_h']}th House", "From Moon")
        c2.metric("Venus Position", f"{result['ven_h']}th House", "From Moon")
        c3.metric("Moon Position", f"{result['moon_h']}th House", "From Ascendant")
        st.markdown("---")

    # Profile Section
    profiles = get_user_profiles(user_id)
    selected_profile = None

    if profiles:
        profile_names = [f"{p['name']} ({p['year']}-{p['month']:02d}-{p['day']:02d})" for p in profiles]
        selected = st.selectbox("Select Active Profile", profile_names)
        selected_profile = profiles[profile_names.index(selected)]

        col_edit, col_del, _ = st.columns([1, 1, 2])
        with col_edit:
            if st.button("✏️ Edit Profile", use_container_width=True):
                st.session_state.edit_profile = selected_profile
        with col_del:
            if st.button("🗑️ Delete Profile", use_container_width=True):
                supabase.table("birth_profiles").delete().eq("id", selected_profile["id"]).execute()
                st.success("Profile removed")
                time.sleep(0.5)
                st.rerun()

    # Create/Edit Profile Form
    edit_mode = "edit_profile" in st.session_state and st.session_state.edit_profile is not None
    with st.expander("👤 Profile Details", expanded=edit_mode or not profiles):
        default = st.session_state.get("edit_profile", {})
        
        # City Finder Input
        city_query = st.text_input("Search Birth City", value=default.get("place_name", ""), key="city_search")
        selected_city_data = None
        
        if city_query and len(city_query.strip()) >= 2:
            mask = cities_df["city_ascii"].str.contains(city_query.strip(), case=False, na=False)
            matches = cities_df[mask].head(10)
            if not matches.empty:
                chosen = st.selectbox("Match Suggestions", matches["display"].tolist())
                selected_city_data = matches[matches["display"] == chosen].iloc[0]
            else:
                st.warning("No location found matching search term.")

        with st.form("profile_form"):
            name = st.text_input("Profile Name", value=default.get("name", ""))
            
            c1, c2, c3 = st.columns(3)
            year = c1.number_input("Year", 1900, 2100, value=default.get("year", 1996))
            month = c2.number_input("Month", 1, 12, value=default.get("month", 9))
            day = c3.number_input("Day", 1, 31, value=default.get("day", 25))
            
            c4, c5, c6 = st.columns(3)
            hour = c4.number_input("Hour (24h)", 0, 23, value=default.get("hour", 7))
            minute = c5.number_input("Minute", 0, 59, value=default.get("minute", 15))
            second = c6.number_input("Second", 0, 59, value=default.get("second", 0))

            submitted = st.form_submit_button("Save Profile", type="primary")

            if submitted:
                # Lat/Long Resolution Strategy
                lat = selected_city_data["lat"] if selected_city_data is not None else default.get("latitude")
                lon = selected_city_data["lng"] if selected_city_data is not None else default.get("longitude")
                place_name = selected_city_data["display"] if selected_city_data is not None else default.get("place_name", "")

                if not name:
                    st.error("Please enter a profile name.")
                elif lat is None or lon is None:
                    st.error("Please search and select a birth city.")
                else:
                    data = {
                        "name": name,
                        "year": int(year), "month": int(month), "day": int(day),
                        "hour": int(hour), "minute": int(minute), "second": int(second),
                        "latitude": float(lat), "longitude": float(lon),
                        "place_name": place_name
                    }

                    if edit_mode:
                        supabase.table("birth_profiles").update(data).eq("id", default["id"]).execute()
                        supabase.table("natal_cache").delete().eq("profile_id", default["id"]).execute()
                        if "last_result" in st.session_state:
                            del st.session_state.last_result
                        st.session_state.edit_profile = None
                    else:
                        save_profile(user_id, data)
                    
                    st.success("Profile saved successfully!")
                    time.sleep(0.5)
                    st.rerun()

    # Action Trigger
    if selected_profile and st.button("🔮 Calculate Current Luck", type="primary", use_container_width=True):
        with st.spinner("Calculating planetary transits..."):
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

    # Detailed Charts View
    if st.session_state.last_result and st.session_state.view == "charts":
        result = st.session_state.last_result
        st.markdown("### Planetary Configurations")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Natal Positions")
            st.dataframe(result["natal_df"], use_container_width=True, height=400)
        with col2:
            st.markdown("#### Current Transits")
            st.dataframe(result["transit_df"], use_container_width=True, height=400)
