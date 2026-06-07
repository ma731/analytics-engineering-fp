"""City Comfort Index — Open-Meteo weather analytics dashboard.

Premium dark neo-brutalist design: gauge KPIs, an animated live scatter,
a gradient area trend, a radar comparison, and a dark glowing map.

Reads from the dbt mart models in DuckDB (not the raw API files):
    - mart_city_weather_summary  (one row per city)
    - fct_city_weather_day       (one row per city per day)
    - fct_air_quality_city_day   (one row per city per day)

Run from the project root:
    streamlit run streamlit_app/app.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

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

# Dark neo-brutalist palette
BG = "#0B0B0F"
PANEL = "#16161D"
BORDER = "#2E2E3A"
TEXT = "#F4F4F5"
MUTED = "#A1A1AA"
TERRACOTTA = "#FF6B4A"
OCHRE = "#E0A436"
GREEN = "#34D399"
CYAN = "#22D3EE"
ROSE = "#F43F5E"
AMBER = "#FBBF24"

CITY_COLORS = [TERRACOTTA, CYAN, OCHRE, GREEN, "#A78BFA"]
COMFORT_SCALE = [ROSE, TERRACOTTA, AMBER, GREEN]   # low -> high (good)
AQI_SCALE = [GREEN, AMBER, TERRACOTTA, ROSE]       # low (good) -> high (bad)
HEAT_SCALE = ["#1E3A8A", CYAN, GREEN, AMBER, TERRACOTTA]  # cold -> hot

st.set_page_config(
    page_title="City Comfort Index",
    page_icon="◧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Darker+Grotesque:wght@600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap');

      html, body, [class*="css"] {{ font-family: 'JetBrains Mono', monospace; }}
      .stApp {{ background:
          radial-gradient(1200px 500px at 80% -10%, rgba(255,107,74,.10), transparent 60%),
          radial-gradient(900px 500px at 0% 0%, rgba(34,211,238,.08), transparent 55%),
          {BG}; }}
      h1, h2, h3, h4 {{
        font-family: 'Darker Grotesque', sans-serif !important;
        font-weight: 900 !important; letter-spacing: -0.01em;
        text-transform: uppercase; color: {TEXT};
      }}
      .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1340px; }}

      /* Hero */
      .hero {{
        background: linear-gradient(120deg, {TERRACOTTA} 0%, #C2410C 100%);
        color: #fff; padding: 1.3rem 1.7rem; border: 1px solid rgba(255,255,255,.18);
        box-shadow: 0 18px 50px -20px rgba(255,107,74,.7);
        display: flex; align-items: center; justify-content: space-between; gap: 1rem;
      }}
      .hero h1 {{ margin: 0; font-size: 2.7rem; line-height: .9; color: #fff !important; }}
      .hero p {{ margin: .35rem 0 0; font-size: .82rem; font-weight: 500; opacity: .95; max-width: 640px; }}

      /* LIVE badge */
      .live {{
        display: inline-flex; align-items: center; gap: .5rem; white-space: nowrap;
        background: rgba(0,0,0,.28); border: 1px solid rgba(255,255,255,.35);
        padding: .35rem .7rem; font-size: .72rem; font-weight: 700; letter-spacing: .08em;
      }}
      .dot {{ width: 9px; height: 9px; border-radius: 50%; background: #d1fae5;
        box-shadow: 0 0 0 0 rgba(209,250,229,.9); animation: pulse 1.6s infinite; }}
      @keyframes pulse {{
        0% {{ box-shadow: 0 0 0 0 rgba(209,250,229,.8); }}
        70% {{ box-shadow: 0 0 0 9px rgba(209,250,229,0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(209,250,229,0); }}
      }}

      h2, h3 {{ border-bottom: 2px solid {BORDER}; padding-bottom: .2rem; margin-top: .4rem; }}

      div[data-testid="stMetric"] {{
        background: {PANEL}; border: 1px solid {BORDER};
        border-left: 4px solid {TERRACOTTA}; padding: .8rem 1rem;
      }}
      div[data-testid="stMetricValue"] {{ font-family: 'Darker Grotesque', sans-serif; font-weight: 900; }}

      div[data-testid="stPlotlyChart"] {{
        border: 1px solid {BORDER}; background: {PANEL};
        padding: .55rem; box-shadow: 0 10px 30px -18px rgba(0,0,0,.9);
      }}
      div[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; }}
      section[data-testid="stSidebar"] {{ background: #0E0E14; border-right: 1px solid {BORDER}; }}
      .footnote {{ font-family: 'JetBrains Mono', monospace; color: {MUTED}; font-size: .76rem; line-height: 1.55; }}
      * {{ border-radius: 0 !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert a #RRGGBB hex string to an rgba() string with the given alpha."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def style_fig(fig: go.Figure, height: int = 340, bars: bool = False) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        font=dict(family="JetBrains Mono, monospace", size=12, color=TEXT),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=16, t=30, b=10),
        legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
        colorway=CITY_COLORS,
    )
    fig.update_xaxes(showline=True, linewidth=1, linecolor=BORDER,
                     gridcolor="#20202A", zeroline=False)
    fig.update_yaxes(showline=True, linewidth=1, linecolor=BORDER,
                     gridcolor="#20202A", zeroline=False)
    if bars:
        fig.update_traces(marker_line_color="rgba(255,255,255,.25)", marker_line_width=1)
    return fig


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


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
summary = load_summary()
weather = load_daily_weather()
aqi = load_daily_aqi()
weather["weather_date"] = pd.to_datetime(weather["weather_date"])
aqi["air_quality_date"] = pd.to_datetime(aqi["air_quality_date"])


# --------------------------------------------------------------------------- #
# Sidebar filters
# --------------------------------------------------------------------------- #
st.sidebar.header("Filters")
all_cities = sorted(summary["city_name"].tolist())
selected_cities = st.sidebar.multiselect("Cities", options=all_cities, default=all_cities)
if not selected_cities:
    st.warning("Select at least one city to see the dashboard.")
    st.stop()

min_date = weather["weather_date"].min().date()
max_date = weather["weather_date"].max().date()
date_range = st.sidebar.slider(
    "Date range", min_value=min_date, max_value=max_date,
    value=(min_date, max_date), format="DD MMM",
)
start_date, end_date = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div class="footnote">
    <b>MAIN MODEL GRAIN</b><br/>
    <code>mart_city_weather_summary</code>: one row per city.<br/>
    <code>fct_*_day</code>: one row per city per day.<br/><br/>
    <b>REPRODUCE</b><br/>
    1. <code>python scripts/extract_open_meteo.py</code><br/>
    2. <code>python scripts/load_to_duckdb.py</code><br/>
    3. <code>dbt build</code><br/>
    4. <code>streamlit run streamlit_app/app.py</code>
    </div>
    """,
    unsafe_allow_html=True,
)

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

