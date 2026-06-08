"""City Comfort Index — Open-Meteo weather analytics dashboard.

Light "brutalist website" design: white canvas, terracotta hero, thick ink
borders, hard offset shadows, Darker Grotesque + JetBrains Mono. Combines the
clean brutalist skin with modern, live data visualizations (gauges, an animated
play-button scatter, a radar, a heatmap, a pulsing live bar).

Reads from the dbt mart models in DuckDB (not the raw API files):
    - mart_city_weather_summary  (one row per city)
    - fct_city_weather_day       (one row per city per day)
    - fct_air_quality_city_day   (one row per city per day)

Run from the project root:
    python -m streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import base64
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "weather_analytics.duckdb"

# Light brutalist palette
INK = "#111827"
PAPER = "#FFFFFF"
CREAM = "#FBFAF6"
TERRACOTTA = "#DD614C"
OCHRE = "#DAA144"
GREEN = "#16A34A"
COBALT = "#2563EB"
VIOLET = "#7C3AED"
DANGER = "#DC2626"
MUTED = "#6B7280"

CITY_COLORS = [TERRACOTTA, COBALT, OCHRE, GREEN, VIOLET]

# City spotlight photos (committed under streamlit_app/assets/cities, one per city)
ASSETS = Path(__file__).resolve().parent / "assets" / "cities"


def city_slug(name: str) -> str:
    """Accent-stripped lowercase alphanumeric slug, matching the photo filenames."""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", n.lower())


def city_photo(name: str) -> Path:
    return ASSETS / f"{city_slug(name)}.jpg"
CITY_BLURBS = {
    "Madrid": "Gran Vía at golden hour — the capital's restless heart.",
    "Barcelona": "Gaudí's Sagrada Família against the Mediterranean sky.",
    "Valencia": "Calatrava's City of Arts — the future on the Turia.",
    "Sevilla": "Plaza de España — Andalusian sun and tilework.",
    "Bilbao": "The Guggenheim's titanium curves on the Nervión.",
}
# Official municipal (city hall) websites — shown as a link on each spotlight card.
# All 58 verified reachable (region TLDs: .es default, .cat Catalonia, .gal Galicia, .eus Euskadi).
CITY_GOV = {
    "Madrid": "https://www.madrid.es",
    "Barcelona": "https://www.barcelona.cat",
    "Valencia": "https://www.valencia.es",
    "Sevilla": "https://www.sevilla.org",
    "Bilbao": "https://www.bilbao.eus",
    "Zaragoza": "https://www.zaragoza.es",
    "Málaga": "https://www.malaga.eu",
    "Murcia": "https://www.murcia.es",
    "Palma": "https://www.palma.cat",
    "Las Palmas de Gran Canaria": "https://www.laspalmasgc.es",
    "Alicante": "https://www.alicante.es",
    "Córdoba": "https://www.cordoba.es",
    "Valladolid": "https://www.valladolid.es",
    "Vigo": "https://www.vigo.org",
    "Gijón": "https://www.gijon.es",
    "A Coruña": "https://www.coruna.gal",
    "Granada": "https://www.granada.org",
    "Vitoria-Gasteiz": "https://www.vitoria-gasteiz.org",
    "Santa Cruz de Tenerife": "https://www.santacruzdetenerife.es",
    "Oviedo": "https://www.oviedo.es",
    "Pamplona": "https://www.pamplona.es",
    "Santander": "https://www.santander.es",
    "Cartagena": "https://www.cartagena.es",
    "Jerez de la Frontera": "https://www.jerez.es",
    "Almería": "https://www.almeria.es",
    "Donostia-San Sebastián": "https://www.donostia.eus",
    "Burgos": "https://www.aytoburgos.es",
    "Albacete": "https://www.albacete.es",
    "Castellón de la Plana": "https://www.castello.es",
    "Logroño": "https://www.logrono.es",
    "Badajoz": "https://www.aytobadajoz.es",
    "Salamanca": "https://www.aytosalamanca.es",
    "Huelva": "https://www.huelva.es",
    "Marbella": "https://www.marbella.es",
    "Lleida": "https://www.paeria.cat",
    "Tarragona": "https://www.tarragona.cat",
    "León": "https://www.aytoleon.es",
    "Cádiz": "https://institucional.cadiz.es",
    "Jaén": "https://www.aytojaen.es",
    "Ourense": "https://www.ourense.gal",
    "Girona": "https://www.girona.cat",
    "Lugo": "https://www.lugo.gal",
    "Cáceres": "https://www.ayto-caceres.es",
    "Toledo": "https://www.toledo.es",
    "Pontevedra": "https://www.pontevedra.gal",
    "Guadalajara": "https://www.guadalajara.es",
    "Ciudad Real": "https://www.ciudadreal.es",
    "Zamora": "https://www.zamora.es",
    "Palencia": "https://www.aytopalencia.es",
    "Ávila": "https://www.avila.es",
    "Cuenca": "https://www.cuenca.es",
    "Segovia": "https://www.segovia.es",
    "Soria": "https://www.soria.es",
    "Huesca": "https://www.huesca.es",
    "Teruel": "https://www.teruel.es",
    "Ceuta": "https://www.ceuta.es",
    "Melilla": "https://www.melilla.es",
    "Ibiza": "https://www.eivissa.es",
}

COMFORT_SCALE = [DANGER, TERRACOTTA, OCHRE, GREEN]   # low -> high (good)
AQI_SCALE = [GREEN, OCHRE, TERRACOTTA, DANGER]       # low (good) -> high (bad)
HEAT_SCALE = ["#1E3A8A", COBALT, GREEN, OCHRE, TERRACOTTA]  # cold -> hot

st.set_page_config(
    page_title="City Comfort Index",
    page_icon="◧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------- #
# Styling — brutalist website skin
# --------------------------------------------------------------------------- #
st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Darker+Grotesque:wght@600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap');

      html, body, [class*="css"] {{ font-family: 'JetBrains Mono', monospace; color: {INK}; }}
      /* Single cohesive cream canvas with one faint warm accent */
      .stApp {{ background:
          radial-gradient(1000px 400px at 90% -8%, rgba(221,97,76,.07), transparent 60%),
          {CREAM}; }}
      /* Website feel: hide Streamlit chrome */
      #MainMenu, footer {{ visibility: hidden; }}
      [data-testid="stToolbar"] {{ display: none; }}
      header[data-testid="stHeader"] {{ background: transparent; }}
      h1, h2, h3, h4 {{
        font-family: 'Darker Grotesque', sans-serif !important;
        font-weight: 900 !important; letter-spacing: -0.01em;
        text-transform: uppercase; color: {INK};
      }}
      .block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1340px; }}

      /* Top bar (sticky site nav) */
      .topbar {{
        position: sticky; top: 0; z-index: 50; background: {CREAM};
        display: flex; align-items: center; justify-content: space-between;
        gap: 1rem; flex-wrap: wrap; border-bottom: 3px solid {INK};
        padding: .5rem 0 .55rem; margin-bottom: 1.1rem;
      }}
      .wordmark {{ font-family: 'Darker Grotesque', sans-serif; font-weight: 900;
        font-size: 1.35rem; text-transform: uppercase; letter-spacing: -.01em; }}
      .wordmark .sq {{ display:inline-block; width:14px; height:14px; background:{TERRACOTTA};
        border:2px solid {INK}; margin-right:.5rem; transform: translateY(1px); }}

      /* Hero */
      .hero {{
        background: linear-gradient(120deg, {TERRACOTTA} 0%, #C2410C 100%);
        color: #fff; padding: 1.35rem 1.7rem;
        border: 4px solid {INK}; box-shadow: 10px 10px 0 {INK}; margin-bottom: 1.7rem;
      }}
      .hero h1 {{ margin: 0; font-size: clamp(2rem, 4.4vw, 2.9rem); line-height: .92; color: #fff !important; }}
      .hero h1 .lt {{ color: #FFFFFF !important; }}
      .hero h1 .dk {{ color: {INK} !important; }}
      .wm-dk {{ color: {INK}; }}
      .wm-ac {{ color: {TERRACOTTA}; }}
      .hero p {{ margin: .5rem 0 0; font-family: 'JetBrains Mono', monospace;
        font-size: clamp(.72rem, 1vw, .82rem); font-weight: 600; max-width: 720px; }}

      /* Live chips */
      .chips {{ display: flex; gap: .5rem; flex-wrap: wrap; }}
      .chip {{ display:inline-flex; align-items:center; gap:.45rem; white-space:nowrap;
        background:{PAPER}; border:2px solid {INK}; padding:.3rem .6rem;
        font-size:.75rem; font-weight:700; letter-spacing:.05em; }}
      .chip.muted {{ color:{MUTED}; }}
      .dot {{ width:9px; height:9px; border-radius:50%; background:{TERRACOTTA};
        box-shadow:0 0 0 0 rgba(221,97,76,.7); animation:pulse 1.6s infinite; }}
      @keyframes pulse {{
        0% {{ box-shadow:0 0 0 0 rgba(221,97,76,.7); }}
        70% {{ box-shadow:0 0 0 8px rgba(221,97,76,0); }}
        100% {{ box-shadow:0 0 0 0 rgba(221,97,76,0); }}
      }}

      /* Section eyebrow + header */
      .eyebrow {{ font-family:'JetBrains Mono',monospace; font-size:.75rem; font-weight:700;
        letter-spacing:.18em; color:{TERRACOTTA}; text-transform:uppercase; margin-top:.6rem; }}
      h2, h3 {{ border-bottom: 3px solid {INK}; padding-bottom: .15rem; }}

      /* Metric cards */
      div[data-testid="stMetric"] {{
        background:{PAPER}; border:3px solid {INK}; padding:.85rem 1rem;
        box-shadow:6px 6px 0 {INK};
      }}
      div[data-testid="stMetricLabel"] {{ overflow: visible !important; max-width: 100% !important; }}
      div[data-testid="stMetricLabel"] * {{ overflow: visible !important; text-overflow: clip !important; }}
      div[data-testid="stMetricLabel"] p {{ font-weight:700; text-transform:uppercase;
        font-size:.75rem; letter-spacing:.03em; color:{INK}; white-space:normal; line-height:1.2; }}
      div[data-testid="stMetricValue"] {{ font-family:'Darker Grotesque',sans-serif; font-weight:900; }}

      /* Framed charts + table */
      div[data-testid="stPlotlyChart"] {{
        border:3px solid {INK}; background:{PAPER}; padding:.55rem; box-shadow:6px 6px 0 {INK};
        overflow: hidden;
      }}
      div[data-testid="stDataFrame"] {{ border:3px solid {INK}; box-shadow:6px 6px 0 {INK}; }}

      section[data-testid="stSidebar"] {{ background:{CREAM}; border-right:3px solid {INK}; }}
      .footnote {{ font-family:'JetBrains Mono',monospace; color:{MUTED}; font-size:.76rem; line-height:1.55; }}
      .footer {{ border-top:3px solid {INK}; margin-top:2rem; padding-top:.8rem; }}

      /* City spotlight (NOWNESS-style cinematic carousel) */
      .spotlight {{ position:relative; height:430px; border:4px solid {INK};
        box-shadow:10px 10px 0 {INK}; background-size:cover; background-position:center;
        display:flex; align-items:flex-end; overflow:hidden; margin-bottom:.9rem; }}
      .spot-inner {{ width:100%; padding:1.4rem 1.7rem;
        background:linear-gradient(to top, rgba(0,0,0,.80), rgba(0,0,0,.20) 55%, transparent); }}
      .spot-kicker {{ color:#fff; font-family:'JetBrains Mono',monospace; font-size:.75rem;
        font-weight:700; letter-spacing:.16em; text-transform:uppercase; opacity:.92; }}
      .spot-city {{ color:#fff !important; font-family:'Darker Grotesque',sans-serif; font-weight:900;
        font-size:clamp(2.4rem,5vw,3.6rem); line-height:.9; margin:.1rem 0 .25rem; text-transform:uppercase; }}
      .spot-blurb {{ color:#f1f1f1; font-family:'JetBrains Mono',monospace; font-size:.8rem;
        margin:0 0 .75rem; max-width:640px; }}
      .spot-stats {{ display:flex; gap:.5rem; flex-wrap:wrap; }}
      .spot-stat {{ background:rgba(255,255,255,.14); border:2px solid rgba(255,255,255,.6);
        color:#fff; padding:.3rem .6rem; font-size:.75rem; font-weight:700; }}
      .thumb {{ width:100%; height:78px; object-fit:cover; border:2px solid {INK}; display:block; }}
      /* Spotlight chips + the City Hall link share one colour (white), never browser-blue */
      .spot-stat, a.spot-stat, a.spot-stat:link, a.spot-stat:visited, a.spot-stat:hover {{
        color:#fff !important; text-decoration:none !important; }}

      /* "At a glance" meter cards (replace the gauges) */
      .meter-card {{ background:{PAPER}; border:3px solid {INK}; box-shadow:6px 6px 0 {INK};
        padding:1rem 1.1rem 1.05rem; }}
      .meter-label {{ font-family:'JetBrains Mono',monospace; font-weight:700; text-transform:uppercase;
        font-size:.75rem; letter-spacing:.04em; color:{INK}; }}
      .meter-value {{ font-family:'Darker Grotesque',sans-serif; font-weight:900; font-size:2.7rem;
        line-height:1; margin:.15rem 0 .6rem; color:{INK}; }}
      .meter-track {{ height:14px; background:#EDEBE3; border:2px solid {INK}; }}
      .meter-fill {{ height:100%; }}
      .meter-scale {{ display:flex; justify-content:space-between; font-family:'JetBrains Mono',monospace;
        font-size:.75rem; color:{MUTED}; margin-top:.35rem; }}
      * {{ border-radius:0 !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


@st.cache_data
def img_b64(path: Path) -> str:
    """Base64-encode a local image so it can be inlined in CSS/HTML (works on Cloud)."""
    p = Path(path)
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def style_fig(fig: go.Figure, height: int = 340, bars: bool = False) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        font=dict(family="JetBrains Mono, monospace", size=12, color=INK),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=16, t=30, b=10),
        legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
        colorway=CITY_COLORS,
    )
    fig.update_xaxes(showline=True, linewidth=2, linecolor=INK, gridcolor="#ECEAE2", zeroline=False)
    fig.update_yaxes(showline=True, linewidth=2, linecolor=INK, gridcolor="#ECEAE2", zeroline=False)
    if bars:
        fig.update_traces(marker_line_color=INK, marker_line_width=1.2)
    return fig


def section(eyebrow: str, title: str) -> None:
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.subheader(title)


# --------------------------------------------------------------------------- #
# Data access (reads from marts)
# --------------------------------------------------------------------------- #
@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        st.error(
            f"DuckDB database not found at `{DB_PATH}`.\n\n"
            "Build it first: `python scripts/load_to_duckdb.py` then `dbt build`."
        )
        st.stop()
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(ttl=600)
def load_summary() -> pd.DataFrame:
    return get_connection().sql("select * from main.mart_city_weather_summary").df()


@st.cache_data(ttl=600)
def load_daily_weather() -> pd.DataFrame:
    return get_connection().sql(
        """
        select city_name, weather_date, temperature_2m_mean, temperature_2m_max,
               temperature_2m_min, precipitation_sum, wind_speed_10m_max,
               is_comfortable, is_rainy, is_windy, is_hot, is_freezing
        from main.fct_city_weather_day
        """
    ).df()


@st.cache_data(ttl=600)
def load_daily_aqi() -> pd.DataFrame:
    return get_connection().sql(
        "select city_name, air_quality_date, avg_european_aqi, avg_pm2_5 "
        "from main.fct_air_quality_city_day"
    ).df()


@st.cache_data(ttl=600)
def load_season_summary() -> pd.DataFrame:
    return get_connection().sql(
        "select city_name, season, total_days, avg_temperature_c, "
        "avg_max_temperature_c, avg_min_temperature_c, total_precipitation_mm, "
        "comfortable_days, rainy_days, hot_days, freezing_days, comfort_score "
        "from main.mart_city_season_summary"
    ).df()


@st.cache_data(ttl=600)
def load_extreme_events() -> pd.DataFrame:
    return get_connection().sql("select * from main.mart_extreme_events").df()


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
summary = load_summary()
weather = load_daily_weather()
aqi = load_daily_aqi()
season_summary = load_season_summary()
extreme_events = load_extreme_events()
weather["weather_date"] = pd.to_datetime(weather["weather_date"])
aqi["air_quality_date"] = pd.to_datetime(aqi["air_quality_date"])

# --------------------------------------------------------------------------- #
# Sidebar (reference only — the city picker lives up top in the main area)
# --------------------------------------------------------------------------- #
st.sidebar.header("About")
st.sidebar.markdown(
    """
    <div class="footnote">
    <b>MAIN MODEL GRAIN</b><br/>
    <code>mart_city_weather_summary</code>: one row per city.<br/>
    <code>fct_*_day</code>: one row per city per day.<br/><br/>
    <b>REPRODUCE</b><br/>
    1. <code>python scripts/extract_spain_cities.py</code><br/>
    2. <code>python scripts/load_to_duckdb.py</code><br/>
    3. <code>dbt build</code><br/>
    4. <code>streamlit run streamlit_app/app.py</code>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Top bar + hero
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="topbar"><div class="wordmark"><span class="sq"></span>CITY COMFORT INDEX</div>'
    '<div class="chip muted">OPEN-METEO · DBT · DUCKDB</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="hero">
      <h1>City Comfort Index</h1>
      <p>HOW PLEASANT IS THE WEATHER ACROSS SPAIN'S LARGEST CITIES? A LIVE COMFORT,
      CLIMATE AND AIR-QUALITY VIEW BUILT ON OPEN-METEO DATA — STRAIGHT FROM THE DBT MARTS.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Controls — prominent city picker + date range at the top of the page
