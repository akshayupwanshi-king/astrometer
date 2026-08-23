# astro_engine.py
import requests
import json
import pandas as pd
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder
import time

BASE_URL = "https://json.freeastrologyapi.com"

signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

good_houses = {1: 30, 5: 20, 9: 20, 2: 10, 4: 10, 7: 10, 11: 10}

def get_timezone(lat, lon):
    tf = TimezoneFinder()
    return tf.timezone_at(lng=lon, lat=lat) or "Asia/Kolkata"

def get_planets_extended(year, month, day, hour, minute, second, lat, lon, tz_offset, api_key):
    url = f"{BASE_URL}/planets/extended"
    payload = {
        "year": year, "month": month, "date": day,
        "hours": hour, "minutes": minute, "seconds": second,
        "latitude": lat, "longitude": lon, "timezone": tz_offset,
        "settings": {"observation_point": "topocentric", "ayanamsha": "lahiri"}
    }
    headers = {"Content-Type": "application/json", "x-api-key": api_key}

    for attempt in range(3):
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code == 429:
            time.sleep((attempt + 1) * 8)
            continue
        r.raise_for_status()
        return r.json().get("output", {})
    raise Exception("API rate limit exceeded")

def get_maha_dashas(year, month, day, hour, minute, second, lat, lon, tz_offset, api_key):
    url = f"{BASE_URL}/vimsottari/maha-dasas"
    payload = {
        "year": year, "month": month, "date": day,
        "hours": hour, "minutes": minute, "seconds": second,
        "latitude": lat, "longitude": lon, "timezone": tz_offset,
        "config": {"observation_point": "topocentric", "ayanamsha": "lahiri"}
    }
    headers = {"Content-Type": "application/json", "x-api-key": api_key}

    for attempt in range(4):
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code == 429:
            time.sleep((attempt + 1) * 10)
            continue
        r.raise_for_status()
        return json.loads(r.json().get("output", "{}"))
    raise Exception("Failed to get Maha-Dasha after retries")

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

def get_house_from_sign(curr_sign, ref_sign):
    try:
        return (signs.index(curr_sign) - signs.index(ref_sign)) % 12 + 1
    except:
        return 6

def calculate_luck_score(natal_df, transit_df, current_maha):
    try:
        moon_sign = natal_df[natal_df['Planet'] == 'Moon']['Zodiac_Sign'].values[0]
        asc_sign = natal_df[natal_df['Planet'] == 'Ascendant']['Zodiac_Sign'].values[0]

        jup_sign = transit_df[transit_df['Planet'] == 'Jupiter']['Zodiac_Sign'].values[0]
        jup_h = get_house_from_sign(jup_sign, moon_sign)
        jup_score = good_houses.get(jup_h, 5)

        ven_sign = transit_df[transit_df['Planet'] == 'Venus']['Zodiac_Sign'].values[0]
        ven_h = get_house_from_sign(ven_sign, moon_sign)
        ven_score = good_houses.get(ven_h, 5)

        moon_sign_t = transit_df[transit_df['Planet'] == 'Moon']['Zodiac_Sign'].values[0]
        moon_h = get_house_from_sign(moon_sign_t, asc_sign)
        moon_score = good_houses.get(moon_h, 5)

        sat_sign = transit_df[transit_df['Planet'] == 'Saturn']['Zodiac_Sign'].values[0]
        sat_h = get_house_from_sign(sat_sign, moon_sign)
        malefic = -15 if sat_h in [1, 5, 9] else 0

        dasha_bonus = 18 if current_maha in ['Jupiter', 'Venus', 'Mercury', 'Moon'] else 8

        total = min(max(jup_score + ven_score + moon_score + malefic + dasha_bonus, 5), 100)
        return total, jup_h, ven_h, moon_h
    except:
        return 40, 6, 6, 6

def get_current_maha(maha_dict, now, tz):
    for info in maha_dict.values():
        start = datetime.fromisoformat(info["start_time"].replace(" ", "T"))
        end = datetime.fromisoformat(info["end_time"].replace(" ", "T"))
        if start.tzinfo is None:
            start = tz.localize(start)
            end = tz.localize(end)
        if start <= now <= end:
            return info["Lord"]
    return "Unknown"
