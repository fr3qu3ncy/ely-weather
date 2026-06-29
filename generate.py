#!/usr/bin/env python3
"""
Generate static weather website for Ely, Cambridgeshire.
Fetches from Open-Meteo, produces index.html + 7 day pages + styles.css.
Push to GitHub Pages at https://fr3qu3ncy.github.io/ely-weather/
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# ─── Config ───────────────────────────────────────────────────────────
LOCATION = "Ely, Cambridgeshire"
LAT = 52.25
LON = 0.15
TZ = "Europe/London"
GEOCODE_KEY = "69c9249c84a15174072507uym8e74af"
GEOCODE_URL = "https://geocode.maps.co/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

WMO = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"), 48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Freezing drizzle", "🌧️"), 57: ("Freezing drizzle", "🌧️"),
    61: ("Light rain", "🌦️"), 63: ("Rain", "🌧️"),
    65: ("Heavy rain", "🌧️"), 66: ("Freezing rain", "🌧️"),
    67: ("Freezing rain", "🌧️"),
    71: ("Light snow", "🌨️"), 73: ("Snow", "🌨️"),
    75: ("Heavy snow", "❄️"), 77: ("Snow grains", "❄️"),
    80: ("Light showers", "🌦️"), 81: ("Showers", "🌧️"),
    82: ("Heavy showers", "🌧️"),
    85: ("Light snow showers", "🌨️"), 86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm w/ hail", "⛈️"),
    99: ("Severe thunderstorm", "⛈️"),
}

# ─── Fetch helpers ────────────────────────────────────────────────────
def geocode(query: str) -> str:
    url = f"{GEOCODE_URL}?q={urllib.parse.quote(query)}&limit=1&api_key={GEOCODE_KEY}"
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())
    return data[0]["display_name"] if data else query

def fetch_daily() -> dict:
    """Fetch daily forecast (7 days)."""
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "timezone": TZ,
        "forecast_days": 7,
        "daily": "sunrise,sunset,temperature_2m_max,temperature_2m_min,"
                 "wind_speed_10m_max,wind_gusts_10m_max,rain_sum,"
                 "precipitation_probability_max,uv_index_max,"
                 "sunshine_duration,weather_code,precipitation_sum",
    })
    with urllib.request.urlopen(f"{WEATHER_URL}?{params}") as r:
        return json.loads(r.read())

def fetch_current() -> dict:
    """Fetch current weather + current-hour details."""
    # current_weather gives temp, wind, weather code
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "timezone": TZ,
        "current_weather": "true",
    })
    with urllib.request.urlopen(f"{WEATHER_URL}?{params}") as r:
        cw_data = json.loads(r.read())

    # hourly for current hour gives apparent temp, humidity, pressure
    params2 = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "timezone": TZ,
        "forecast_days": 1,
        "hourly": "apparent_temperature,relative_humidity_2m,pressure_msl",
    })
    with urllib.request.urlopen(f"{WEATHER_URL}?{params2}") as r:
        hr_data = json.loads(r.read())

    # Find the current hour
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%dT%H:%M")
    times = hr_data.get("hourly", {}).get("time", [])
    idx = 0
    for i, t in enumerate(times):
        if t >= now_str:
            idx = i
            break

    cw = cw_data.get("current_weather", {})
    hr = hr_data.get("hourly", {})
    return {
        "temperature": cw.get("temperature"),
        "apparent_temp": hr.get("apparent_temperature", [None])[idx] if idx < len(hr.get("apparent_temperature", [])) else None,
        "humidity": hr.get("relative_humidity_2m", [None])[idx] if idx < len(hr.get("relative_humidity_2m", [])) else None,
        "pressure": hr.get("pressure_msl", [None])[idx] if idx < len(hr.get("pressure_msl", [])) else None,
        "wind_speed": cw.get("windspeed"),
        "wind_direction": cw.get("winddirection"),
        "weather_code": cw.get("weathercode"),
        "time": cw.get("time"),
    }

def fetch_hourly(date_str: str) -> dict:
    """Fetch hourly data for a specific date (24h window)."""
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "timezone": TZ,
        "start_date": date_str, "end_date": date_str,
        "hourly": "temperature_2m,apparent_temperature,weather_code,"
                  "cloud_cover,precipitation,precipitation_probability,"
                  "wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
                  "uv_index,relative_humidity_2m,sunshine_duration,"
                  "pressure_msl",
    })
    with urllib.request.urlopen(f"{WEATHER_URL}?{params}") as r:
        return json.loads(r.read())

def fetch_hourly_7d() -> dict:
    """Fetch 7 days of hourly data in one call."""
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "timezone": TZ,
        "forecast_days": 7,
        "hourly": "temperature_2m,apparent_temperature,weather_code,"
                  "cloud_cover,precipitation,precipitation_probability,"
                  "wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
                  "uv_index,relative_humidity_2m,sunshine_duration,"
                  "pressure_msl,is_day",
    })
    with urllib.request.urlopen(f"{WEATHER_URL}?{params}") as r:
        return json.loads(r.read())

# ─── Data processing ─────────────────────────────────────────────────
def process_weather():
    location_name = geocode(LOCATION)
    daily_data = fetch_daily()
    current_data = fetch_current()

    days = []
    dates = daily_data["daily"]["time"]
    for i, date in enumerate(dates):
        dt = datetime.strptime(date, "%Y-%m-%d")
        hourly_data = fetch_hourly(date)
        days.append({
            "date": date,
            "day_name": "Today" if i == 0 else dt.strftime("%A"),
            "short_day": "Today" if i == 0 else dt.strftime("%a %d %b"),
            "day_num": dt.day,
            "month": dt.strftime("%b"),
            "is_today": i == 0,
            "weather_code": daily_data["daily"]["weather_code"][i],
            "temp_max": daily_data["daily"]["temperature_2m_max"][i],
            "temp_min": daily_data["daily"]["temperature_2m_min"][i],
            "uv_max": daily_data["daily"]["uv_index_max"][i],
            "rain_sum": daily_data["daily"]["rain_sum"][i],
            "precip_prob": daily_data["daily"]["precipitation_probability_max"][i],
            "wind_max": daily_data["daily"]["wind_speed_10m_max"][i],
            "wind_gust_max": daily_data["daily"]["wind_gusts_10m_max"][i],
            "sunrise": daily_data["daily"]["sunrise"][i],
            "sunset": daily_data["daily"]["sunset"][i],
            "sunshine": daily_data["daily"]["sunshine_duration"][i] / 3600,
            "hourly": hourly_data.get("hourly", {}),
        })

    # Current weather - fetch_current() already returns processed dict
    current = current_data

    return location_name, current, days

# ─── HTML generation ─────────────────────────────────────────────────
CSS = """
/* ─── Reset & base ───────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface-hover: #232733;
  --border: #2a2e3a;
  --text: #e4e6ed;
  --text-dim: #8b8fa3;
  --accent: #60a5fa;
  --accent-glow: rgba(96,165,250,0.15);
  --rain: #38bdf8;
  --sun: #fbbf24;
  --wind: #a78bfa;
  --temp-warm: #fb923c;
  --temp-cool: #38bdf8;
  --radius: 16px;
  --radius-sm: 10px;
}
html { font-size: 16px; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ─── Header ─────────────────────────────────────────────── */
header {
  padding: 2rem 1.5rem 1rem;
  text-align: center;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, #161922 0%, var(--bg) 100%);
}
header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 0.25rem;
}
header .subtitle {
  color: var(--text-dim);
  font-size: 0.9rem;
}
header .updated {
  color: var(--text-dim);
  font-size: 0.75rem;
  margin-top: 0.5rem;
  opacity: 0.7;
}