# --------------------------------------------------------------------------- #
all_cities = sorted(summary["city_name"].tolist())
MAJOR_CITIES = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao"]
default_cities = [c for c in MAJOR_CITIES if c in all_cities] or all_cities

section("Controls", "Choose cities to display")
ctrl_l, ctrl_r = st.columns([2.1, 1])
with ctrl_l:
    show_all = st.checkbox(f"Show all {len(all_cities)} cities", value=False)
    if show_all:
        selected_cities = all_cities
    else:
        selected_cities = st.multiselect(
            "Cities on the dashboard",
            options=all_cities, default=default_cities,
            help=f"Type a name to add any of the {len(all_cities)} Spanish cities.",
        )
with ctrl_r:
    min_date = weather["weather_date"].min().date()
    max_date = weather["weather_date"].max().date()
    date_range = st.slider(
        "Date range", min_value=min_date, max_value=max_date,
        value=(min_date, max_date), format="DD MMM YYYY",
    )
st.caption(f"{len(all_cities)} cities available · {len(selected_cities)} selected")
if not selected_cities:
    st.warning("Pick at least one city above to see the dashboard.")
    st.stop()
start_date, end_date = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])

# --------------------------------------------------------------------------- #
# Apply filters
# --------------------------------------------------------------------------- #
w = weather[
    weather["city_name"].isin(selected_cities)
    & weather["weather_date"].between(start_date, end_date)
].copy()
a = aqi[
    aqi["city_name"].isin(selected_cities)
    & aqi["air_quality_date"].between(start_date, end_date)
].copy()
s = summary[summary["city_name"].isin(selected_cities)].copy()

