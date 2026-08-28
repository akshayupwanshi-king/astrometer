import streamlit as st
import time
from datetime import datetime
import pytz
from supabase import create_client
import streamlit.components.v1 as components
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Import backend astrological routines
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
    page_title="AstroMeter Pro • Celestial Intelligence",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== NEBULA DESIGN SYSTEM ======================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap');

    :root {
        --bg-dark: #070913;
        --card-bg: rgba(18, 22, 41, 0.75);
        --card-border: rgba(168, 85, 247, 0.15);
        --purple-glow: #A855F7;
        --cyan-glow: #06B6D4;
        --text-bright: #F8FAFC;
        --text-muted: #94A3B8;
    }

    .stApp {
        background-color: var(--bg-dark);
        background-image: 
            radial-gradient(at 0% 0%, rgba(168, 85, 247, 0.12) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(6, 182, 212, 0.1) 0px, transparent 50%);
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: var(--text-bright);
    }

    .astro-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
        margin-bottom: 20px;
    }

    .astro-stat-value {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #F8FAFC 0%, #A855F7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .astro-stat-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: var(--text-muted);
        font-weight: 600;
    }

    .stButton > button {
        background: linear-gradient(135deg, #A855F7 0%, #6366F1 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
        box-shadow: 0 4px 20px rgba(168, 85, 247, 0.3) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) scale(1.01) !important;
        box-shadow: 0 8px 25px rgba(168, 85, 247, 0.5) !important;
    }

    .stTextInput input, .stNumberInput input, .stSelectbox > div > div {
        background: rgba(11, 15, 30, 0.8) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 12px !important;
        color: #F8FAFC !important;
        padding: 10px 14px !important;
    }

    section[data-testid="stSidebar"] {
        background: rgba(7, 9, 19, 0.9) !important;
        border-right: 1px solid var(--card-border);
    }

    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ====================== ASTRO HELPER FUNCTIONS ======================
def build_house_map_from_df(df):
    """
    Directly extracts house mappings using DataFrame columns ('Planet' & 'House').
    """
    house_map = {i: [] for i in range(1, 13)}
    
    planet_col = 'Planet' if 'Planet' in df.columns else 'planet'
    house_col = 'House' if 'House' in df.columns else 'house'

    for _, row in df.iterrows():
        p_name = str(row[planet_col])
        try:
            h_num = int(row[house_col])
        except (ValueError, TypeError):
            continue

        if 1 <= h_num <= 12:
            # Clean shortening for planet labels inside the chart diamond
            short_name = p_name[:2] if p_name not in ['Rahu', 'Ketu', 'Pluto'] else p_name[:3]
            house_map[h_num].append(short_name)
            
    return house_map

def draw_north_indian_chart(natal_planets, transit_planets=None, title="Kundli Chart"):
    """
    Draws a North Indian Diamond/Square Kundli using Matplotlib.
    """
    fig, ax = plt.subplots(figsize=(7, 7), facecolor='#0D0F1D')
    ax.set_facecolor('#0D0F1D')

    # Outer Square
    outer_square = patches.Rectangle((0, 0), 10, 10, linewidth=2.5, edgecolor='#A855F7', facecolor='none')
    ax.add_patch(outer_square)

    # Diagonal Lines
    lines = [
        ((0, 10), (10, 0)), ((0, 0), (10, 10)),
        ((5, 10), (0, 5)), ((0, 5), (5, 0)),
        ((5, 0), (10, 5)), ((10, 5), (5, 10))
    ]
    for line in lines:
        ax.plot([line[0][0], line[1][0]], [line[0][1], line[1][1]], color='#6366F1', linewidth=1.5)

    # House Center Coordinates
    house_positions = {
        1: (5.0, 7.5),  2: (2.5, 9.0),  3: (1.0, 7.5),
        4: (2.5, 5.0),  5: (1.0, 2.5),  6: (2.5, 1.0),
        7: (5.0, 2.5),  8: (7.5, 1.0),  9: (9.0, 2.5),
        10: (7.5, 5.0), 11: (9.0, 7.5), 12: (7.5, 9.0)
    }

    for house in range(1, 13):
        center = house_positions[house]
        n_list = natal_planets.get(house, [])
        t_list = transit_planets.get(house, []) if transit_planets else []

        # 1. Draw Natal Planets (White Text)
        if n_list:
            ax.text(
                center[0], center[1] + (0.3 if t_list else 0.0), " ".join(n_list),
                color='#F8FAFC', fontsize=9, fontweight='bold',
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#1E1B4B', alpha=0.85, edgecolor='#A855F7')
            )

        # 2. Draw Transit Planets (Cyan Text)
        if t_list:
            ax.text(
                center[0], center[1] - (0.3 if n_list else 0.0), "T: " + " ".join(t_list),
                color='#06B6D4', fontsize=8.5, fontweight='bold',
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#0F172A', alpha=0.85, edgecolor='#06B6D4')
            )

    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-0.5, 10.5)
    ax.axis('off')
    plt.title(title, color='#F8FAFC', fontsize=14, pad=15, fontweight='bold')
    plt.tight_layout()
    return fig
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