# Comfort ranking recomputed over the filtered window
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

# --------------------------------------------------------------------------- #
# Hero + live status (the live status fragment refreshes every 2s)
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <div class="hero">
      <div>
        <h1>City Comfort Index</h1>
        <p>HOW PLEASANT IS THE WEATHER ACROSS SPAIN'S LARGEST CITIES? A LIVE COMFORT,
        CLIMATE AND AIR-QUALITY VIEW BUILT ON OPEN-METEO DATA.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.fragment(run_every="2s")
def live_status() -> None:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    span = f"{start_date:%d %b} – {end_date:%d %b}"
    st.markdown(
        f"""
        <div style="display:flex;gap:.6rem;flex-wrap:wrap;margin:.7rem 0 .2rem">
          <span class="live"><span class="dot"></span>LIVE · {now}</span>
          <span class="live" style="border-color:{BORDER};color:{MUTED}">
            MONITORING {len(selected_cities)} CITIES</span>
          <span class="live" style="border-color:{BORDER};color:{MUTED}">WINDOW {span}</span>
          <span class="live" style="border-color:{BORDER};color:{MUTED}">
            {len(w):,} CITY-DAYS</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


live_status()


# --------------------------------------------------------------------------- #
# KPI gauges
# --------------------------------------------------------------------------- #
def gauge(value, title, vmin, vmax, steps, bar_color, suffix=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(float(value), 1),
        number={"suffix": suffix, "font": {"family": "JetBrains Mono", "size": 30}},
        title={"text": title, "font": {"family": "Darker Grotesque", "size": 20}},
        gauge={
            "axis": {"range": [vmin, vmax], "tickcolor": MUTED},
            "bar": {"color": bar_color, "thickness": 0.28},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": steps,
        },
    ))
    fig.update_layout(
        height=210, margin=dict(l=18, r=18, t=42, b=6),
        paper_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, family="JetBrains Mono"),
    )
    return fig


g1, g2, g3 = st.columns(3)
with g1:
    st.plotly_chart(gauge(
        ranking["overall_comfort_index"].mean(), "OVERALL COMFORT", -20, 40,
        [{"range": [-20, 0], "color": "#3b1d22"}, {"range": [0, 20], "color": "#3a3320"},
         {"range": [20, 40], "color": "#163a2c"}], TERRACOTTA), width="stretch")
with g2:
    st.plotly_chart(gauge(
        w["temperature_2m_mean"].mean(), "AVG TEMPERATURE", 0, 40,
        [{"range": [0, 18], "color": "#16304a"}, {"range": [18, 26], "color": "#163a2c"},
         {"range": [26, 40], "color": "#3b1d22"}], CYAN, " °C"), width="stretch")
with g3:
    aqi_mean = a["avg_european_aqi"].mean() if not a.empty else 0
    st.plotly_chart(gauge(
        aqi_mean, "AIR QUALITY (AQI)", 0, 100,
        [{"range": [0, 25], "color": "#163a2c"}, {"range": [25, 50], "color": "#3a3320"},
         {"range": [50, 100], "color": "#3b1d22"}], GREEN), width="stretch")


# --------------------------------------------------------------------------- #
# Animated "live" scatter: temperature vs air quality over time
# --------------------------------------------------------------------------- #
st.subheader("Temperature × air quality over time ▶")
anim = w.merge(
    a.rename(columns={"air_quality_date": "weather_date"}),
    on=["city_name", "weather_date"], how="inner",
)
if not anim.empty:
    anim = anim.sort_values("weather_date")
    anim["day"] = anim["weather_date"].dt.strftime("%d %b")
    anim["precip_size"] = anim["precipitation_sum"].clip(lower=0) + 2
    fig_anim = px.scatter(
        anim, x="temperature_2m_mean", y="avg_european_aqi",
        animation_frame="day", animation_group="city_name",
        color="city_name", size="precip_size", size_max=34,
        color_discrete_sequence=CITY_COLORS, text="city_name",
        range_x=[anim["temperature_2m_mean"].min() - 2, anim["temperature_2m_mean"].max() + 2],
        range_y=[max(0, anim["avg_european_aqi"].min() - 8), anim["avg_european_aqi"].max() + 8],
        labels={"temperature_2m_mean": "Mean temp (°C)", "avg_european_aqi": "European AQI",
                "city_name": "City"},
    )
    fig_anim.update_traces(textposition="top center",
                           textfont=dict(size=10, color=MUTED))
    fig_anim.update_layout(transition={"duration": 300})
    st.plotly_chart(style_fig(fig_anim, height=440), width="stretch")
    st.caption("Press ▶ to watch each city drift through the period. Bubble size = daily precipitation.")
else:
    st.info("No overlapping weather + air-quality days in range.")


# --------------------------------------------------------------------------- #
# Ranking + map
# --------------------------------------------------------------------------- #
left, right = st.columns([1.05, 1])
with left:
    st.subheader("Comfort ranking")
    fig_rank = px.bar(
        ranking, x="overall_comfort_index", y="city_name", orientation="h",
        color="overall_comfort_index", color_continuous_scale=COMFORT_SCALE,
        text="overall_comfort_index",
        labels={"overall_comfort_index": "Overall comfort index", "city_name": ""},
    )
    fig_rank.update_traces(textposition="outside", cliponaxis=False,
                           textfont=dict(color=TEXT))
    fig_rank.update_layout(coloraxis_showscale=False,
                           yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(style_fig(fig_rank, bars=True), width="stretch")

with right:
    st.subheader("Where they are")
    map_df = s.copy()
    map_df["size"] = map_df["population"].clip(lower=1).pow(0.5)
    fig_map = px.scatter_mapbox(
        map_df, lat="latitude", lon="longitude", color="overall_comfort_index",
        size="size", hover_name="city_name", size_max=30, zoom=4.3,
        color_continuous_scale=COMFORT_SCALE,
        hover_data={"latitude": False, "longitude": False, "size": False,
                    "overall_comfort_index": True, "avg_temperature_c": True},
    )
    fig_map.update_layout(
        mapbox_style="carto-darkmatter", height=340,
        margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family="JetBrains Mono"),
        coloraxis_colorbar=dict(title="COMFORT"),
    )
    st.plotly_chart(fig_map, width="stretch")


# --------------------------------------------------------------------------- #
# Gradient area trend + radar
# --------------------------------------------------------------------------- #
c_left, c_right = st.columns([1.15, 1])
with c_left:
    st.subheader("Daily mean temperature")
    fig_area = go.Figure()
    for i, city in enumerate(sorted(w["city_name"].unique())):
        d = w[w["city_name"] == city].sort_values("weather_date")
        color = CITY_COLORS[i % len(CITY_COLORS)]
        fig_area.add_trace(go.Scatter(
            x=d["weather_date"], y=d["temperature_2m_mean"], name=city,
            mode="lines", line=dict(color=color, width=2.5, shape="spline"),
            fill="tozeroy", fillcolor=_rgba(color, 0.12),
        ))
    fig_area.update_layout(legend=dict(orientation="h", y=1.04, x=0))
    st.plotly_chart(style_fig(fig_area, height=360), width="stretch")

with c_right:
    st.subheader("City profiles")
    metrics = ["Warmth", "Comfort", "Clean air", "Calm", "Dry"]
    radar = go.Figure()
    aqi_max = max(ranking["avg_european_aqi"].fillna(0).max(), 1)
    for i, (_, r) in enumerate(ranking.iterrows()):
        warmth = min(100, max(0, (r["avg_temp"] / 30) * 100))
        comfort = r["comfort_score"]
        clean = 100 - min(100, (r["avg_european_aqi"] if pd.notna(r["avg_european_aqi"]) else 0)
                          / aqi_max * 100)
        calm = 100 - (r["windy_days"] / r["days"] * 100)
        dry = 100 - (r["rainy_days"] / r["days"] * 100)
        color = CITY_COLORS[i % len(CITY_COLORS)]
        radar.add_trace(go.Scatterpolar(
            r=[warmth, comfort, clean, calm, dry], theta=metrics, fill="toself",
            name=r["city_name"], line=dict(color=color, width=2),
            fillcolor=_rgba(color, 0.10),
        ))
    radar.update_layout(
        template="plotly_dark", height=360, paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono", size=11, color=TEXT),
        margin=dict(l=30, r=30, t=40, b=20),
        polar=dict(bgcolor="rgba(0,0,0,0)",
                   radialaxis=dict(range=[0, 100], gridcolor="#20202A", showticklabels=False),
                   angularaxis=dict(gridcolor="#20202A")),
        legend=dict(orientation="h", y=1.12, x=0),
    )
    st.plotly_chart(radar, width="stretch")


# --------------------------------------------------------------------------- #
# Heatmap + day types
# --------------------------------------------------------------------------- #
h_left, h_right = st.columns([1.2, 1])
with h_left:
    st.subheader("Daily temperature heatmap")
    pivot = w.pivot_table(index="city_name", columns="weather_date",
                          values="temperature_2m_mean", aggfunc="mean")
    fig_heat = px.imshow(
        pivot, color_continuous_scale=HEAT_SCALE, aspect="auto",
        labels={"x": "", "y": "", "color": "°C"},
    )
    fig_heat.update_xaxes(showticklabels=True, tickformat="%d %b", nticks=10)
    st.plotly_chart(style_fig(fig_heat, height=300), width="stretch")

with h_right:
    st.subheader("Day types")
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
        color_discrete_map={"Comfortable": GREEN, "Rainy": CYAN,
                            "Windy": MUTED, "Hot": TERRACOTTA},
        labels={"city_name": "", "day_count": "Days", "condition": ""},
    )
    fig_stack.update_layout(legend=dict(orientation="h", y=1.06, x=0))
    st.plotly_chart(style_fig(fig_stack, height=300, bars=True), width="stretch")


# --------------------------------------------------------------------------- #
# Table + definitions
# --------------------------------------------------------------------------- #
st.subheader("City comfort table")
table = ranking[[
    "city_name", "days", "avg_temp", "comfortable_days", "rainy_days",
    "windy_days", "hot_days", "comfort_score", "avg_european_aqi",
    "overall_comfort_index",
]].rename(columns={
    "city_name": "City", "days": "Days", "avg_temp": "Avg °C",
    "comfortable_days": "Comfortable", "rainy_days": "Rainy", "windy_days": "Windy",
    "hot_days": "Hot", "comfort_score": "Comfort score",
    "avg_european_aqi": "Avg AQI", "overall_comfort_index": "Overall index",
})
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
    f"""<p class="footnote">SOURCE: OPEN-METEO APIS → DBT (STAGING → INTERMEDIATE → MARTS)
    ON DUCKDB. READS ONLY FROM THE <b style="color:{TERRACOTTA}">MART</b> MODELS.</p>""",
    unsafe_allow_html=True,
)