if w.empty:
    st.warning("No data in the selected range. Widen the date filter.")
    st.stop()

ranking = (
    w.groupby("city_name")
    .agg(
        days=("weather_date", "count"),
        comfortable_days=("is_comfortable", "sum"),
        rainy_days=("is_rainy", "sum"),
        windy_days=("is_windy", "sum"),
        hot_days=("is_hot", "sum"),
        avg_temp=("temperature_2m_mean", "mean"),
    )
    .reset_index()
)
ranking["comfort_score"] = (100 * ranking["comfortable_days"] / ranking["days"]).round(1)
aqi_by_city = a.groupby("city_name")["avg_european_aqi"].mean().reset_index()
ranking = ranking.merge(aqi_by_city, on="city_name", how="left")
ranking["overall_comfort_index"] = (
    ranking["comfort_score"] - 0.5 * ranking["avg_european_aqi"].fillna(0)
).round(1)
ranking = ranking.sort_values("overall_comfort_index", ascending=False)
best_city = ranking.iloc[0]

def _zone_now(tz: str) -> str:
    """Current HH:MM:SS in an IANA timezone; falls back to UTC if tzdata is missing."""
    try:
        return datetime.now(ZoneInfo(tz)).strftime("%H:%M:%S")
    except Exception:
        return datetime.now(timezone.utc).strftime("%H:%M:%S") + " UTC"


