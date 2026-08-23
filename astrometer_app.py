import streamlit as st
import time
from datetime import datetime
import pytz
from supabase import create_client

# Import all secret logic from engine
from astro_engine import (
    get_timezone,
    get_planets_extended,
    get_maha_dashas,
    planets_to_df,
    calculate_luck_score,
    get_current_maha
)

# ====================== PAGE CONFIG ======================
st.set_page_config(page_title="AstroMeter Pro", page_icon="🌠", layout="wide")

# ====================== SECRETS ======================
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
API_KEY = st.secrets["api"]["key"]

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
                        p["latitude"], p["longitude"], utc_offset,
                        api_key=API_KEY
                    )
                    maha_dict = get_maha_dashas(
                        p["year"], p["month"], p["day"],
                        p["hour"], p["minute"], p["second"],
                        p["latitude"], p["longitude"], utc_offset,
                        api_key=API_KEY
                    )
                    save_natal_cache(p["id"], natal_raw, maha_dict)

                natal_df = planets_to_df(natal_raw)

                # Current transit
                transit_raw = get_planets_extended(
                    now.year, now.month, now.day,
                    now.hour, now.minute, now.second,
                    p["latitude"], p["longitude"], utc_offset,
                    api_key=API_KEY
                )
                transit_df = planets_to_df(transit_raw)

                current_maha = get_current_maha(maha_dict, now, tz)

                st.success(f"**Current Maha-Dasha:** {current_maha}")

                # ---- Speedtest-style Luck Meter ----
                score, jup_h, ven_h, moon_h = calculate_luck_score(natal_df, transit_df, current_maha)

                if score >= 67:
                    zone = "High"
                    zone_color = "#00C853"
                    message = "Excellent time for important actions!"
                elif score >= 34:
                    zone = "Moderate"
                    zone_color = "#FFB300"
                    message = "Steady progress. Avoid major risks."
                else:
                    zone = "Low"
                    zone_color = "#FF1744"
                    message = "Low energy period. Better to wait."

                angle = (score / 100) * 180

                meter_html = f"""
                <div style="display:flex; flex-direction:column; align-items:center; margin: 20px 0 30px 0;">
                  <div style="position:relative; width:280px; height:160px;">
                    <svg width="280" height="160" viewBox="0 0 280 160">
                      <path d="M 30 150 A 110 110 0 0 1 95 45" fill="none" stroke="#FF1744" stroke-width="18" stroke-linecap="round"/>
                      <path d="M 95 45 A 110 110 0 0 1 185 45" fill="none" stroke="#FFB300" stroke-width="18" stroke-linecap="round"/>
                      <path d="M 185 45 A 110 110 0 0 1 250 150" fill="none" stroke="#00C853" stroke-width="18" stroke-linecap="round"/>
                    </svg>
                    <div style="
                      position:absolute; bottom:10px; left:50%; width:6px; height:110px;
                      background:#222; transform-origin:bottom center;
                      transform:translateX(-50%) rotate({angle - 90}deg);
                      border-radius:4px; z-index:10;
                      transition:transform 1.2s cubic-bezier(0.34, 1.56, 0.64, 1);
                    "></div>
                    <div style="
                      position:absolute; bottom:0; left:50%; transform:translateX(-50%);
                      width:28px; height:28px; background:#222; border-radius:50%;
                      border:4px solid white; box-shadow:0 2px 8px rgba(0,0,0,0.3); z-index:20;
                    "></div>
                  </div>
                  <div style="font-size:64px; font-weight:800; color:{zone_color}; margin-top:-10px; line-height:1;">
                    {score}
                  </div>
                  <div style="font-size:22px; font-weight:600; color:{zone_color}; margin-top:4px; letter-spacing:1px;">
                    {zone.upper()}
                  </div>
                  <div style="margin-top:16px; font-size:16px; color:#555; text-align:center; max-width:320px;">
                    {message}
                  </div>
                </div>
                """
                st.components.v1.html(meter_html, height=340)

                st.caption(f"Jupiter in {jup_h}th from Moon  •  Venus in {ven_h}th from Moon  •  Moon in {moon_h}th from Ascendant")

                # Charts
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Natal Chart")
                    st.dataframe(natal_df, use_container_width=True)
                with col2:
                    st.subheader("Current Transit")
                    st.dataframe(transit_df, use_container_width=True)

            except Exception as e:
                st.error(f"Error during calculation: {str(e)}")
