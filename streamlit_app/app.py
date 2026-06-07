"""City Comfort Index — Open-Meteo weather analytics dashboard.

Brutalist design: thick ink borders, hard offset shadows, zero radius,
Darker Grotesque + JetBrains Mono, terracotta/ochre accents.

Reads from the dbt mart models in DuckDB (not the raw API files):
    - mart_city_weather_summary  (one row per city)
    - fct_city_weather_day       (one row per city per day)
    - fct_air_quality_city_day   (one row per city per day)

Run from the project root:
    streamlit run streamlit_app/app.py
"""

from __future__ import annotations

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

# Brutalism palette (sampled from typeui.sh/design-skills/brutalism)
INK = "#111827"
TERRACOTTA = "#DD614C"
OCHRE = "#DAA144"
GREEN = "#16A34A"
COBALT = "#2563EB"
DANGER = "#DC2626"

CITY_COLORS = [TERRACOTTA, OCHRE, INK, GREEN, COBALT]
COMFORT_SCALE = [DANGER, TERRACOTTA, OCHRE, GREEN]          # low -> high (good)
AQI_SCALE = [GREEN, OCHRE, TERRACOTTA, DANGER]              # low (good) -> high (bad)

st.set_page_config(
    page_title="City Comfort Index",
    page_icon="◧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------- #
# Brutalist styling
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Darker+Grotesque:wght@500;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');

      html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace; }
      h1, h2, h3, h4 {
        font-family: 'Darker Grotesque', sans-serif !important;
        font-weight: 900 !important; letter-spacing: -0.01em;
        text-transform: uppercase; color: #111827;
      }
      .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1320px; }

      /* Hero */
      .hero {
        background: #DD614C; color: #FFFFFF; padding: 1.4rem 1.8rem;
        border: 4px solid #111827; box-shadow: 10px 10px 0 #111827;
        margin-bottom: 2rem;
      }
      .hero h1 {
        margin: 0; font-size: 3rem; line-height: .95; color: #FFFFFF !important;
      }
      .hero p {
        margin: .5rem 0 0; font-family: 'JetBrains Mono', monospace;
        font-size: .92rem; font-weight: 600; max-width: 760px;
      }

      /* Section headers get a thick underline */
      h2, h3 { border-bottom: 4px solid #111827; padding-bottom: .15rem; }

      /* Metric cards */
      div[data-testid="stMetric"] {
        background: #FFFFFF; border: 3px solid #111827; border-radius: 0;
        padding: .9rem 1rem; box-shadow: 6px 6px 0 #111827;
      }
      div[data-testid="stMetricLabel"] p {
        font-family: 'JetBrains Mono', monospace; font-weight: 700;
        text-transform: uppercase; font-size: .72rem; letter-spacing: .04em;
        color: #111827;
      }
      div[data-testid="stMetricValue"] {
        font-family: 'Darker Grotesque', sans-serif; font-weight: 900;
      }

      /* Frame every chart */
      div[data-testid="stPlotlyChart"] {
        border: 3px solid #111827; border-radius: 0; background: #FFFFFF;
        padding: .5rem; box-shadow: 6px 6px 0 #111827;
      }

      /* Dataframe */
      div[data-testid="stDataFrame"] {
        border: 3px solid #111827; border-radius: 0; box-shadow: 6px 6px 0 #111827;
      }

      /* Sidebar */
      section[data-testid="stSidebar"] {
        background: #F5F4F0; border-right: 4px solid #111827;
      }
      .footnote {
        font-family: 'JetBrains Mono', monospace; color: #374151;
        font-size: .78rem; line-height: 1.55;
      }
      /* Kill rounded corners + easing globally */
      * { border-radius: 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def brutalize(fig: go.Figure, height: int = 360, bars: bool = False) -> go.Figure:
    """Apply the brutalist look to a plotly figure."""
    fig.update_layout(
        template="simple_white",
        font=dict(family="JetBrains Mono, monospace", size=12, color=INK),
        height=height,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=10, r=16, t=10, b=10),
        legend=dict(
            font=dict(family="JetBrains Mono, monospace", size=11),
            bordercolor=INK, borderwidth=2,
        ),
    )
    fig.update_xaxes(showline=True, linewidth=2, linecolor=INK,
                     gridcolor="#E5E5E5", zeroline=False, ticks="outside")
    fig.update_yaxes(showline=True, linewidth=2, linecolor=INK,
                     gridcolor="#E5E5E5", zeroline=False)
    if bars:
        fig.update_traces(marker_line_color=INK, marker_line_width=1.5)
    return fig


# --------------------------------------------------------------------------- #
# Data access (reads from marts)
# --------------------------------------------------------------------------- #
@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        st.error(
            f"DuckDB database not found at `{DB_PATH}`.\n\n"
            "Build it first:\n"
            "1. `python scripts/load_to_duckdb.py`\n"
            "2. `dbt build`"
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
        select
            city_name, weather_date, temperature_2m_mean, temperature_2m_max,
            temperature_2m_min, precipitation_sum, wind_speed_10m_max,
            is_comfortable, is_rainy, is_windy, is_hot, is_freezing
        from main.fct_city_weather_day
        """
    ).df()


@st.cache_data(ttl=600)
def load_daily_aqi() -> pd.DataFrame:
    return get_connection().sql(
        """
        select city_name, air_quality_date, avg_european_aqi, avg_pm2_5
        from main.fct_air_quality_city_day
        """
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
# Header
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <div class="hero">
      <h1>City Comfort Index</h1>
      <p>HOW PLEASANT IS THE WEATHER ACROSS SPAIN'S LARGEST CITIES? A DAILY COMFORT,
      CLIMATE AND AIR-QUALITY VIEW BUILT ON OPEN-METEO DATA.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

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
    "Date range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="DD MMM",
)
start_date, end_date = (pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div class="footnote">
    <b>MAIN MODEL GRAIN</b><br/>
    <code>mart_city_weather_summary</code>: one row per city.<br/>
    <code>fct_city_weather_day</code> / <code>fct_air_quality_city_day</code>:
    one row per city per day.<br/><br/>
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
mask_w = (
    weather["city_name"].isin(selected_cities)
    & weather["weather_date"].between(start_date, end_date)
)
mask_a = (
    aqi["city_name"].isin(selected_cities)
    & aqi["air_quality_date"].between(start_date, end_date)
)
w = weather[mask_w].copy()
a = aqi[mask_a].copy()
s = summary[summary["city_name"].isin(selected_cities)].copy()

if w.empty:
    st.warning("No data in the selected range. Widen the date filter.")
    st.stop()

# Recompute the comfort ranking over the filtered window so filters matter.
ranking = (
    w.groupby("city_name")
    .agg(
        days=("weather_date", "count"),
        comfortable_days=("is_comfortable", "sum"),
        rainy_days=("is_rainy", "sum"),
        windy_days=("is_windy", "sum"),
        hot_days=("is_hot", "sum"),
        freezing_days=("is_freezing", "sum"),
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

# --------------------------------------------------------------------------- #
# KPI row
# --------------------------------------------------------------------------- #
best_city = ranking.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Cities in view", len(selected_cities))
c2.metric("Avg temperature", f"{w['temperature_2m_mean'].mean():.1f} °C")
c3.metric(
    "Comfortable days",
    f"{int(ranking['comfortable_days'].sum())}",
    help="Mean temp 18–26 °C and not rainy, windy, hot or freezing.",
)
c4.metric(
    "Most comfortable",
    best_city["city_name"],
    f"index {best_city['overall_comfort_index']:.1f}",
)

st.markdown("")

# --------------------------------------------------------------------------- #
# Row 1: comfort ranking + map
# --------------------------------------------------------------------------- #
left, right = st.columns([1.1, 1])

with left:
    st.subheader("Comfort ranking")
    fig = px.bar(
        ranking,
        x="overall_comfort_index",
        y="city_name",
        orientation="h",
        color="overall_comfort_index",
        color_continuous_scale=COMFORT_SCALE,
        text="overall_comfort_index",
        labels={"overall_comfort_index": "Overall comfort index", "city_name": ""},
    )
    fig.update_traces(textposition="outside", cliponaxis=False,
                      textfont=dict(family="JetBrains Mono", size=12, color=INK))
    fig.update_layout(coloraxis_showscale=False,
                      yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(brutalize(fig, bars=True), width="stretch")

with right:
    st.subheader("Where they are")
    map_df = s.copy()
    map_df["size"] = map_df["population"].clip(lower=1).pow(0.5)
    fig_map = px.scatter_mapbox(
        map_df,
        lat="latitude",
        lon="longitude",
        color="overall_comfort_index",
        size="size",
        hover_name="city_name",
        hover_data={"latitude": False, "longitude": False, "size": False,
                    "overall_comfort_index": True, "avg_temperature_c": True},
        color_continuous_scale=COMFORT_SCALE,
        size_max=30,
        zoom=4.4,
    )
    fig_map.update_traces(marker=dict(opacity=0.95))
    fig_map.update_layout(
        mapbox_style="carto-positron",
        height=360,
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(title="COMFORT", outlinecolor=INK, outlinewidth=2),
        font=dict(family="JetBrains Mono, monospace", color=INK),
    )
    st.plotly_chart(fig_map, width="stretch")
    st.caption("Map metrics reflect the full observation window per city.")

# --------------------------------------------------------------------------- #
# Row 2: temperature trend
# --------------------------------------------------------------------------- #
st.subheader("Daily mean temperature")
fig_trend = px.line(
    w.sort_values("weather_date"),
    x="weather_date",
    y="temperature_2m_mean",
    color="city_name",
    color_discrete_sequence=CITY_COLORS,
    labels={"weather_date": "", "temperature_2m_mean": "Mean temp (°C)",
            "city_name": "City"},
)
fig_trend.update_traces(line=dict(width=3))
fig_trend.update_layout(
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
st.plotly_chart(brutalize(fig_trend, height=380), width="stretch")

# --------------------------------------------------------------------------- #
# Row 3: condition breakdown + air quality
# --------------------------------------------------------------------------- #
b_left, b_right = st.columns(2)

with b_left:
    st.subheader("Day types by city")
    melted = ranking.melt(
        id_vars="city_name",
        value_vars=["comfortable_days", "rainy_days", "windy_days",
                    "hot_days", "freezing_days"],
        var_name="condition",
        value_name="day_count",
    )
    label_map = {
        "comfortable_days": "Comfortable", "rainy_days": "Rainy",
        "windy_days": "Windy", "hot_days": "Hot", "freezing_days": "Freezing",
    }
    melted["condition"] = melted["condition"].map(label_map)
    fig_stack = px.bar(
        melted, x="city_name", y="day_count", color="condition",
        color_discrete_map={
            "Comfortable": GREEN, "Rainy": COBALT, "Windy": "#94A3B8",
            "Hot": TERRACOTTA, "Freezing": "#22D3EE",
        },
        labels={"city_name": "", "day_count": "Days", "condition": ""},
    )
    fig_stack.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(brutalize(fig_stack, bars=True), width="stretch")

with b_right:
    st.subheader("Air quality")
    if aqi_by_city.empty:
        st.info("No air-quality data in range.")
    else:
        aqi_sorted = aqi_by_city.sort_values("avg_european_aqi")
        fig_aqi = px.bar(
            aqi_sorted, x="avg_european_aqi", y="city_name", orientation="h",
            color="avg_european_aqi", color_continuous_scale=AQI_SCALE,
            text=aqi_sorted["avg_european_aqi"].round(1),
            labels={"avg_european_aqi": "Avg European AQI", "city_name": ""},
        )
        fig_aqi.update_traces(textposition="outside", cliponaxis=False,
                              textfont=dict(family="JetBrains Mono", color=INK))
        fig_aqi.update_layout(coloraxis_showscale=False)
        st.plotly_chart(brutalize(fig_aqi, bars=True), width="stretch")
        st.caption("Lower European AQI = better air quality.")

# --------------------------------------------------------------------------- #
# Row 4: temperature distribution
# --------------------------------------------------------------------------- #
st.subheader("Temperature spread by city")
fig_box = px.box(
    w, x="city_name", y="temperature_2m_mean", color="city_name",
    color_discrete_sequence=CITY_COLORS, points="outliers",
    labels={"city_name": "", "temperature_2m_mean": "Daily mean temp (°C)"},
)
fig_box.update_layout(showlegend=False)
st.plotly_chart(brutalize(fig_box, bars=True), width="stretch")

# --------------------------------------------------------------------------- #
# Ranking table + metric definitions
# --------------------------------------------------------------------------- #
st.subheader("City comfort table")
table = ranking[[
    "city_name", "days", "avg_temp", "comfortable_days", "rainy_days",
    "windy_days", "hot_days", "comfort_score", "avg_european_aqi",
    "overall_comfort_index",
]].rename(columns={
    "city_name": "City", "days": "Days", "avg_temp": "Avg °C",
    "comfortable_days": "Comfortable", "rainy_days": "Rainy",
    "windy_days": "Windy", "hot_days": "Hot", "comfort_score": "Comfort score",
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
        - **Comfortable day** — daily mean temperature between **18 °C and 26 °C**
          and the day is **not** rainy, windy, hot or freezing.
        - **Rainy** — `rain_sum > 1.0 mm`. &nbsp; **Windy** — `wind_speed_10m_max > 40 km/h`.
        - **Hot** — `temperature_2m_max > 35 °C`. &nbsp; **Freezing** — `temperature_2m_min < 0 °C`.
        - **Comfort score** — `100 × comfortable_days / total_days` (0–100).
        - **Overall comfort index** — `comfort_score − 0.5 × avg_European_AQI`;
          rewards pleasant weather and penalises poor air quality.
        - **European AQI** — Open-Meteo's European Air Quality Index (lower is better).
        """
    )

st.markdown(
    """
    <p class="footnote">
    SOURCE: OPEN-METEO APIS → DBT (STAGING → INTERMEDIATE → MARTS) ON DUCKDB.
    THIS DASHBOARD READS ONLY FROM THE <b>MART</b> MODELS, NEVER THE RAW FILES.
    </p>
    """,
    unsafe_allow_html=True,
)