@st.fragment(run_every="1s")
def live_status() -> None:
    spain = _zone_now("Europe/Madrid")       # mainland Spain (CET/CEST)
    canary = _zone_now("Atlantic/Canary")    # Canary Islands (1h behind)
    span = f"{start_date:%d %b %Y} – {end_date:%d %b %Y}"
    st.markdown(
        f"""
        <div class="chips" style="margin:.2rem 0 1.2rem">
          <span class="chip"><span class="dot"></span>LIVE</span>
          <span class="chip muted">🇪🇸 SPAIN {spain}</span>
          <span class="chip muted">🏝️ CANARY {canary}</span>
          <span class="chip muted">MONITORING {len(selected_cities)} CITIES</span>
          <span class="chip muted">WINDOW {span}</span>
          <span class="chip muted">{len(w):,} CITY-DAYS</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


live_status()

# --------------------------------------------------------------------------- #
# City spotlight — auto-rotating cinematic carousel with real city photos
# --------------------------------------------------------------------------- #
section("City spotlight", "Postcards from the data")
# The carousel rotates through the cities you select: a photo for the majors,
# a branded card otherwise. Each card links to the city's town hall when known.
spotlight_cities = selected_cities


@st.fragment(run_every="4s")
def city_spotlight() -> None:
    n = len(spotlight_cities)
    idx = st.session_state.get("spot_idx", 0) % n
    st.session_state["spot_idx"] = idx + 1
    city = spotlight_cities[idx]
    b64 = img_b64(city_photo(city))
    bg = f"url(data:image/jpeg;base64,{b64})" if b64 else "linear-gradient(125deg,#DD614C,#7C2D12)"
    row = summary[summary["city_name"] == city]
    temp = f"{row['avg_temperature_c'].iloc[0]:.1f} °C" if not row.empty else "—"
    comfort = f"{row['overall_comfort_index'].iloc[0]:.0f}" if not row.empty else "—"
    aqi_val = row["avg_air_quality_index"].iloc[0] if not row.empty else None
    aqi = f"{aqi_val:.0f}" if aqi_val is not None and pd.notna(aqi_val) else "—"
    blurb = CITY_BLURBS.get(city, "One of Spain's 58 monitored cities.")
    gov = CITY_GOV.get(city)
    gov_chip = (
        f'<a class="spot-stat" style="text-decoration:none" href="{gov}" '
        f'target="_blank" rel="noopener">CITY HALL &#8599;</a>'
    ) if gov else ""
    st.markdown(
        f"""
        <div class="spotlight" style="background-image:{bg};">
          <div class="spot-inner">
            <div class="spot-kicker">City spotlight &middot; {idx + 1}/{n} &middot; from your selection</div>
            <div class="spot-city">{city}</div>
            <div class="spot-blurb">{blurb}</div>
            <div class="spot-stats">
              <span class="spot-stat">{temp}</span>
              <span class="spot-stat">COMFORT {comfort}</span>
              <span class="spot-stat">AQI {aqi}</span>
              {gov_chip}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


city_spotlight()

# Thumbnail strip — photo cities within the current selection (cap to keep it tidy)
thumb_cities = [c for c in selected_cities if city_photo(c).exists()][:8]
if thumb_cities:
    tcols = st.columns(len(thumb_cities))
    for col, c in zip(tcols, thumb_cities):
        b = img_b64(city_photo(c))
        with col:
            st.markdown(
                f'<img class="thumb" src="data:image/jpeg;base64,{b}" alt="{c}" />',
                unsafe_allow_html=True,
            )
            st.caption(c)

st.markdown("")

# --------------------------------------------------------------------------- #
# KPI cards
# --------------------------------------------------------------------------- #
k1, k2, k3, k4 = st.columns(4)
k1.metric("Cities", len(selected_cities))
k2.metric("Avg temp", f"{w['temperature_2m_mean'].mean():.1f} °C")
k3.metric("Comfy days", int(ranking["comfortable_days"].sum()),
          help="Comfortable days: mean temp 18–26 °C and not rainy, windy, hot or freezing.")
k4.metric("Top city", best_city["city_name"],
          f"index {best_city['overall_comfort_index']:.1f}")

st.markdown("")


# --------------------------------------------------------------------------- #
# Gauges
# --------------------------------------------------------------------------- #
def meter_card(label, value, vmin, vmax, color, suffix=""):
    """A brutalist meter: big value + a progress bar showing where it sits on its scale."""
    pct = max(0.0, min(100.0, (float(value) - vmin) / (vmax - vmin) * 100))
    return f"""
    <div class="meter-card">
      <div class="meter-label">{label}</div>
      <div class="meter-value">{float(value):.1f}{suffix}</div>
      <div class="meter-track"><div class="meter-fill" style="width:{pct:.0f}%;background:{color};"></div></div>
      <div class="meter-scale"><span>{vmin:g}</span><span>{vmax:g}</span></div>
    </div>
    """


section("Instruments", "At a glance")
aqi_mean = a["avg_european_aqi"].mean() if not a.empty else 0.0
g1, g2, g3 = st.columns(3)
<<<<<<< Updated upstream
g1.markdown(meter_card("Overall comfort", ranking["overall_comfort_index"].mean(), -20, 100, TERRACOTTA),
            unsafe_allow_html=True)
g2.markdown(meter_card("Comfort score", ranking["comfort_score"].mean(), 0, 100, OCHRE),
            unsafe_allow_html=True)
g3.markdown(meter_card("Air quality · AQI", aqi_mean, 0, 100, GREEN), unsafe_allow_html=True)
=======
with g1:
    st.plotly_chart(gauge(
        ranking["overall_comfort_index"].mean(), "OVERALL COMFORT", -20, 40,
        [{"range": [-20, 0], "color": "#fde8e4"}, {"range": [0, 20], "color": "#fbf3dd"},
         {"range": [20, 40], "color": "#e3f5ea"}], TERRACOTTA), use_container_width=True)
with g2:
    st.plotly_chart(gauge(
        w["temperature_2m_mean"].mean(), "AVG TEMPERATURE", 0, 40,
        [{"range": [0, 18], "color": "#e6eefb"}, {"range": [18, 26], "color": "#e3f5ea"},
         {"range": [26, 40], "color": "#fde8e4"}], COBALT, " °C"), use_container_width=True)
with g3:
    aqi_mean = a["avg_european_aqi"].mean() if not a.empty else 0
    st.plotly_chart(gauge(
        aqi_mean, "AIR QUALITY (AQI)", 0, 100,
        [{"range": [0, 25], "color": "#e3f5ea"}, {"range": [25, 50], "color": "#fbf3dd"},
         {"range": [50, 100], "color": "#fde8e4"}], GREEN), use_container_width=True)
>>>>>>> Stashed changes


# --------------------------------------------------------------------------- #
# Overview: ranking + map
# --------------------------------------------------------------------------- #
section("Overview", "Comfort ranking & map")
o_left, o_right = st.columns([1.05, 1])
with o_left:
    # With many cities, focus the bar chart on the best + worst performers.
    if len(ranking) > 16:
        rank_plot = pd.concat([ranking.head(10), ranking.tail(5)])
        rank_note = f"Top 10 and bottom 5 of {len(ranking)} cities."
    else:
        rank_plot = ranking
        rank_note = None
    rank_height = max(320, 26 * len(rank_plot))
    fig_rank = px.bar(
        rank_plot, x="overall_comfort_index", y="city_name", orientation="h",
        color="overall_comfort_index", color_continuous_scale=COMFORT_SCALE,
        text="overall_comfort_index",
        labels={"overall_comfort_index": "Overall comfort index", "city_name": ""},
    )
    fig_rank.update_traces(textposition="outside", cliponaxis=False, textfont=dict(color=INK))
    fig_rank.update_layout(coloraxis_showscale=False, yaxis={"categoryorder": "total ascending"})
    fig_rank = style_fig(fig_rank, height=rank_height, bars=True)
    # extend the x-axis and right margin so the longest bar's value label isn't clipped
    xmax = ranking["overall_comfort_index"].max()
    fig_rank.update_xaxes(range=[ranking["overall_comfort_index"].min() - 3, xmax + max(6, xmax * 0.18)])
    fig_rank.update_layout(margin=dict(l=10, r=40, t=30, b=10))
    st.plotly_chart(fig_rank, width="stretch")
    if rank_note:
        st.caption(rank_note)
with o_right:
    # Use the date-filtered ranking (not whole-window summary) so the map and the
    # ranking bar always agree; pull coordinates/population from dim/summary.
    map_df = ranking.merge(
        s[["city_name", "latitude", "longitude", "population"]],
        on="city_name", how="left",
    )
    map_df["size"] = map_df["population"].clip(lower=1).pow(0.5)
    fig_map = px.scatter_mapbox(
        map_df, lat="latitude", lon="longitude", color="overall_comfort_index",
        size="size", hover_name="city_name", size_max=30, zoom=4.3,
        color_continuous_scale=COMFORT_SCALE,
        hover_data={"latitude": False, "longitude": False, "size": False,
                    "overall_comfort_index": ":.1f", "avg_temp": ":.1f"},
    )
    fig_map.update_layout(mapbox_style="carto-positron", height=340,
                          margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="rgba(0,0,0,0)",
                          font=dict(color=INK), coloraxis_colorbar=dict(title="COMFORT"))
    st.plotly_chart(fig_map, width="stretch")


# --------------------------------------------------------------------------- #
# Live explorer: animated scatter
# --------------------------------------------------------------------------- #
section("Live explorer", "Temperature × air quality over time ▶")
anim = w.merge(a.rename(columns={"air_quality_date": "weather_date"}),
               on=["city_name", "weather_date"], how="inner")
if not anim.empty:
    anim = anim.sort_values("weather_date")
    anim["day"] = anim["weather_date"].dt.strftime("%d %b")
    anim["precip_size"] = anim["precipitation_sum"].clip(lower=0) + 2
    show_labels = len(selected_cities) <= 8
    fig_anim = px.scatter(
        anim, x="temperature_2m_mean", y="avg_european_aqi",
        animation_frame="day", animation_group="city_name",
        color="city_name", size="precip_size", size_max=34,
        color_discrete_sequence=CITY_COLORS, text="city_name" if show_labels else None,
        range_x=[anim["temperature_2m_mean"].min() - 2, anim["temperature_2m_mean"].max() + 2],
        range_y=[max(0, anim["avg_european_aqi"].min() - 8), anim["avg_european_aqi"].max() + 8],
        labels={"temperature_2m_mean": "Mean temp (°C)", "avg_european_aqi": "European AQI",
                "city_name": "City"},
    )
    if show_labels:
        fig_anim.update_traces(textposition="top center", textfont=dict(size=10, color=MUTED))
    fig_anim.update_layout(transition={"duration": 300})
    st.plotly_chart(style_fig(fig_anim, height=440), width="stretch")
    st.caption("Press ▶ to watch each city drift through the period. Bubble size = daily precipitation.")
else:
    st.info("No overlapping weather + air-quality days in range.")


# --------------------------------------------------------------------------- #
# Climate: gradient area + radar
# --------------------------------------------------------------------------- #
section("Climate", "Trends & profiles")
c_left, c_right = st.columns([1.15, 1])
with c_left:
    fig_area = go.Figure()
    for i, city in enumerate(sorted(w["city_name"].unique())):
        d = w[w["city_name"] == city].sort_values("weather_date")
        color = CITY_COLORS[i % len(CITY_COLORS)]
        fig_area.add_trace(go.Scatter(
            x=d["weather_date"], y=d["temperature_2m_mean"], name=city, mode="lines",
            line=dict(color=color, width=2.6, shape="spline"),
        ))
    fig_area.update_layout(legend=dict(orientation="h", y=1.04, x=0))
    st.plotly_chart(style_fig(fig_area, height=360), width="stretch")
with c_right:
    metrics = ["Warmth", "Comfort", "Clean air", "Calm", "Dry"]
    radar = go.Figure()
    aqi_max = max(ranking["avg_european_aqi"].fillna(0).max(), 1)
    radar_cities = ranking.head(8)  # radar is unreadable beyond ~8 overlays
    for i, (_, r) in enumerate(radar_cities.iterrows()):
        warmth = min(100, max(0, (r["avg_temp"] / 30) * 100))
        comfort = r["comfort_score"]
        clean = 100 - min(100, (r["avg_european_aqi"] if pd.notna(r["avg_european_aqi"]) else 0) / aqi_max * 100)
        calm = 100 - (r["windy_days"] / r["days"] * 100)
        dry = 100 - (r["rainy_days"] / r["days"] * 100)
        color = CITY_COLORS[i % len(CITY_COLORS)]
        radar.add_trace(go.Scatterpolar(
            r=[warmth, comfort, clean, calm, dry], theta=metrics, fill="toself",
            name=r["city_name"], line=dict(color=color, width=2), fillcolor=_rgba(color, 0.08),
        ))
    radar.update_layout(
        template="plotly_white", height=360, paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono", size=11, color=INK),
        margin=dict(l=70, r=70, t=55, b=45),
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(range=[0, 100], gridcolor="#ECEAE2", showticklabels=False),
                   angularaxis=dict(gridcolor="#D9D6CC", tickfont=dict(size=10))),
        legend=dict(orientation="h", y=1.14, x=0),
    )
    st.plotly_chart(radar, width="stretch")
    if len(ranking) > len(radar_cities):
        st.caption(f"Radar shows the top {len(radar_cities)} of {len(ranking)} cities by comfort.")