/* ─── Container ──────────────────────────────────────────── */
.container {
  max-width: 960px;
  margin: 0 auto;
  padding: 1.5rem;
}

/* ─── Index: card grid ───────────────────────────────────── */
.forecast-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}
.card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--accent);
  opacity: 0;
  transition: opacity 0.2s;
}
.card:hover {
  background: var(--surface-hover);
  border-color: var(--accent);
  transform: translateY(-2px);
}
.card:hover::before { opacity: 1; }

/* Today card — taller, spans 2 rows */
.card.today {
  grid-row: span 2;
  border-color: var(--accent);
  background: linear-gradient(135deg, var(--surface) 0%, #1e2235 100%);
}
.card.today::before { opacity: 1; }
.card.today .today-label {
  display: inline-block;
  background: var(--accent);
  color: var(--bg);
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  margin-bottom: 0.75rem;
}

/* ─── Card content ───────────────────────────────────────── */
.card-day {
  font-size: 0.8rem;
  color: var(--text-dim);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}
.card-icon {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}
.card-condition {
  font-size: 0.72rem;
  color: var(--text-dim);
  margin-bottom: 0.75rem;
  line-height: 1.3;
  word-wrap: break-word;
  hyphens: auto;
}
.card-temp {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
}
.card-temp .high { color: var(--temp-warm); }
.card-temp .low { color: var(--temp-cool); }
.card-stats {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.card-stat {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
}
.card-stat .label { color: var(--text-dim); }
.card-stat .value { font-weight: 600; }

/* ─── Current weather (in today's card) ──────────────────── */
.current-section {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}
.current-temp {
  font-size: 3rem;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 0.25rem;
}
.current-details {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--text-dim);
}
.current-details span { color: var(--text); font-weight: 600; }

/* ─── Day detail page ────────────────────────────────────── */
.detail-back {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--text-dim);
  font-size: 0.85rem;
  margin-bottom: 1.5rem;
  padding: 0.4rem 0.75rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  transition: all 0.2s;
}
.detail-back:hover {
  color: var(--text);
  border-color: var(--accent);
  text-decoration: none;
}

.detail-header {
  margin-bottom: 2rem;
}
.detail-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}
.detail-header .condition {
  color: var(--text-dim);
  font-size: 1rem;
}

/* Current weather block (today only) */
.current-block {
  background: linear-gradient(135deg, #1e2235, var(--surface));
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}
.current-block .section-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--accent);
  margin-bottom: 0.75rem;
}
.current-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.current-main {
  grid-column: 1;
}
.current-main .big-temp {
  font-size: 3.5rem;
  font-weight: 800;
  line-height: 1;
}
.current-main .big-icon {
  font-size: 3rem;
}
.current-meta {
  grid-column: 2;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  justify-content: center;
}
.current-meta-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
}
.current-meta-item .lbl { color: var(--text-dim); }
.current-meta-item .val { font-weight: 600; }

/* Section cards */
.section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1rem;
}
.section-label {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-dim);
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.section-label .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

/* Stat grid inside sections */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}
.stat-item {
  background: rgba(255,255,255,0.03);
  border-radius: var(--radius-sm);
  padding: 0.75rem;
}
.stat-item .stat-label {
  font-size: 0.7rem;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}
.stat-item .stat-value {
  font-size: 1.25rem;
  font-weight: 700;
}
.stat-item .stat-value.temp-warm { color: var(--temp-warm); }
.stat-item .stat-value.temp-cool { color: var(--temp-cool); }
.stat-item .stat-unit {
  font-size: 0.75rem;
  color: var(--text-dim);
  margin-left: 0.25rem;
}