# ====================== HEADER ======================
st.markdown("""
<div style="text-align: center; padding: 20px 0 10px 0;">
    <h1 style="font-size: 2.8rem; font-weight: 800; margin-bottom: 0px; background: linear-gradient(135deg, #A855F7 0%, #06B6D4 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        ASTROMETER PRO
    </h1>
    <p style="color: #94A3B8; font-size: 1rem; letter-spacing: 2px; font-weight: 600;">
        CELESTIAL REAL-TIME INTELLIGENCE
    </p>
</div>
""", unsafe_allow_html=True)

# ====================== LOGIN VIEW ======================
if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown('<div class="astro-card">', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["✦ Sign In", "✦ Register"])

        with tab1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Enter Cosmos", type="primary", use_container_width=True):
                res = sign_in(email, password)
                if res and res.user:
                    st.session_state.user = res.user
                    st.session_state.logged_in = True
                    st.rerun()

        with tab2:
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_pass")
            password2 = st.text_input("Confirm Password", type="password", key="signup_pass2")
            if st.button("Create Account", use_container_width=True):
                if password == password2 and len(password) >= 6:
                    res = sign_up(email, password)
                    if res and res.user:
                        st.success("Account ready. Sign in to continue.")
                else:
                    st.error("Check password parameters.")
        st.markdown('</div>', unsafe_allow_html=True)

