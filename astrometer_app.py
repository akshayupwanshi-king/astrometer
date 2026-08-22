import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime, date, time
import pytz
from timezonefinder import TimezoneFinder
from astral.sun import sun
from astral import LocationInfo

# ====================== CONFIG ======================
API_KEY = "klc5pT5iG06kuRW51dYdb4yZNMxaLMR93tiFKfGp"   # ← replace if needed
BASE_URL = "https://json.freeastrologyapi.com"

st.set_page_config(
    page_title="AstroMeter 🌠",
    page_icon="🌠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== HELPER FUNCTIONS ======================

def get_timezone(lat, lon):
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lng=lon, lat=lat)
    return tz_str or "Asia/Kolkata"

def get_planets_extended(year, month, day, hour, minute, second, lat, lon, tz_offset):
    url = f"{BASE_URL}/planets/extended"
    payload = {
        "year": year, "month": month, "date": day,
        "hours": hour, "minutes": minute, "seconds": second,
        "latitude": lat, "longitude": lon, "timezone": tz_offset,
        "settings": {
            "observation_point": "topocentric",
            "ayanamsha": "lahiri"
        }
    }
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("output", {})

def planets_to_df(astrological_data):
    houses = {i: {"planets": []} for i in range(1, 13)}
    for planet_name, planet_info in astrological_data.items():
        house_number = planet_info.get("house_number", 1)
        planet_info["name"] = planet_name
        houses.setdefault(house_number, {"planets": []})
        houses[house_number]["planets"].append(planet_info)

    rows = []
    for house_num in range(1, 13):
        for planet in houses[house_num]["planets"]:
            rows.append({
                "House": house_num,
                "Planet": planet["name"],
                "CurrSign": planet.get("current_sign", "N/A"),
                "FullDeg": planet.get("fullDegree", 0),
                "NormDeg": planet.get("normDegree", 0),
                "Retro": planet.get("isRetro", "N/A"),
                "Zodiac_Sign": planet.get("zodiac_sign_name", "N/A"),
                "Zodiac_Lord": planet.get("zodiac_sign_lord", "N/A"),
                "NakNo": planet.get("nakshatra_number", "N/A"),
                "Nakshatra": planet.get("nakshatra_name", "N/A"),
                "Pada": planet.get("nakshatra_pada", "N/A"),
                "Dasha_Lord": planet.get("nakshatra_vimsottari_lord", "N/A")
            })
    return pd.DataFrame(rows)

def get_maha_dashas(year, month, day, hour, minute, second, lat, lon, tz_offset):
    url = f"{BASE_URL}/vimsottari/maha-dasas"
    payload = {
        "year": year, "month": month, "date": day,
        "hours": hour, "minutes": minute, "seconds": second,
        "latitude": lat, "longitude": lon, "timezone": tz_offset,
        "config": {
            "observation_point": "topocentric",
            "ayanamsha": "lahiri"
        }
    }
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    data = r.json()
    output_str = data.get("output", "{}")
    return json.loads(output_str)

def get_current_dasha(maha_dict, current_dt):
    """Find current Maha-Dasha from the timeline"""
    for order, info in maha_dict.items():
        start = datetime.fromisoformat(info["start_time"].replace(" ", "T"))
        end   = datetime.fromisoformat(info["end_time"].replace(" ", "T"))
        # make timezone-aware if needed
        if start.tzinfo is None:
            start = start.replace(tzinfo=current_dt.tzinfo)
            end   = end.replace(tzinfo=current_dt.tzinfo)
        if start <= current_dt <= end:
            return info["Lord"], start, end
    return "Unknown", None, None

def get_sunrise(lat, lon, tz_str):
    location = LocationInfo(latitude=lat, longitude=lon)
    tz = pytz.timezone(tz_str)
    s = sun(location.observer, date=date.today(), tzinfo=tz)
    return s["sunrise"]

# ====================== LUCK CALCULATION (simplified clean version) ======================

signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
hora_order = ['Sun', 'Venus', 'Mercury', 'Moon', 'Saturn', 'Jupiter', 'Mars']
good_houses = {1: 30, 5: 20, 9: 20, 2: 10, 4: 10, 7: 10, 11: 10}
day_rulers = {0: 'Moon', 1: 'Mars', 2: 'Mercury', 3: 'Jupiter',
              4: 'Venus', 5: 'Saturn', 6: 'Sun'}

def get_house_from_sign(curr_sign, ref_sign):
    return (signs.index(curr_sign) - signs.index(ref_sign)) % 12 + 1