/* ─── Hourly cards ──────────────────────────────────────── */
.hourly-section {
  margin-top: 1.5rem;
}
.hourly-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hour-card {
  display: grid;
  grid-template-columns: 52px 1fr;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.25);
  transition: all 0.3s ease;
}
.hour-card.current-hour {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent), 0 4px 16px rgba(96,165,250,0.2);
  background: linear-gradient(135deg, #1e2235, var(--surface));
}
.hour-card.current-hour .hour-time {
  color: var(--accent);
}
.hour-now-badge {
  display: none;
  font-size: 0.55rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--bg);
  background: var(--accent);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
}
.hour-card.current-hour .hour-now-badge {
  display: inline-block;
}
/* Past hours: washed out, compact (temp, feels, wind, gust only) */
.hour-card.past-hour {
  opacity: 0.35;
}
.hour-card.past-hour .hour-metric-detail {
  display: none;
}
.hour-card.past-hour .hour-icon {
  display: none;
}
.hour-card.past-hour .hour-left {
  padding: 0.3rem 0.3rem;
}
.hour-card.past-hour .hour-time {
  font-size: 0.95rem;
}
.hour-card.past-hour .hour-right {
  padding: 0.3rem;
  gap: 2px;
}
.hour-card.past-hour .hour-metric {
  padding: 0.2rem 0.15rem;
  background: transparent;
}
.hour-card.past-hour .hour-metric-value {
  font-size: 0.85rem;
}
.hour-card.past-hour .hour-metric-label {
  font-size: 0.55rem;
}
.hour-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0.6rem 0.4rem;
  border-right: 1px solid var(--border);
  gap: 0.2rem;
}
.hour-time {
  font-size: 1rem;
  font-weight: 800;
  color: var(--text);
}
.hour-icon {
  font-size: 1.5rem;
  line-height: 1;
}
.hour-right {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 2px;
  padding: 0.5rem;
}
.hour-metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.3rem 0.2rem;
  border-radius: 6px;
  background: rgba(255,255,255,0.02);
}
.hour-metric-label {
  font-size: 0.55rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-dim);
  margin-bottom: 0.15rem;
}
.hour-metric-value {
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.2;
}
.hour-metric-unit {
  font-size: 0.6rem;
  color: var(--text-dim);
  font-weight: 400;
}
/* Color classes for metric values */
.val-warm     { color: #fb923c; }
.val-hot      { color: #ef4444; }
.val-cool     { color: #38bdf8; }
.val-cold     { color: #818cf8; }
.val-dry      { color: #4ade80; }
.val-drizzle  { color: #38bdf8; }
.val-rainy    { color: #2563eb; }
.val-wet      { color: #7c3aed; }
.val-calm     { color: #4ade80; }
.val-breezy   { color: #fbbf24; }
.val-windy    { color: #f97316; }
.val-stormy   { color: #ef4444; }
.val-clear    { color: #fbbf24; }
.val-cloudy   { color: #94a3b8; }
.val-overcast { color: #64748b; }
.val-humid-low    { color: #4ade80; }
.val-humid-mid    { color: #fbbf24; }
.val-humid-high   { color: #38bdf8; }
.val-humid-soak   { color: #7c3aed; }
.val-uv-low  { color: #4ade80; }
.val-uv-mod  { color: #fbbf24; }
.val-uv-high { color: #f97316; }
.val-uv-ext  { color: #ef4444; }
.val-press-high { color: #4ade80; }
.val-press-mid  { color: #fbbf24; }
.val-press-low  { color: #ef4444; }
.val-sun-high { color: #fbbf24; }
.val-sun-mid  { color: #f59e0b; }
.val-sun-low  { color: #94a3b8; }
.val-feels-warm { color: #fb923c; }
.val-feels-hot  { color: #ef4444; }
.val-feels-cool { color: #38bdf8; }
.val-feels-cold { color: #818cf8; }

/* Bar charts */
.bar-container {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.bar {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
  min-width: 40px;
}
.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}
.bar-fill.temp-high { background: var(--temp-warm); }
.bar-fill.temp-low { background: var(--temp-cool); }
.bar-fill.rain { background: var(--rain); }
.bar-fill.wind { background: var(--wind); }
.bar-fill.sun { background: var(--sun); }
.bar-fill.cloud { background: var(--text-dim); }
.bar-fill.uv { background: linear-gradient(90deg, #4ade80, #fbbf24, #ef4444); }
.bar-value {
  font-size: 0.75rem;
  font-weight: 600;
  min-width: 3rem;
  text-align: right;
}

/* ─── Day separator (multi-day hourly page) ──────────────── */
.day-separator {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 1.25rem 0 0.75rem;
  padding: 0.5rem 0;
}
.day-separator::before,
.day-separator::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}
.day-separator .day-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--accent);
  white-space: nowrap;
}
.day-separator .day-date {
  font-size: 0.7rem;
  color: var(--text-dim);
  white-space: nowrap;
}

/* ─── Hourly card: button-style link on index ────────────── */
.card.hourly-link {
  grid-column: span 2;
  border-color: var(--sun);
  background: var(--surface);
  padding: 0.75rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.85rem;
  letter-spacing: 0.03em;
  color: var(--sun);
  min-height: auto;
}
.card.hourly-link:hover {
  background: #1e2235;
}
.card.hourly-link::before { display: none; }

/* ─── Activities card ──────────────────────────────────────────── */
.card.activities-card {
  grid-column: span 2;
  border-color: var(--accent);
  padding: 1.25rem;
}
.card.activities-card::before { display: none; }
.activities-header {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-dim);
  margin-bottom: 0.75rem;
}
.activity-slot {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border);
}
.activity-slot:last-child { border-bottom: none; }
.activity-icon {
  font-size: 2.25rem;
  flex-shrink: 0;
  width: 3rem;
  text-align: center;
}
.activity-info {
  flex: 1;
  min-width: 0;
}
.activity-name {
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--text-dim);
  margin-bottom: 0.2rem;
}
.activity-time {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.01em;
}
.activity-duration {
  font-size: 0.75rem;
  color: var(--accent);
  margin-top: 0.15rem;
  font-weight: 500;
}

/* ─── Footer ─────────────────────────────────────────────── */
footer {
  text-align: center;
  padding: 2rem 1.5rem;
  color: var(--text-dim);
  font-size: 0.75rem;
  border-top: 1px solid var(--border);
  margin-top: 2rem;
}

/* ─── Responsive ─────────────────────────────────────────── */
@media (max-width: 600px) {
  .forecast-grid { grid-template-columns: repeat(2, 1fr); }
  .card.today { grid-column: span 2; }
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .current-grid { grid-template-columns: 1fr; }
  .current-meta { grid-column: 1; }
}

/* ─── Live weather indicators ────────────────────────────── */
.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.65rem;
  color: var(--text-dim);
  margin-top: 0.4rem;
}
.live-badge .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #4ade80;
  animation: pulse 2s infinite;
}
.live-badge.loading .dot { background: var(--accent); }
.live-badge.error .dot { background: #ef4444; animation: none; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.live-temp { font-size: 3rem; font-weight: 800; line-height: 1; }
.live-details { display: flex; flex-direction: column; gap: 0.3rem; margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-dim); }
.live-details span { color: var(--text); font-weight: 600; }
.live-big-temp { font-size: 3.5rem; font-weight: 800; line-height: 1; }
.live-meta-item { display: flex; justify-content: space-between; font-size: 0.9rem; }
.live-meta-item .lbl { color: var(--text-dim); }
.live-meta-item .val { font-weight: 600; }
"""

def wmo_info(code: int) -> tuple:
    return WMO.get(code, (f"Code {code}", "🌡️"))[::-1]

# ─── Live weather JS ──────────────────────────────────────────────────
LIVE_JS = '''<script>
(function(){
  var CK="ely_weather_now",CT=600000;
  var W={0:["Clear sky","\\u2600\\ufe0f"],1:["Mainly clear","\\ud83c\\udf24\\ufe0f"],2:["Partly cloudy","\\u26c5"],3:["Overcast","\\u2601\\ufe0f"],45:["Fog","\\ud83c\\udf2b\\ufe0f"],48:["Rime fog","\\ud83c\\udf2b\\ufe0f"],51:["Light drizzle","\\ud83c\\udf26\\ufe0f"],53:["Moderate drizzle","\\ud83c\\udf26\\ufe0f"],55:["Dense drizzle","\\ud83c\\udf27\\ufe0f"],56:["Freezing drizzle","\\ud83c\\udf27\\ufe0f"],57:["Dense freezing drizzle","\\ud83c\\udf27\\ufe0f"],61:["Slight rain","\\ud83c\\udf26\\ufe0f"],63:["Moderate rain","\\ud83c\\udf27\\ufe0f"],65:["Heavy rain","\\ud83c\\udf27\\ufe0f"],66:["Freezing rain","\\ud83c\\udf27\\ufe0f"],67:["Heavy freezing rain","\\ud83c\\udf27\\ufe0f"],71:["Slight snow","\\ud83c\\udf28\\ufe0f"],73:["Moderate snow","\\u2744\\ufe0f"],75:["Heavy snow","\\u2744\\ufe0f"],77:["Snow grains","\\u2744\\ufe0f"],80:["Light showers","\\ud83c\\udf26\\ufe0f"],81:["Moderate showers","\\ud83c\\udf27\\ufe0f"],82:["Heavy showers","\\ud83c\\udf27\\ufe0f"],85:["Light snow showers","\\ud83c\\udf28\\ufe0f"],86:["Heavy snow showers","\\u2744\\ufe0f"],95:["Thunderstorm","\\u26c8\\ufe0f"],96:["Thunderstorm w/ hail","\\u26c8\\ufe0f"],99:["Severe thunderstorm","\\u26c8\\ufe0f"]};
  var D=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
  function wd(d){return D[Math.round(d/22.5)%16]}
  function wmo(c){return W[c]||["Unknown","\\ud83c\\udf21\\ufe0f"]}
  function ts(){return new Date().toLocaleTimeString("en-GB",{hour:"2-digit",minute:"2-digit"})}
  function updI(d){
    var b=document.getElementById("live-badge-index"),t=document.getElementById("live-temp-index"),
        f=document.getElementById("live-feels-index"),h=document.getElementById("live-humid-index"),
        w=document.getElementById("live-wind-index"),p=document.getElementById("live-pressure-index");
    if(!t)return;var c=wmo(d.code);
    if(b){b.className="live-badge";b.innerHTML='<span class="dot"></span> Updated '+ts()}
    if(t)t.textContent=c[1]+" "+Math.round(d.temp)+"\\u00b0C";
    if(f)f.textContent=Math.round(d.ap)+"\\u00b0C";
    if(h)h.textContent=d.hu+"%";
    if(w)w.textContent=d.ws+" km/h "+wd(d.wd);
    if(p&&d.pr!==null)p.textContent=Math.round(d.pr)+" hPa";
  }
  function updD(d){
    var b=document.getElementById("live-badge-day"),ic=document.getElementById("live-icon-day"),
        t=document.getElementById("live-temp-day"),de=document.getElementById("live-desc-day"),
        f=document.getElementById("live-feels-day"),h=document.getElementById("live-humid-day"),
        w=document.getElementById("live-wind-day"),p=document.getElementById("live-pressure-day");
    if(!t&&!ic)return;var c=wmo(d.code);
    if(b){b.className="live-badge";b.innerHTML='<span class="dot"></span> Updated '+ts()}
    if(ic)ic.textContent=c[1];if(t)t.textContent=d.temp.toFixed(1)+"\\u00b0C";
    if(de)de.textContent=c[0];if(f)f.textContent=d.ap.toFixed(1)+"\\u00b0C";
    if(h)h.textContent=d.hu+"%";if(w)w.textContent=d.ws+" km/h "+wd(d.wd);
    if(p&&d.pr!==null)p.textContent=Math.round(d.pr)+" hPa";
  }
  function hc(){try{var c=localStorage.getItem(CK);if(!c)return false;
    var j=JSON.parse(c);if(Date.now()-j.ts>CT)return false;
    if(document.getElementById("live-temp-index"))updI(j);
    if(document.getElementById("live-temp-day"))updD(j);return true}catch(e){return false}}
  async function go(){
    try{var r=await fetch("https://api.open-meteo.com/v1/forecast?latitude=52.25&longitude=0.15&timezone=Europe%2FLondon&current_weather=true&hourly=apparent_temperature,relative_humidity_2m,pressure_msl&forecast_days=1");
      var d=await r.json(),now=new Date(),ns=now.toISOString().slice(0,13);
      var tm=d.hourly?d.hourly.time:[],ix=0;
      for(var i=0;i<tm.length;i++){if(tm[i]>=ns){ix=i;break}}
      var cw=d.current_weather||{},hr=d.hourly||{};
      var data={temp:cw.temperature,code:cw.weathercode,ws:cw.windspeed,wd:cw.winddirection,
        ap:(hr.apparent_temperature&&hr.apparent_temperature[ix])??cw.temperature,
        hu:(hr.relative_humidity_2m&&hr.relative_humidity_2m[ix])??0,
        pr:(hr.pressure_msl&&hr.pressure_msl[ix])??null};
      localStorage.setItem(CK,JSON.stringify({ts:Date.now(),temp:data.temp,code:data.code,ws:data.ws,wd:data.wd,ap:data.ap,hu:data.hu,pr:data.pr}));
      if(document.getElementById("live-temp-index"))updI(data);
      if(document.getElementById("live-temp-day"))updD(data);
    }catch(e){
      var bi=document.getElementById("live-badge-index"),bd=document.getElementById("live-badge-day");
      if(bi){bi.className="live-badge error";bi.innerHTML='<span class="dot"></span> Live data unavailable'}
      if(bd){bd.className="live-badge error";bd.innerHTML='<span class="dot"></span> Live data unavailable'}
    }
  }
  if(!hc())go();
})();
</script>'''

CURRENT_HOUR_JS = '''<script>
(function(){
  function highlightNow(){
    var now=new Date(), ts=now.toISOString().slice(0,13);
    document.querySelectorAll(".hour-card.current-hour").forEach(function(c){c.classList.remove("current-hour")});
    document.querySelectorAll(".hour-card.past-hour").forEach(function(c){c.classList.remove("past-hour")});
    document.querySelectorAll(".hour-card").forEach(function(c){
      var ct=c.getAttribute("data-time");
      if(!ct) return;
      if(ct < ts) c.classList.add("past-hour");
    });
    var card=document.querySelector('.hour-card[data-time="'+ts+'"]');
    if(card) card.classList.add("current-hour");
  }
  highlightNow();
  setInterval(highlightNow, 60000);
})();
</script>'''

def sunrise_str(iso: str) -> str:
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M")
    return dt.strftime("%H:%M")

def sunset_str(iso: str) -> str:
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M")
    return dt.strftime("%H:%M")

def fmt(val, fmt_str=".0f", default="—"):
    """Format a numeric value, returning default if None."""
    if val is None:
        return default
    return f"{val:{fmt_str}}"

def wind_dir(deg: int) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(deg / 22.5) % 16]

def make_bar_html(pct: float, cls: str, value_str: str) -> str:
    pct = max(0, min(100, pct))
    return f'''<div class="bar-container">
      <div class="bar"><div class="bar-fill {cls}" style="width:{pct}%"></div></div>
      <span class="bar-value">{value_str}</span>
    </div>'''

def gen_css() -> str:
    return CSS

def gen_index(location_name: str, current: dict, days: list, activities = None):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    cw_code = current["weather_code"]
    cw_icon, cw_desc = wmo_info(cw_code)

    cards_html = ""
    for d in days:
        icon, desc = wmo_info(d["weather_code"])
        date_slug = d["date"]
        link = f'day-{date_slug}.html'

        if d["is_today"]:
            # Current weather section — static fallback, JS updates live
            at = current.get('apparent_temp') or current.get('temperature')
            hu = current.get('humidity') or 0
            ws = current.get('wind_speed') or 0
            wd = current.get('wind_direction') or 0
            cur_html = f'''
<div class="current-section" id="live-current-index">
  <div class="today-label">Now</div>
  <div class="live-badge loading" id="live-badge-index"><span class="dot"></span> Loading live data…</div>
  <div class="live-temp" id="live-temp-index">{cw_icon} {d['temp_max']:.0f}°C</div>
  <div class="live-details" id="live-details-index">
    <div>Feels like <span id="live-feels-index">{at:.0f}°C</span></div>
    <div>Humidity <span id="live-humid-index">{hu}%</span></div>
    <div>Wind <span id="live-wind-index">{ws:.0f} km/h {wind_dir(wd)}</span></div>'''
            if current.get('pressure'):
                cur_html += f'''
    <div>Pressure <span id="live-pressure-index">{current['pressure']:.0f} hPa</span></div>'''
            cur_html += f'''
  </div>
</div>'''
        else:
            cur_html = ""

        cards_html += f'''
<a href="{link}" class="card {'today' if d['is_today'] else ''}" style="text-decoration:none;color:inherit;">
  {cur_html}
  <div class="card-day">{d['short_day']}</div>
  <div class="card-icon">{icon}</div>
  <div class="card-condition">{desc}</div>
  <div class="card-temp">
    <span class="high">{d['temp_max']:.0f}°</span>
    <span class="low">{d['temp_min']:.0f}°</span>
  </div>
  <div class="card-stats">
    <div class="card-stat"><span class="label">💧 Rain</span><span class="value">{d['rain_sum']:.1f}mm ({d['precip_prob']}%)</span></div>
    <div class="card-stat"><span class="label">⚡ Wind</span><span class="value">{d['wind_max']:.0f}/{d['wind_gust_max']:.0f} km/h</span></div>
    <div class="card-stat"><span class="label">🌞 Sun</span><span class="value">{d['sunshine']:.0f}h</span></div>
    <div class="card-stat"><span class="label">🔆 UV</span><span class="value">{d['uv_max']:.1f}</span></div>
  </div>
</a>'''
        if d['is_today']:
            # Hourly forecast card — placed right under Now
            cards_html += f'''
<a href="hourly.html" class="card hourly-link" style="text-decoration:none;color:inherit;">
  <span>Hourly Forecast</span>
</a>'''
            # Activities card — after hourly button
            if activities:
                act_cards = ""
                for act in activities:
                    act_cards += f'''
<div class="activity-slot">
  <div class="activity-icon">{act["icon"]}</div>
  <div class="activity-info">
    <div class="activity-name">{act["name"]}</div>
    <div class="activity-time">{act["day"]}, {act["start"]}–{act["end"]}</div>
    <div class="activity-duration">{act["duration"]}h window</div>
  </div>
</div>'''
                cards_html += f'''
<div class="card activities-card">
  <div class="activities-header">Recommended Activities</div>
  {act_cards}
</div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weather in Ely</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>🌤️ Ely Weather</h1>
  <div class="subtitle">{location_name}</div>
  <div class="updated">Generated {now_str} BST</div>
</header>
<div class="container">
  <div class="forecast-grid">
    {cards_html}
  </div>
</div>
<footer>
  Data from Open-Meteo · Static site regenerated hourly · Current weather updates live
</footer>
{LIVE_JS}
</body>
</html>'''

def gen_day(location_name: str, day: dict, current: dict) -> str:
    icon, desc = wmo_info(day["weather_code"])
    hourly = day["hourly"]
    times = hourly.get("time", [])

    # Current weather block (only for today) — static fallback, JS updates live
    current_block = ""
    if day["is_today"]:
        cw_icon, cw_desc = wmo_info(current["weather_code"])
        ct = current.get("temperature") or 0
        cat = current.get("apparent_temp") or ct
        chu = current.get("humidity") or 0
        cws = current.get("wind_speed") or 0
        cwd = current.get("wind_direction") or 0
        cp = current.get("pressure") or 0
        current_block = f'''
<div class="current-block" id="live-current-day">
  <div class="section-label">Current Conditions</div>
  <div class="live-badge loading" id="live-badge-day"><span class="dot"></span> Loading live data…</div>
  <div class="current-grid">
    <div class="current-main">
      <div class="big-icon" id="live-icon-day">{cw_icon}</div>
      <div class="live-big-temp" id="live-temp-day">{ct:.1f}°C</div>
      <div style="color:var(--text-dim);font-size:0.85rem;margin-top:0.25rem;" id="live-desc-day">{cw_desc}</div>
    </div>
    <div class="current-meta">
      <div class="live-meta-item"><span class="lbl">Feels like</span><span class="val" id="live-feels-day">{cat:.1f}°C</span></div>
      <div class="live-meta-item"><span class="lbl">Humidity</span><span class="val" id="live-humid-day">{chu}%</span></div>
      <div class="live-meta-item"><span class="lbl">Wind</span><span class="val" id="live-wind-day">{cws:.0f} km/h {wind_dir(cwd)}</span></div>
      <div class="live-meta-item"><span class="lbl">Pressure</span><span class="val" id="live-pressure-day">{cp:.0f} hPa</span></div>
    </div>
  </div>
</div>'''

    # ─── Temperature section ────────────────────────────────
    avg_temp = (day["temp_max"] + day["temp_min"]) / 2
    temp_range = day["temp_max"] - day["temp_min"]
    high_pct = min(100, max(0, ((day["temp_max"] + 5) / 40) * 100))
    low_pct = min(100, max(0, ((day["temp_min"] + 5) / 40) * 100))
    temp_section = f'''
<div class="section">
  <div class="section-label"><span class="dot" style="background:var(--temp-warm)"></span> Temperature</div>
  <div class="stat-grid">
    <div class="stat-item">
      <div class="stat-label">High</div>
      <div class="stat-value temp-warm">{day['temp_max']:.0f}<span class="stat-unit">°C</span></div>
      {make_bar_html(high_pct, 'temp-high', f'{day["temp_max"]:.0f}°')}
    </div>
    <div class="stat-item">
      <div class="stat-label">Low</div>
      <div class="stat-value temp-cool">{day['temp_min']:.0f}<span class="stat-unit">°C</span></div>
      {make_bar_html(low_pct, 'temp-low', f'{day["temp_min"]:.0f}°')}
    </div>
    <div class="stat-item">
      <div class="stat-label">Average</div>
      <div class="stat-value">{avg_temp:.0f}<span class="stat-unit">°C</span></div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Range</div>
      <div class="stat-value">{temp_range:.0f}<span class="stat-unit">°C</span></div>
    </div>
  </div>
</div>'''

    # ─── Sunshine section ───────────────────────────────────
    sun_pct = min(100, (day["sunshine"] / 17) * 100)
    uv_pct = min(100, (day["uv_max"] / 11) * 100)
    sun_section = f'''
<div class="section">
  <div class="section-label"><span class="dot" style="background:var(--sun)"></span> Sunshine & UV</div>
  <div class="stat-grid">
    <div class="stat-item">
      <div class="stat-label">Sunshine</div>
      <div class="stat-value">{day['sunshine']:.1f}<span class="stat-unit">hours</span></div>
      {make_bar_html(sun_pct, 'sun', f'{day["sunshine"]:.1f}h')}
    </div>
    <div class="stat-item">
      <div class="stat-label">UV Index</div>
      <div class="stat-value">{day['uv_max']:.1f}</div>
      {make_bar_html(uv_pct, 'uv', f'{day["uv_max"]:.1f}') }
    </div>
    <div class="stat-item">
      <div class="stat-label">Sunrise</div>
      <div class="stat-value">🌅 {sunrise_str(day['sunrise'])}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Sunset</div>
      <div class="stat-value">🌇 {sunset_str(day['sunset'])}</div>
    </div>
  </div>
</div>'''

    # ─── Rain section ───────────────────────────────────────
    rain_pct = min(100, (day["rain_sum"] / 20) * 100)
    rain_section = f'''
<div class="section">
  <div class="section-label"><span class="dot" style="background:var(--rain)"></span> Rain & Precipitation</div>
  <div class="stat-grid">
    <div class="stat-item">
      <div class="stat-label">Total Rain</div>
      <div class="stat-value">{day['rain_sum']:.1f}<span class="stat-unit">mm</span></div>
      {make_bar_html(rain_pct, 'rain', f'{day["rain_sum"]:.1f}mm')}
    </div>
    <div class="stat-item">
      <div class="stat-label">Chance</div>
      <div class="stat-value">{day['precip_prob']}<span class="stat-unit">%</span></div>
      {make_bar_html(day['precip_prob'], 'rain', f'{day["precip_prob"]}%')}
    </div>
  </div>
</div>'''

    # ─── Wind section ───────────────────────────────────────
    wind_pct = min(100, (day["wind_max"] / 60) * 100)
    gust_pct = min(100, (day["wind_gust_max"] / 80) * 100)
    wind_section = f'''
<div class="section">
  <div class="section-label"><span class="dot" style="background:var(--wind)"></span> Wind</div>
  <div class="stat-grid">
    <div class="stat-item">
      <div class="stat-label">Max Speed</div>
      <div class="stat-value">{day['wind_max']:.0f}<span class="stat-unit">km/h</span></div>
      {make_bar_html(wind_pct, 'wind', f'{day["wind_max"]:.0f}')}
    </div>
    <div class="stat-item">
      <div class="stat-label">Max Gusts</div>
      <div class="stat-value">{day['wind_gust_max']:.0f}<span class="stat-unit">km/h</span></div>
      {make_bar_html(gust_pct, 'wind', f'{day["wind_gust_max"]:.0f}')}
    </div>
  </div>
</div>'''

    # ─── Hourly cards ───────────────────────────────────────
    def temp_color(val):
        if val is None: return ""
        if val >= 20: return "val-hot"
        if val >= 15: return "val-warm"
        if val >= 10: return "val-cool"
        return "val-cold"

    def feels_color(val):
        if val is None: return ""
        if val >= 20: return "val-feels-hot"
        if val >= 15: return "val-feels-warm"
        if val >= 10: return "val-feels-cool"
        return "val-feels-cold"

    def rain_color(val):
        if val is None: return ""
        if val == 0: return "val-dry"
        if val < 2: return "val-drizzle"
        if val < 10: return "val-rainy"
        return "val-wet"

    def wind_color(val):
        if val is None: return ""
        if val < 15: return "val-calm"
        if val < 30: return "val-breezy"
        if val < 50: return "val-windy"
        return "val-stormy"

    def cloud_color(val):
        if val is None: return ""
        if val < 30: return "val-clear"
        if val < 70: return "val-cloudy"
        return "val-overcast"

    def humid_color(val):
        if val is None: return ""
        if val < 40: return "val-humid-low"
        if val < 60: return "val-humid-mid"
        if val < 80: return "val-humid-high"
        return "val-humid-soak"

    def uv_color(val):
        if val is None: return ""
        if val < 3: return "val-uv-low"
        if val < 6: return "val-uv-mod"
        if val < 8: return "val-uv-high"
        return "val-uv-ext"

    def press_color(val):
        if val is None: return ""
        if val >= 1015: return "val-press-high"
        if val >= 1005: return "val-press-mid"
        return "val-press-low"

    def sun_color(val):
        if val is None: return ""
        dur = val / 3600 if val else 0
        if dur >= 0.5: return "val-sun-high"
        if dur >= 0.1: return "val-sun-mid"
        return "val-sun-low"

    hourly_html = ""
    if times:
        cards = ""
        for i in range(min(24, len(times))):
            t = times[i]
            tc = hourly.get("temperature_2m", [None]*24)[i]
            at = hourly.get("apparent_temperature", [None]*24)[i]
            wc = hourly.get("weather_code", [0]*24)[i]
            pr = hourly.get("precipitation", [0]*24)[i]
            pp = hourly.get("precipitation_probability", [0]*24)[i]
            ws = hourly.get("wind_speed_10m", [0]*24)[i]
            wd = hourly.get("wind_direction_10m", [0]*24)[i]
            cc = hourly.get("cloud_cover", [0]*24)[i]
            sun = hourly.get("sunshine_duration", [0]*24)[i]
            uv = hourly.get("uv_index", [0]*24)[i]
            hu = hourly.get("relative_humidity_2m", [0]*24)[i]
            ps = hourly.get("pressure_msl", [0]*24)[i]

            h_icon, h_desc = wmo_info(wc)

            cards += f'''<div class="hour-card" data-time="{t}">
              <div class="hour-left">
                <span class="hour-now-badge">NOW</span>
                <span class="hour-time">{t[11:13]}:00</span>
                <span class="hour-icon">{h_icon}</span>
              </div>
              <div class="hour-right">
                <div class="hour-metric hour-metric-temp">
                  <span class="hour-metric-label">Temp</span>
                  <span class="hour-metric-value {temp_color(tc)}">{tc:.0f}°</span>
                </div>
                <div class="hour-metric hour-metric-feels">
                  <span class="hour-metric-label">Feels</span>
                  <span class="hour-metric-value {feels_color(at)}">{at:.0f}°</span>
                </div>
                <div class="hour-metric hour-metric-wind">
                  <span class="hour-metric-label">Wind</span>
                  <span class="hour-metric-value {wind_color(ws)}">{ws:.0f}</span>
                </div>
                <div class="hour-metric hour-metric-gust">
                  <span class="hour-metric-label">Gust</span>
                  <span class="hour-metric-value {wind_color(hourly.get('wind_gusts_10m',[0]*24)[i])}">{hourly.get('wind_gusts_10m',[0]*24)[i]:.0f}</span>
                </div>
                <div class="hour-metric hour-metric-detail">
                  <span class="hour-metric-label">Dir</span>
                  <span class="hour-metric-value {wind_color(ws)}">{wind_dir(wd)}</span>
                </div>
                <div class="hour-metric hour-metric-detail">
                  <span class="hour-metric-label">Rain</span>
                  <span class="hour-metric-value {rain_color(pp)}">{pp}%</span>
                </div>
                <div class="hour-metric hour-metric-detail">
                  <span class="hour-metric-label">Rain</span>
                  <span class="hour-metric-value {rain_color(pr)}">{pr:.1f}<span class="hour-metric-unit">mm</span></span>
                </div>
                <div class="hour-metric hour-metric-detail">
                  <span class="hour-metric-label">Cloud</span>
                  <span class="hour-metric-value {cloud_color(cc)}">{cc}%</span>
                </div>
                <div class="hour-metric hour-metric-detail">
                  <span class="hour-metric-label">Humid</span>
                  <span class="hour-metric-value {humid_color(hu)}">{hu}%</span>
                </div>
                <div class="hour-metric hour-metric-detail">
                  <span class="hour-metric-label">UV</span>
                  <span class="hour-metric-value {uv_color(uv)}">{uv:.1f}</span>
                </div>
                <div class="hour-metric hour-metric-detail">
                  <span class="hour-metric-label">Sun</span>
                  <span class="hour-metric-value {sun_color(sun)}">{sun/3600:.1f}h</span>
                </div>
                <div class="hour-metric hour-metric-detail">
                  <span class="hour-metric-label">Press</span>
                  <span class="hour-metric-value {press_color(ps)}">{ps:.0f}</span>
                </div>
              </div>
            </div>'''

        hourly_html = f'''
<div class="section hourly-section">
  <div class="section-label">Hourly Forecast</div>
  <div class="hourly-list">{cards}</div>
</div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{day['day_name']} — Ely Weather</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>🌤️ Ely Weather</h1>
  <div class="subtitle">{location_name}</div>
</header>
<div class="container">
  <a href="index.html" class="detail-back">← Back to forecast</a>
  <div class="detail-header">
    <h2>{icon} {day['day_name']}</h2>
    <div class="condition">{desc}</div>
  </div>
  {current_block}
  {temp_section}
  {sun_section}
  {rain_section}
  {wind_section}
  {hourly_html}
</div>
<footer>
  Data from Open-Meteo · <a href="index.html">7-day forecast</a>
</footer>
{LIVE_JS}
{CURRENT_HOUR_JS if day["is_today"] else ""}
</body>
</html>'''

# ─── Multi-day hourly JS ─────────────────────────────────────────────
HOURLY_JS = '''<script>
(function(){
  function highlightNow(){
    var now=new Date(), ts=now.toISOString().slice(0,13);
    document.querySelectorAll(".hour-card.current-hour").forEach(function(c){c.classList.remove("current-hour")});
    document.querySelectorAll(".hour-card.past-hour").forEach(function(c){c.classList.remove("past-hour")});
    document.querySelectorAll(".hour-card").forEach(function(c){
      var ct=c.getAttribute("data-time");
      if(!ct) return;
      if(ct < ts) c.classList.add("past-hour");
    });
    var card=document.querySelector('.hour-card[data-time="'+ts+'"]');
    if(card) card.classList.add("current-hour");
  }
  highlightNow();
  setInterval(highlightNow, 60000);
})();
</script>'''

def gen_hourly(location_name: str, hourly_7d: dict) -> str:
    """Generate the hourly forecast page spanning all 7 days."""
    times = hourly_7d.get("time", [])

    def temp_color(val):
        if val is None: return ""
        if val >= 20: return "val-hot"
        if val >= 15: return "val-warm"
        if val >= 10: return "val-cool"
        return "val-cold"

    def feels_color(val):
        if val is None: return ""
        if val >= 20: return "val-feels-hot"
        if val >= 15: return "val-feels-warm"
        if val >= 10: return "val-feels-cool"
        return "val-feels-cold"

    def rain_color(val):
        if val is None: return ""
        if val == 0: return "val-dry"
        if val < 2: return "val-drizzle"
        if val < 10: return "val-rainy"
        return "val-wet"

    def wind_color(val):
        if val is None: return ""
        if val < 15: return "val-calm"
        if val < 30: return "val-breezy"
        if val < 50: return "val-windy"
        return "val-stormy"

    def cloud_color(val):
        if val is None: return ""
        if val < 30: return "val-clear"
        if val < 70: return "val-cloudy"
        return "val-overcast"

    def humid_color(val):
        if val is None: return ""
        if val < 40: return "val-humid-low"
        if val < 60: return "val-humid-mid"
        if val < 80: return "val-humid-high"
        return "val-humid-soak"

    def uv_color(val):
        if val is None: return ""
        if val < 3: return "val-uv-low"
        if val < 6: return "val-uv-mod"
        if val < 8: return "val-uv-high"
        return "val-uv-ext"

    def press_color(val):
        if val is None: return ""
        if val >= 1015: return "val-press-high"
        if val >= 1005: return "val-press-mid"
        return "val-press-low"

    def sun_color(val):
        if val is None: return ""
        dur = val / 3600 if val else 0
        if dur >= 0.5: return "val-sun-high"
        if dur >= 0.1: return "val-sun-mid"
        return "val-sun-low"

    cards = ""
    current_day = None
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for i in range(len(times)):
        t = times[i]
        # Parse date for day separator
        dt = datetime.strptime(t, "%Y-%m-%dT%H:%M")
        day_str = dt.strftime("%Y-%m-%d")

        if day_str != current_day:
            current_day = day_str
            day_name = day_names[dt.weekday()]
            date_display = f"{dt.day} {month_names[dt.month - 1]} {dt.year}"
            if dt.date() == datetime.now().date():
                cards += f'<div class="day-separator"><span class="day-label">Today</span><span class="day-date">{date_display}</span></div>'
            else:
                cards += f'<div class="day-separator"><span class="day-label">{day_name}</span><span class="day-date">{date_display}</span></div>'

        tc = hourly_7d.get("temperature_2m", [None]*len(times))[i]
        at = hourly_7d.get("apparent_temperature", [None]*len(times))[i]
        wc = hourly_7d.get("weather_code", [0]*len(times))[i]
        pr = hourly_7d.get("precipitation", [0]*len(times))[i]
        pp = hourly_7d.get("precipitation_probability", [0]*len(times))[i]
        ws = hourly_7d.get("wind_speed_10m", [0]*len(times))[i]
        wd = hourly_7d.get("wind_direction_10m", [0]*len(times))[i]
        cc = hourly_7d.get("cloud_cover", [0]*len(times))[i]
        sun = hourly_7d.get("sunshine_duration", [0]*len(times))[i]
        uv = hourly_7d.get("uv_index", [0]*len(times))[i]
        hu = hourly_7d.get("relative_humidity_2m", [0]*len(times))[i]
        ps = hourly_7d.get("pressure_msl", [0]*len(times))[i]

        h_icon, h_desc = wmo_info(wc)

        cards += f'''<div class="hour-card" data-time="{t[:13]}">
          <div class="hour-left">
            <span class="hour-now-badge">NOW</span>
            <span class="hour-time">{t[11:13]}:00</span>
            <span class="hour-icon">{h_icon}</span>
          </div>
          <div class="hour-right">
            <div class="hour-metric hour-metric-temp">
              <span class="hour-metric-label">Temp</span>
              <span class="hour-metric-value {temp_color(tc)}">{tc:.0f}°</span>
            </div>
            <div class="hour-metric hour-metric-feels">
              <span class="hour-metric-label">Feels</span>
              <span class="hour-metric-value {feels_color(at)}">{at:.0f}°</span>
            </div>
            <div class="hour-metric hour-metric-wind">
              <span class="hour-metric-label">Wind</span>
              <span class="hour-metric-value {wind_color(ws)}">{ws:.0f}</span>
            </div>
            <div class="hour-metric hour-metric-gust">
              <span class="hour-metric-label">Gust</span>
              <span class="hour-metric-value {wind_color(hourly_7d.get('wind_gusts_10m',[0]*len(times))[i])}">{hourly_7d.get('wind_gusts_10m',[0]*len(times))[i]:.0f}</span>
            </div>
            <div class="hour-metric hour-metric-detail">
              <span class="hour-metric-label">Dir</span>
              <span class="hour-metric-value {wind_color(ws)}">{wind_dir(wd)}</span>
            </div>
            <div class="hour-metric hour-metric-detail">
              <span class="hour-metric-label">Rain</span>
              <span class="hour-metric-value {rain_color(pp)}">{pp}%</span>
            </div>
            <div class="hour-metric hour-metric-detail">
              <span class="hour-metric-label">Rain</span>
              <span class="hour-metric-value {rain_color(pr)}">{pr:.1f}<span class="hour-metric-unit">mm</span></span>
            </div>
            <div class="hour-metric hour-metric-detail">
              <span class="hour-metric-label">Cloud</span>
              <span class="hour-metric-value {cloud_color(cc)}">{cc}%</span>
            </div>
            <div class="hour-metric hour-metric-detail">
              <span class="hour-metric-label">Humid</span>
              <span class="hour-metric-value {humid_color(hu)}">{hu}%</span>
            </div>
            <div class="hour-metric hour-metric-detail">
              <span class="hour-metric-label">UV</span>
              <span class="hour-metric-value {uv_color(uv)}">{uv:.1f}</span>
            </div>
            <div class="hour-metric hour-metric-detail">
              <span class="hour-metric-label">Sun</span>
              <span class="hour-metric-value {sun_color(sun)}">{sun/3600:.1f}h</span>
            </div>
            <div class="hour-metric hour-metric-detail">
              <span class="hour-metric-label">Press</span>
              <span class="hour-metric-value {press_color(ps)}">{ps:.0f}</span>
            </div>
          </div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hourly Forecast — Ely Weather</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>🌤️ Ely Weather</h1>
  <div class="subtitle">{location_name}</div>
</header>
<div class="container">
  <a href="index.html" class="detail-back">← Back to forecast</a>
  <div class="detail-header">
    <h2>Hourly Forecast</h2>
    <div class="condition">7-day hourly breakdown</div>
  </div>
  <div class="hourly-list">{cards}</div>
</div>
<footer>
  Data from Open-Meteo · <a href="index.html">7-day forecast</a>
</footer>
{HOURLY_JS}
</body>
</html>'''

# ─── Activity recommendations ──────────────────────────────────────────
def find_activities(hourly: dict) -> list:
    """Scan hourly data for suitable activity windows. Returns list of activity dicts."""
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    clouds = hourly.get("cloud_cover", [])
    winds = hourly.get("wind_speed_10m", [])
    gusts = hourly.get("wind_gusts_10m", [])
    is_day = hourly.get("is_day", [])
    precip = hourly.get("precipitation", [])
    now = datetime.now(timezone.utc).astimezone(ZoneInfo(TZ))
    # Skip to next hour
    now_hour = now.replace(minute=0, second=0, microsecond=0)
    skip_before = None
    tz_info = ZoneInfo(TZ)
    for i, t in enumerate(times):
        dt_t = datetime.fromisoformat(t).replace(tzinfo=tz_info)
        if dt_t >= now_hour:
            skip_before = i
            break

    slots = []

    def fmt(t):
        return datetime.fromisoformat(t).strftime("%H:%M")

    def fmt_end(t):
        # End of the hour slot (start + 1h)
        return (datetime.fromisoformat(t) + timedelta(hours=1)).strftime("%H:%M")

    def day_label(t):
        dt = datetime.fromisoformat(t)
        today = now.date()
        tomorrow = today + timedelta(days=1)
        if dt.date() == today:
            return "Today"
        elif dt.date() == tomorrow:
            return "Tomorrow"
        return dt.strftime("%a %d %b")

    def find_consecutive(check, min_hours, start_from=0):
        best = None
        run = 0
        run_start = None
        for i in range(start_from, len(times)):
            if check(i):
                if run == 0:
                    run_start = i
                run += 1
                if run >= min_hours and (best is None or run_start < best):
                    best = run_start
            else:
                run = 0
                run_start = None
        if best is not None:
            length = 0
            for i in range(best, len(times)):
                if check(i):
                    length += 1
                else:
                    break
            return best, length
        return None, 0

    # Wash car: daylight, no rain, cloud > 45%, 13 <= temp <= 29, min 1 hour
    def wash_ok(i):
        return is_day[i] == 1 and precip[i] == 0 and clouds[i] > 45 and 13 <= temps[i] <= 29
    start, length = find_consecutive(wash_ok, 1, skip_before or 0)
    if start is not None:
        end_idx = min(start + length, len(times))
        slots.append({
            "name": "Wash car",
            "icon": "🚗",
            "start": fmt(times[start]),
            "end": fmt_end(times[end_idx - 1]),
            "day": day_label(times[start]),
            "duration": length,
        })

    # Astro photography: is_day==0, cloud <= 10%, wind < 16.09 km/h (10 mph), gust < 32.19 km/h (20 mph), min 3 hours
    def astro_ok(i):
        return is_day[i] == 0 and clouds[i] <= 10 and winds[i] < 16.09 and gusts[i] < 32.19
    start, length = find_consecutive(astro_ok, 3, skip_before or 0)
    if start is not None:
        end_idx = min(start + length, len(times))
        slots.append({
            "name": "Astro photography",
            "icon": "🔭",
            "start": fmt(times[start]),
            "end": fmt_end(times[end_idx - 1]),
            "day": day_label(times[start]),
            "duration": length,
        })

    # Gardening: no rain 4h before slot, daylight, no rain during slot,
    # wind < 24.14 km/h (15 mph), cloud <= 60%, min 2 hours

    def garden_ok(i):
        # Check 4h dry period before this index
        if i < 4:
            return False
        for j in range(i - 4, i):
            if precip[j] > 0:
                return False
        # Slot conditions
        if is_day[i] != 1:
            return False
        if precip[i] > 0:
            return False
        if winds[i] >= 24.14:
            return False
        if clouds[i] > 60:
            return False
        return True

    # Find first consecutive 2-hour garden window
    garden_start = None
    garden_len = 0
    for i in range((skip_before or 0), len(times)):
        if garden_ok(i):
            if garden_start is None:
                garden_start = i
                garden_len = 1
            else:
                garden_len += 1
            if garden_len >= 2:
                break
        else:
            garden_start = None
            garden_len = 0

    if garden_start is not None and garden_len >= 2:
        end_idx = min(garden_start + garden_len, len(times))
        slots.append({
            "name": "Gardening",
            "icon": "🌱",
            "start": fmt(times[garden_start]),
            "end": fmt_end(times[end_idx - 1]),
            "day": day_label(times[garden_start]),
            "duration": garden_len,
        })

    return slots

# ─── Main ─────────────────────────────────────────────────────────────
def main():
    out_dir = Path("/tmp/ely-weather")
    out_dir.mkdir(exist_ok=True)

    print("Fetching location...")
    location_name, current, days = process_weather()
    print(f"  → {location_name}")

    print("Fetching 7-day hourly data...")
    hourly_7d_data = fetch_hourly_7d()
    hourly_7d = hourly_7d_data.get("hourly", {})
    print(f"  → {len(hourly_7d.get('time', []))} hours fetched")

    # Activities
    activities = find_activities(hourly_7d)
    print(f"  → {len(activities)} activities found")

    # CSS
    print("Writing styles.css...")
    (out_dir / "styles.css").write_text(gen_css())

    # Index
    print("Writing index.html...")
    (out_dir / "index.html").write_text(gen_index(location_name, current, days, activities))

    # Day pages
    for d in days:
        path = out_dir / f"day-{d['date']}.html"
        path.write_text(gen_day(location_name, d, current))
        print(f"  → day-{d['date']}.html")

    # Hourly page
    print("Writing hourly.html...")
    (out_dir / "hourly.html").write_text(gen_hourly(location_name, hourly_7d))

    # CNAME for GitHub Pages custom domain (optional)
    # (out_dir / "CNAME").write_text("ely.fr3qu3ncy.com")

    # robots.txt
    (out_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n")

    # .nojekyll (tell GitHub not to process with Jekyll)
    (out_dir / ".nojekyll").write_text("")

    print(f"\n✅ Site generated in {out_dir}")

if __name__ == "__main__":
    main()