# --------------------------------------------------------------------------- #
# Detail: heatmap + day types
# --------------------------------------------------------------------------- #
section("Detail", "Daily breakdown")
d_left, d_right = st.columns([1.2, 1])
with d_left:
    pivot = w.pivot_table(index="city_name", columns="weather_date",
                          values="temperature_2m_mean", aggfunc="mean")
    fig_heat = px.imshow(pivot, color_continuous_scale=HEAT_SCALE, aspect="auto",
                         labels={"x": "", "y": "", "color": "°C"})
    fig_heat.update_xaxes(showticklabels=True, tickformat="%d %b", nticks=10)
    st.plotly_chart(style_fig(fig_heat, height=300), width="stretch")
with d_right:
    melted = ranking.melt(
        id_vars="city_name",
        value_vars=["comfortable_days", "rainy_days", "windy_days", "hot_days"],
        var_name="condition", value_name="day_count",
    )
    melted["condition"] = melted["condition"].map({
        "comfortable_days": "Comfortable", "rainy_days": "Rainy",
        "windy_days": "Windy", "hot_days": "Hot",
    })
    fig_stack = px.bar(
        melted, x="city_name", y="day_count", color="condition",
        color_discrete_map={"Comfortable": GREEN, "Rainy": COBALT, "Windy": MUTED, "Hot": TERRACOTTA},
        labels={"city_name": "", "day_count": "Days", "condition": ""},
    )
    fig_stack.update_layout(legend=dict(orientation="h", y=1.06, x=0))
    st.plotly_chart(style_fig(fig_stack, height=300, bars=True), width="stretch")