def get_hora_planet(now, sunrise):
    day_ruler = day_rulers[now.weekday()]
    start_idx = hora_order.index(day_ruler)
    minutes = (now - sunrise).total_seconds() / 60
    hora_num = int(minutes // 60)
    return hora_order[(start_idx + hora_num) % 7]

def calculate_luck(natal_df, transit_df, now, sunrise, maha_dasha):
    moon_sign = natal_df[natal_df['Planet'] == 'Moon']['Zodiac_Sign'].values[0]
    asc_sign  = natal_df[natal_df['Planet'] == 'Ascendant']['Zodiac_Sign'].values[0]

    # Jupiter
    jup_sign = transit_df[transit_df['Planet'] == 'Jupiter']['Zodiac_Sign'].values[0]
    jup_h_moon = get_house_from_sign(jup_sign, moon_sign)
    jup_score = good_houses.get(jup_h_moon, 5)

    # Venus
    ven_sign = transit_df[transit_df['Planet'] == 'Venus']['Zodiac_Sign'].values[0]
    ven_h_moon = get_house_from_sign(ven_sign, moon_sign)
    ven_score = good_houses.get(ven_h_moon, 5)

    # Moon
    moon_sign_t = transit_df[transit_df['Planet'] == 'Moon']['Zodiac_Sign'].values[0]
    moon_h = get_house_from_sign(moon_sign_t, asc_sign)
    moon_score = good_houses.get(moon_h, 5)

    # Saturn malefic
    sat_sign = transit_df[transit_df['Planet'] == 'Saturn']['Zodiac_Sign'].values[0]
    sat_h = get_house_from_sign(sat_sign, moon_sign)
    malefic = -15 if sat_h in [1, 5, 9] else 0

    # Hora
    hora = get_hora_planet(now, sunrise)
    hourly = 12 if hora in ['Jupiter', 'Venus'] else 6 if hora in ['Moon', 'Mercury'] else 0

    # Dasha bonus (simple)
    dasha_bonus = 15 if maha_dasha in ['Jupiter', 'Venus', 'Mercury', 'Moon'] else 5

    total = min(max(jup_score + ven_score + moon_score + malefic + hourly + dasha_bonus, 0), 100)
    return total, jup_h_moon, ven_h_moon, moon_h, hora

# ====================== UI ======================

st.title("🌠 AstroMeter — Vedic Luck Meter")
st.markdown("Calculate your current cosmic luck score using real-time Vedic astrology.")

with st.sidebar:
    st.header("Birth Details")
    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input("Year", 1900, 2100, 1996)
        month = st.number_input("Month", 1, 12, 9)
        day = st.number_input("Day", 1, 31, 25)
    with col2:
        hour = st.number_input("Hour (24h)", 0, 23, 7)
        minute = st.number_input("Minute", 0, 59, 15)
        second = st.number_input("Second", 0, 59, 0)

    st.subheader("Location")
    lat = st.number_input("Latitude", -90.0, 90.0, 21.146633, format="%.6f")
    lon = st.number_input("Longitude", -180.0, 180.0, 79.088860, format="%.6f")

    st.markdown("---")
    calculate_btn = st.button("🔮 Calculate Luck", type="primary", use_container_width=True)

# ====================== MAIN LOGIC ======================

if calculate_btn:
    with st.spinner("Consulting the stars..."):
        try:
            tz_str = get_timezone(lat, lon)
            tz = pytz.timezone(tz_str)
            now = datetime.now(tz)
            birth_dt = tz.localize(datetime(year, month, day, hour, minute, second))

            # Timezone offset
            utc_offset = now.utcoffset().total_seconds() / 3600

            # 1. Natal chart
            natal_raw = get_planets_extended(year, month, day, hour, minute, second, lat, lon, utc_offset)
            natal_df = planets_to_df(natal_raw)

            # 2. Transit chart (current moment)
            transit_raw = get_planets_extended(
                now.year, now.month, now.day,
                now.hour, now.minute, now.second,
                lat, lon, utc_offset
            )
            transit_df = planets_to_df(transit_raw)

            # 3. Maha Dashas
            maha_dict = get_maha_dashas(year, month, day, hour, minute, second, lat, lon, utc_offset)
            maha_dasha, maha_start, maha_end = get_current_dasha(maha_dict, now)

            # 4. Sunrise
            sunrise = get_sunrise(lat, lon, tz_str)

            # 5. Luck score
            score, jup_h, ven_h, moon_h, hora = calculate_luck(
                natal_df, transit_df, now, sunrise, maha_dasha
            )

            # ====================== DISPLAY ======================
            st.success("Calculation complete!")

            # Score Card
            zone = "🔴 Low" if score <= 33 else "🟡 Moderate" if score <= 66 else "🟢 High"
            st.markdown(f"### Luck Score: **{score}/100**  —  {zone}")

            colA, colB, colC = st.columns(3)
            with colA:
                st.metric("Current Maha-Dasha", maha_dasha)
            with colB:
                st.metric("Current Hora", hora)
            with colC:
                st.metric("Moon House (from Asc)", f"{moon_h}th")

            st.markdown("---")

            # Detailed breakdown
            st.subheader("Cosmic Breakdown")
            desc = (
                f"Jupiter is currently in the **{jup_h}th** house from your natal Moon.  \n"
                f"Venus is in the **{ven_h}th** house from Moon.  \n"
                f"Transit Moon is in the **{moon_h}th** house from Ascendant.  \n"
                f"**{hora} Hora** is active right now.  \n"
                f"You are running **{maha_dasha} Maha-Dasha**."
            )
            st.info(desc)

            if score >= 67:
                st.success("🌠 **High Luck Zone** — Great time to take important actions!")
            elif score >= 34:
                st.warning("Steady progress recommended. Avoid major risks.")
            else:
                st.error("Low energy period. Better to wait or do remedial work.")

            # Show tables
            with st.expander("📊 View Natal Chart"):
                st.dataframe(natal_df, use_container_width=True)

            with st.expander("📊 View Current Transit Chart"):
                st.dataframe(transit_df, use_container_width=True)

            with st.expander("📜 Full Maha-Dasha Timeline"):
                rows = []
                for k, v in maha_dict.items():
                    rows.append({
                        "Order": int(k),
                        "Lord": v["Lord"],
                        "Start": v["start_time"][:19],
                        "End": v["end_time"][:19]
                    })
                st.dataframe(pd.DataFrame(rows).sort_values("Order"), use_container_width=True)

        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.exception(e)

else:
    st.info("← Enter your birth details in the sidebar and click **Calculate Luck**")