# ====================== DASHBOARD VIEW ======================
else:
    user = st.session_state.user
    user_id = user.id

    with st.sidebar:
        st.markdown("### 🪐 Navigation")
        if st.button("🎯 Intelligence Dashboard", use_container_width=True):
            st.session_state.view = "meter"
            st.rerun()
        if st.button("🔮 North Indian Kundli", use_container_width=True):
            st.session_state.view = "charts"
            st.rerun()
        st.markdown("---")
        st.caption("Active Session")
        st.markdown(f"**{user.email}**")
        if st.button("Sign Out", use_container_width=True):
            sign_out()

    # ---------- METRICS & METER DISPLAY ----------
    if st.session_state.last_result and st.session_state.view == "meter":
        result = st.session_state.last_result
        score = result["score"]
        current_maha = result["current_maha"]

        if score >= 67:
            zone, zone_color = "Optimal Alignment", "#10B981"
        elif score >= 34:
            zone, zone_color = "Balanced Energy", "#F59E0B"
        else:
            zone, zone_color = "Restorative Phase", "#EF4444"

        final_angle = (score / 100) * 180 - 90

        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.markdown(f"""
            <div class="astro-card">
                <div class="astro-stat-label">Jupiter House</div>
                <div class="astro-stat-value">{result['jup_h']}th</div>
                <div style="font-size:0.75rem; color:#94A3B8;">From Natal Moon</div>
            </div>
            """, unsafe_allow_html=True)
        with m_col2:
            st.markdown(f"""
            <div class="astro-card">
                <div class="astro-stat-label">Venus House</div>
                <div class="astro-stat-value">{result['ven_h']}th</div>
                <div style="font-size:0.75rem; color:#94A3B8;">From Natal Moon</div>
            </div>
            """, unsafe_allow_html=True)
        with m_col3:
            st.markdown(f"""
            <div class="astro-card">
                <div class="astro-stat-label">Moon Position</div>
                <div class="astro-stat-value">{result['moon_h']}th</div>
                <div style="font-size:0.75rem; color:#94A3B8;">From Ascendant</div>
            </div>
            """, unsafe_allow_html=True)

        meter_html = f"""
        <div style="display:flex; flex-direction:column; align-items:center; font-family:'Plus Jakarta Sans', sans-serif;">
          <div style="font-size:12px; font-weight: 700; color:#A855F7; letter-spacing: 3px; margin-bottom: 8px;">
            CURRENT MAHA-DASHA • {current_maha.upper()}
          </div>

          <div style="position:relative; width:300px; height:150px;">
            <svg width="300" height="150" viewBox="0 0 320 180">
              <path d="M 30 160 A 130 130 0 0 1 290 160" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="22" stroke-linecap="round"/>
              <path d="M 30 160 A 130 130 0 0 1 110 48" fill="none" stroke="#EF4444" stroke-width="22" stroke-linecap="round"/>
              <path d="M 110 48 A 130 130 0 0 1 210 48" fill="none" stroke="#F59E0B" stroke-width="22" stroke-linecap="round"/>
              <path d="M 210 48 A 130 130 0 0 1 290 160" fill="none" stroke="#10B981" stroke-width="22" stroke-linecap="round"/>
            </svg>

            <div id="needle" style="
              position:absolute; bottom:18px; left:50%; width:4px; height:110px;
              background: #F8FAFC; transform-origin: bottom center;
              transform: translateX(-50%) rotate(-90deg); border-radius: 4px; z-index: 10;
              box-shadow: 0 0 15px rgba(168, 85, 247, 0.8);
            "></div>
          </div>

          <div id="score" style="
            font-size: 72px; font-weight: 800; color: {zone_color}; line-height:1; margin-top:-10px;
          ">0</div>

          <div style="font-size: 15px; font-weight: 700; color: {zone_color}; letter-spacing: 2px; margin-top: 6px;">
            {zone.upper()}
          </div>
        </div>

        <script>
          const needle = document.getElementById('needle');
          const scoreEl = document.getElementById('score');
          
          setTimeout(() => {{
            needle.style.transition = 'transform 1.8s cubic-bezier(0.16, 1, 0.3, 1)';
            needle.style.transform = `translateX(-50%) rotate({final_angle}deg)`;
          }}, 50);

          let current = 0;
          const duration = 1800;
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
        components.html(meter_html, height=310)

    # ---------- PROFILE MANAGEMENT ----------
    profiles = get_user_profiles(user_id)
    selected_profile = None

    if profiles:
        profile_names = [f"{p['name']} ({p['year']}-{p['month']:02d}-{p['day']:02d})" for p in profiles]
        selected = st.selectbox("Active Subject Profile", profile_names)
        selected_profile = profiles[profile_names.index(selected)]

        col_edit, col_del = st.columns(2)
        with col_edit:
            if st.button("✏️ Edit Profile Parameters", use_container_width=True):
                st.session_state.edit_profile = selected_profile
        with col_del:
            if st.button("🗑️ Delete Profile", use_container_width=True):
                supabase.table("birth_profiles").delete().eq("id", selected_profile["id"]).execute()
                st.session_state.pop("last_result", None)
                st.rerun()

    # ---------- PROFILE ADD/EDIT FORM ----------
    edit_mode = "edit_profile" in st.session_state and st.session_state.edit_profile is not None
    
    with st.expander("➕ Configure Birth Chart Data", expanded=edit_mode or not profiles):
        city_query = st.text_input("Search Birth City", placeholder="Type city name...", key="city_search")
        selected_city = None
        lat = lon = None

        if city_query and len(city_query.strip()) >= 2:
            mask = cities_df["city_ascii"].str.contains(city_query.strip(), case=False, na=False)
            matches = cities_df[mask].head(8)

            if not matches.empty:
                chosen = st.selectbox("Matching Location", matches["display"].tolist(), key="city_choice")
                selected_city = matches[matches["display"] == chosen].iloc[0]
                lat, lon = float(selected_city["lat"]), float(selected_city["lng"])

        with st.form("profile_form"):
            default = st.session_state.get("edit_profile", {})

            name = st.text_input("Subject Name", value=default.get("name", ""))
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

            submitted = st.form_submit_button("Save Profile Matrix", type="primary", use_container_width=True)

            if submitted:
                if name and lat is not None and lon is not None:
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
                        st.session_state.pop("edit_profile", None)
                    else:
                        save_profile(user_id, data)

                    st.rerun()

    # ---------- ENGINE COMPUTE BUTTON ----------
    if selected_profile and st.button("🔮 Align Planetary Matrix", type="primary", use_container_width=True):
        with st.spinner("Computing real-time transits..."):
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
                st.error(f"Execution Error: {str(e)}")

    # ---------- NORTH INDIAN KUNDLI CHART VIEW ----------
    if st.session_state.view == "charts":
        if st.session_state.last_result is None:
            st.warning("⚠️ No planetary data computed yet. Please select or create a profile on the Intelligence Dashboard and click 'Align Planetary Matrix' first.")
        else:
            result = st.session_state.last_result

            natal_df = result["natal_df"]
            transit_df = result["transit_df"]

            # Extract house mappings directly from DataFrame structure
            natal_house_map = build_house_map_from_df(natal_df)
            transit_house_map = build_house_map_from_df(transit_df)

            col_chart, col_data = st.columns([1.2, 1])

            with col_chart:
                st.markdown("### 🔮 Kundli Chart (North Indian)")
                fig = draw_north_indian_chart(
                    natal_planets=natal_house_map,
                    transit_planets=transit_house_map,
                    title="Natal (White) & Transits (T:)"
                )
                st.pyplot(fig, use_container_width=True)

            with col_data:
                st.markdown("### 📊 Planetary Positions")
                tab1, tab2 = st.tabs(["Natal Positions", "Current Transits"])
                with tab1:
                    st.dataframe(natal_df, use_container_width=True, height=350)
                with tab2:
                    st.dataframe(transit_df, use_container_width=True, height=350)