# --------------------------------------------------------------------------- #
# Seasons — four-season comfort comparison (full year, from mart_city_season_summary)
# --------------------------------------------------------------------------- #
SEASON_ORDER = ["Winter", "Spring", "Summer", "Autumn"]
section("Seasons", "Four-season comfort")
seas = season_summary[season_summary["city_name"].isin(selected_cities)].copy()
seas["season"] = pd.Categorical(seas["season"], categories=SEASON_ORDER, ordered=True)
seas = seas.sort_values("season")
se_left, se_right = st.columns([1.3, 1])
with se_left:
    top_season_cities = ranking.head(8)["city_name"].tolist()
    seas_top = seas[seas["city_name"].isin(top_season_cities)]
    fig_se = px.bar(
        seas_top, x="season", y="comfort_score", color="city_name", barmode="group",
        color_discrete_sequence=CITY_COLORS,
        labels={"season": "", "comfort_score": "Comfort score", "city_name": ""},
    )
    fig_se.update_layout(legend=dict(orientation="h", y=1.06, x=0))
    st.plotly_chart(style_fig(fig_se, height=360, bars=True), width="stretch")
with se_right:
    seas_agg = (
        seas.groupby("season", observed=True)
        .agg(t=("avg_temperature_c", "mean"), cs=("comfort_score", "mean"))
        .reindex(SEASON_ORDER)
    )

    def _season_color(t: float) -> str:
        if pd.isna(t):
            return MUTED
        return ("#1E3A8A" if t < 6 else COBALT if t < 12 else GREEN
                if t < 18 else OCHRE if t < 24 else TERRACOTTA)

    cards = []
    for name in SEASON_ORDER:
        row = seas_agg.loc[name]
        t = row["t"]
        cs = row["cs"]
        col = _season_color(t)
        t_txt = "—" if pd.isna(t) else f"{t:.0f}°"
        cs_txt = "—" if pd.isna(cs) else f"{cs:.0f}"
        cards.append(
            f'<div class="seascard" style="border-left:6px solid {col}">'
            f'<div class="seasname">{name.upper()}</div>'
            f'<div class="seastemp" style="color:{col}">{t_txt}</div>'
            f'<div class="seasmeta">avg comfort {cs_txt}</div></div>'
        )
    st.markdown(
        """<style>
        .seasgrid{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;}
        .seascard{background:#fff;border:2px solid #111827;padding:.7rem .8rem;}
        .seasname{font-family:'JetBrains Mono',monospace;font-size:.68rem;letter-spacing:.1em;font-weight:700;color:#111827;}
        .seastemp{font-family:'Darker Grotesque','JetBrains Mono',monospace;font-size:2rem;font-weight:800;line-height:1.1;}
        .seasmeta{font-family:'JetBrains Mono',monospace;font-size:.66rem;color:#6B7280;}
        </style>"""
        + f'<div class="seasgrid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )
st.caption(
    "Meteorological seasons (Winter = Dec–Feb …). Uses the full year of weather, "
    "independent of the date filter above."
)

# --------------------------------------------------------------------------- #
# Extremes — heatwaves, cold snaps, heavy rain (full year, from mart_extreme_events)
# --------------------------------------------------------------------------- #
section("Extremes", "Heat, cold & rain")
ext = extreme_events[extreme_events["city_name"].isin(selected_cities)].copy()
ex_left, ex_right = st.columns([1.3, 1])
with ex_left:
    ext_top = ext.sort_values("heatwave_days", ascending=False).head(10)
    ext_melt = ext_top.melt(
        id_vars="city_name",
        value_vars=["heatwave_days", "cold_snap_days", "heavy_rain_days"],
        var_name="kind", value_name="days",
    )
    ext_melt["kind"] = ext_melt["kind"].map({
        "heatwave_days": "Heatwave", "cold_snap_days": "Cold snap", "heavy_rain_days": "Heavy rain",
    })
    fig_ex = px.bar(
        ext_melt, x="city_name", y="days", color="kind", barmode="group",
        color_discrete_map={"Heatwave": TERRACOTTA, "Cold snap": COBALT, "Heavy rain": GREEN},
        labels={"city_name": "", "days": "Days", "kind": ""},
    )
    fig_ex.update_layout(legend=dict(orientation="h", y=1.06, x=0))
    st.plotly_chart(style_fig(fig_ex, height=360, bars=True), width="stretch")
with ex_right:
    def _ext_card(title, row, value_col, streak_col, col, unit="days"):
        return (
            f'<div class="extcard" style="border-left:6px solid {col}">'
            f'<div class="extkind">{title}</div>'
            f'<div class="extcity">{row["city_name"]}</div>'
            f'<div class="extbig" style="color:{col}">{int(row[value_col])} <span>{unit}</span></div>'
            f'<div class="extmeta">longest streak {int(row[streak_col])} days</div></div>'
        )

    hottest = ext.sort_values("heatwave_days", ascending=False).iloc[0]
    coldest = ext.sort_values("cold_snap_days", ascending=False).iloc[0]
    wettest = ext.sort_values("heavy_rain_days", ascending=False).iloc[0]
    st.markdown(
        """<style>
        .extcard{background:#fff;border:2px solid #111827;padding:.6rem .8rem;margin-bottom:.55rem;}
        .extkind{font-family:'JetBrains Mono',monospace;font-size:.64rem;letter-spacing:.1em;font-weight:700;color:#6B7280;}
        .extcity{font-family:'Darker Grotesque','JetBrains Mono',monospace;font-size:1.15rem;font-weight:800;color:#111827;}
        .extbig{font-family:'Darker Grotesque','JetBrains Mono',monospace;font-size:1.7rem;font-weight:800;line-height:1.05;}
        .extbig span{font-size:.7rem;font-weight:700;}
        .extmeta{font-family:'JetBrains Mono',monospace;font-size:.64rem;color:#6B7280;}
        </style>"""
        + _ext_card("MOST HEATWAVE DAYS", hottest, "heatwave_days", "longest_heatwave", TERRACOTTA)
        + _ext_card("MOST COLD-SNAP DAYS", coldest, "cold_snap_days", "longest_cold_snap", COBALT)
        + _ext_card("MOST HEAVY-RAIN DAYS", wettest, "heavy_rain_days", "longest_wet_spell", GREEN),
        unsafe_allow_html=True,
    )
st.caption(
    "Heatwave = 3+ consecutive days max > 35 °C · Cold snap = 3+ days min < 0 °C · "
    "Heavy rain = 20+ mm. Computed with window functions over the full year."
)

# --------------------------------------------------------------------------- #
# Table + definitions + footer
# --------------------------------------------------------------------------- #
section("Reference", "City comfort table")


def aqi_band_chip(aqi: float):
    """Return (label, color) for a European AQI value, matching the dbt seed bands."""
    if pd.isna(aqi):
        return ("NO DATA", MUTED)
    for hi, label, col in [
        (20, "GOOD", GREEN), (40, "FAIR", "#7DA82B"), (60, "MODERATE", OCHRE),
        (80, "POOR", TERRACOTTA), (100, "VERY POOR", "#B5341F"),
    ]:
        if aqi < hi:
            return (label, col)
    return ("EXTREME", "#7F1D1D")


SORT_OPTS = {
    "Overall index": ("overall_comfort_index", False),
    "Comfort score": ("comfort_score", False),
    "Warmest": ("avg_temp", False),
    "Cleanest air": ("avg_european_aqi", True),
}
sc_l, _sc_r = st.columns([1, 3])
with sc_l:
    sort_label = st.selectbox("Sort by", list(SORT_OPTS), index=0, key="lb_sort")
order_col, asc = SORT_OPTS[sort_label]
tbl = ranking.sort_values(order_col, ascending=asc, na_position="last").reset_index(drop=True)

MEDALS = {0: "#DAA144", 1: "#C9C9C2", 2: "#C0845A"}  # gold / silver / bronze
rows_html = []
for i, r in tbl.iterrows():
    cs = float(r["comfort_score"])
    bar_w = max(4.0, min(100.0, cs))
    bar_col = GREEN if cs >= 50 else OCHRE if cs >= 25 else TERRACOTTA
    band, band_col = aqi_band_chip(r["avg_european_aqi"])
    aqi_txt = "—" if pd.isna(r["avg_european_aqi"]) else f"{r['avg_european_aqi']:.0f}"
    rank_bg = MEDALS.get(i, "transparent")
    rows_html.append(
        f'<div class="crow" style="animation-delay:{i * 0.03:.2f}s">'
        f'<span class="crank" style="background:{rank_bg}">{i + 1}</span>'
        f'<span class="ccity">{r["city_name"]}</span>'
        f'<span class="cbarwrap"><span class="cbar" style="--w:{bar_w:.0f}%;background:{bar_col}"></span>'
        f'<span class="cbarlab">{cs:.0f}</span></span>'
        f'<span class="cnum">{r["avg_temp"]:.1f}°</span>'
        f'<span class="cband" style="border-color:{band_col};color:{band_col}">{band} {aqi_txt}</span>'
        f'<span class="cnum cidx">{r["overall_comfort_index"]:.1f}</span>'
        "</div>"
    )
head_html = (
    '<div class="crow chead">'
    "<span>#</span><span>CITY</span><span>COMFORT SCORE</span><span>AVG</span>"
    "<span>AIR QUALITY</span><span>INDEX</span></div>"
)
st.markdown(
    """<style>
    .ctable{border:2px solid #111827;background:#111827;display:flex;flex-direction:column;gap:2px;}
    .crow{display:grid;grid-template-columns:44px 1.25fr 1.6fr 60px 138px 64px;align-items:center;
      gap:.7rem;padding:.5rem .85rem;background:#fff;opacity:0;transform:translateY(10px);
      animation:lbRowIn .5s ease forwards;}
    .crow:hover{background:#FBFAF6;}
    .chead{background:#111827;font-family:'JetBrains Mono',monospace;font-size:.64rem;
      letter-spacing:.09em;font-weight:700;opacity:1;transform:none;animation:none;}
    .chead span{color:#fff;}
    .crank{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
      border:2px solid #111827;font-family:'JetBrains Mono',monospace;font-weight:800;font-size:.82rem;color:#111827;}
    .ccity{font-family:'Darker Grotesque','JetBrains Mono',monospace;font-weight:800;font-size:.96rem;color:#111827;}
    .cbarwrap{position:relative;height:22px;background:#EDEAE0;border:2px solid #111827;overflow:hidden;}
    .cbar{display:block;height:100%;width:var(--w);animation:lbBarFill 1s cubic-bezier(.2,.7,.2,1);}
    .cbarlab{position:absolute;right:6px;top:0;line-height:22px;font-family:'JetBrains Mono',monospace;
      font-weight:800;font-size:.72rem;color:#111827;}
    .cnum{font-family:'JetBrains Mono',monospace;font-weight:700;color:#111827;text-align:right;}
    .cidx{font-size:1.02rem;}
    .cband{font-family:'JetBrains Mono',monospace;font-size:.62rem;font-weight:800;border:2px solid;
      padding:.2rem .3rem;text-align:center;white-space:nowrap;}
    @keyframes lbRowIn{to{opacity:1;transform:none;}}
    @keyframes lbBarFill{from{width:0;}}
    </style>"""
    + f'<div class="ctable">{head_html}{"".join(rows_html)}</div>',
    unsafe_allow_html=True,
)

table = ranking[[
    "city_name", "days", "avg_temp", "comfortable_days", "rainy_days",
    "windy_days", "hot_days", "comfort_score", "avg_european_aqi", "overall_comfort_index",
]].rename(columns={
    "city_name": "City", "days": "Days", "avg_temp": "Avg °C",
    "comfortable_days": "Comfortable", "rainy_days": "Rainy", "windy_days": "Windy",
    "hot_days": "Hot", "comfort_score": "Comfort score",
    "avg_european_aqi": "Avg AQI", "overall_comfort_index": "Overall index",
})
with st.expander("Full numeric table (sortable)"):
    st.dataframe(
        table.style.format({"Avg °C": "{:.1f}", "Comfort score": "{:.1f}",
                            "Avg AQI": "{:.1f}", "Overall index": "{:.1f}"}),
        width="stretch", hide_index=True,
    )

with st.expander("METRIC DEFINITIONS"):
    st.markdown(
        """
        - **Comfortable day** — mean temp 18–26 °C and not rainy, windy, hot or freezing.
        - **Rainy** `rain_sum > 1 mm` · **Windy** `wind > 40 km/h` · **Hot** `max > 35 °C`.
        - **Comfort score** = `100 × comfortable_days / total_days`.
        - **Overall comfort index** = `comfort_score − 0.5 × avg_European_AQI`.
        - **European AQI** — lower is better. Radar axes are normalised 0–100 across the selection.
        """
    )

st.markdown(
    f"""<div class="footer footnote">
    CITY COMFORT INDEX · SOURCE: OPEN-METEO APIS → DBT (STAGING → INTERMEDIATE → MARTS) ON DUCKDB.
    THIS DASHBOARD READS ONLY FROM THE <b style="color:{TERRACOTTA}">MART</b> MODELS, NEVER THE RAW FILES.
    </div>""",
    unsafe_allow_html=True,
)
