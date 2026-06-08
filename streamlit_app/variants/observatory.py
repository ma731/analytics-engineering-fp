"""Spain Weather Theatre - Streamlit dashboard over dbt mart models.

The dashboard keeps the analytical contract from the project: all measured values
come from the dbt mart tables in DuckDB. The Spanish city atlas is a visual
interpolation from those measured city signals so the presentation can show a
national sweep without inventing a second data source.

Run from the project root:
    python -m streamlit run streamlit_app/app.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "weather_analytics.duckdb"

BG = "#070A0D"
BG_2 = "#0C1116"
PANEL = "#121922"
PANEL_2 = "#17212B"
LINE = "#2D3A42"
TEXT = "#FFF8EA"
MUTED = "#AEB9BC"
SUN = "#FFD34D"
HEAT = "#FF5A36"
RAIN = "#35B7FF"
CLEAN = "#78F2A0"
FOG = "#D6E2E4"

CITY_COLORS = [HEAT, RAIN, SUN, CLEAN, "#FF9B54", "#CDE7E2"]
TEMP_SCALE = ["#143D6B", RAIN, CLEAN, SUN, "#FF9B54", HEAT]
COMFORT_SCALE = ["#481C24", HEAT, SUN, CLEAN]
AQI_SCALE = [CLEAN, SUN, "#FF9B54", HEAT]
RAIN_SCALE = ["#101820", "#15567A", RAIN, "#B8EDFF"]

CITY_PHOTOS = {
    "Madrid": "https://commons.wikimedia.org/wiki/Special:FilePath/Madrid%20Gran%20V%C3%ADa.jpg?width=1800",
    "Barcelona": "https://commons.wikimedia.org/wiki/Special:FilePath/Sagrada%20Familia%2C%20Barcelona%20%28P1170692%29.jpg?width=1800",
    "Valencia": "https://commons.wikimedia.org/wiki/Special:FilePath/The%20City%20of%20Arts%20and%20Sciences%20complex%20by%20Santiago%20Calatrava%20and%20F%C3%A9lix%20Candela.%20Valencia%2C%20Spain%2C%20Southwestern%20Europe.%20September%2028%2C%202014.jpg?width=1800",
    "Sevilla": "https://commons.wikimedia.org/wiki/Special:FilePath/Plaza%20de%20Espa%C3%B1a%20%28Sevilla%29%20-%2001.jpg?width=1800",
    "Bilbao": "https://commons.wikimedia.org/wiki/Special:FilePath/Bilbao%20Guggenheim%201190433.jpg?width=1800",
}

DEFAULT_CITY_PHOTO = CITY_PHOTOS["Madrid"]
DEFAULT_DEMO_CITIES = ("Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao")

st.set_page_config(
    page_title="Spain Climate Observatory",
    page_icon="ES",
    layout="wide",
    initial_sidebar_state="expanded",
)


@dataclass(frozen=True)
class AtlasCity:
    city: str
    lat: float
    lon: float
    region: str


SPANISH_CITY_ATLAS: tuple[AtlasCity, ...] = (
    AtlasCity("A Coruna", 43.3623, -8.4115, "Galicia"),
    AtlasCity("Albacete", 38.9943, -1.8585, "Castilla-La Mancha"),
    AtlasCity("Alicante", 38.3452, -0.4810, "Comunitat Valenciana"),
    AtlasCity("Almeria", 36.8340, -2.4637, "Andalucia"),
    AtlasCity("Avila", 40.6565, -4.6818, "Castilla y Leon"),
    AtlasCity("Badajoz", 38.8794, -6.9707, "Extremadura"),
    AtlasCity("Barcelona", 41.3874, 2.1686, "Catalunya"),
    AtlasCity("Bilbao", 43.2630, -2.9350, "Euskadi"),
    AtlasCity("Burgos", 42.3439, -3.6969, "Castilla y Leon"),
    AtlasCity("Caceres", 39.4753, -6.3724, "Extremadura"),
    AtlasCity("Cadiz", 36.5271, -6.2886, "Andalucia"),
    AtlasCity("Castellon de la Plana", 39.9864, -0.0513, "Comunitat Valenciana"),
    AtlasCity("Ceuta", 35.8894, -5.3198, "Ceuta"),
    AtlasCity("Ciudad Real", 38.9848, -3.9274, "Castilla-La Mancha"),
    AtlasCity("Cordoba", 37.8882, -4.7794, "Andalucia"),
    AtlasCity("Cuenca", 40.0704, -2.1374, "Castilla-La Mancha"),
    AtlasCity("Girona", 41.9794, 2.8214, "Catalunya"),
    AtlasCity("Granada", 37.1773, -3.5986, "Andalucia"),
    AtlasCity("Guadalajara", 40.6333, -3.1667, "Castilla-La Mancha"),
    AtlasCity("Huelva", 37.2614, -6.9447, "Andalucia"),
    AtlasCity("Huesca", 42.1401, -0.4089, "Aragon"),
    AtlasCity("Jaen", 37.7796, -3.7849, "Andalucia"),
    AtlasCity("Leon", 42.5987, -5.5671, "Castilla y Leon"),
    AtlasCity("Lleida", 41.6176, 0.6200, "Catalunya"),
    AtlasCity("Logrono", 42.4627, -2.4449, "La Rioja"),
    AtlasCity("Lugo", 43.0121, -7.5559, "Galicia"),
    AtlasCity("Madrid", 40.4168, -3.7038, "Madrid"),
    AtlasCity("Malaga", 36.7213, -4.4214, "Andalucia"),
    AtlasCity("Melilla", 35.2923, -2.9381, "Melilla"),
    AtlasCity("Murcia", 37.9922, -1.1307, "Region de Murcia"),
    AtlasCity("Ourense", 42.3358, -7.8639, "Galicia"),
    AtlasCity("Oviedo", 43.3619, -5.8494, "Asturias"),
    AtlasCity("Palencia", 42.0097, -4.5288, "Castilla y Leon"),
    AtlasCity("Palma", 39.5696, 2.6502, "Illes Balears"),
    AtlasCity("Pamplona", 42.8125, -1.6458, "Navarra"),
    AtlasCity("Pontevedra", 42.4310, -8.6444, "Galicia"),
    AtlasCity("Salamanca", 40.9701, -5.6635, "Castilla y Leon"),
    AtlasCity("San Sebastian", 43.3183, -1.9812, "Euskadi"),
    AtlasCity("Santa Cruz de Tenerife", 28.4636, -16.2518, "Canarias"),
    AtlasCity("Santander", 43.4623, -3.8099, "Cantabria"),
    AtlasCity("Segovia", 40.9429, -4.1088, "Castilla y Leon"),
    AtlasCity("Sevilla", 37.3891, -5.9845, "Andalucia"),
    AtlasCity("Soria", 41.7666, -2.4790, "Castilla y Leon"),
    AtlasCity("Tarragona", 41.1189, 1.2445, "Catalunya"),
    AtlasCity("Teruel", 40.3456, -1.1065, "Aragon"),
    AtlasCity("Toledo", 39.8628, -4.0273, "Castilla-La Mancha"),
    AtlasCity("Valencia", 39.4699, -0.3763, "Comunitat Valenciana"),
    AtlasCity("Valladolid", 41.6523, -4.7245, "Castilla y Leon"),
    AtlasCity("Vitoria-Gasteiz", 42.8467, -2.6716, "Euskadi"),
    AtlasCity("Zamora", 41.5035, -5.7468, "Castilla y Leon"),
    AtlasCity("Zaragoza", 41.6488, -0.8891, "Aragon"),
    AtlasCity("Las Palmas de Gran Canaria", 28.1235, -15.4363, "Canarias"),
)


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

          :root {{
            --bg: {BG}; --bg2: {BG_2}; --panel: {PANEL}; --panel2: {PANEL_2};
            --line: {LINE}; --text: {TEXT}; --muted: {MUTED}; --sun: {SUN};
            --heat: {HEAT}; --rain: {RAIN}; --clean: {CLEAN};
          }}

          html, body, [class*="css"], .stApp, button, input, textarea, select {{
            font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif !important;
            color: var(--text);
            text-rendering: optimizeLegibility;
            font-feature-settings: "kern" 1, "liga" 1;
          }}

          .stApp {{
            background:
              linear-gradient(115deg, rgba(255,90,54,.08), transparent 24%),
              linear-gradient(245deg, rgba(53,183,255,.08), transparent 28%),
              radial-gradient(circle at 50% -15%, rgba(255,211,77,.16), transparent 36%),
              var(--bg);
            overflow-x: hidden;
          }}

          .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: .055;
            background-image:
              linear-gradient(rgba(255,255,255,.18) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,.12) 1px, transparent 1px);
            background-size: 84px 84px;
            mask-image: linear-gradient(to bottom, black, transparent 78%);
            animation: gridDrift 18s linear infinite;
            z-index: 0;
          }}

          .stApp::after {{
            content: "";
            position: fixed;
            inset: -18vh -14vw auto -14vw;
            height: 78vh;
            pointer-events: none;
            z-index: 0;
            opacity: .42;
            background:
              radial-gradient(ellipse at 50% 12%, rgba(255,211,77,.24), transparent 22%),
              radial-gradient(ellipse at 75% 30%, rgba(53,183,255,.18), transparent 28%),
              linear-gradient(180deg, transparent 0 34%, rgba(53,183,255,.14) 35% 36%, transparent 37% 48%, rgba(255,90,54,.11) 49% 50%, transparent 51%),
              repeating-linear-gradient(172deg, transparent 0 48px, rgba(255,248,234,.09) 49px 50px, transparent 51px 96px);
            transform: perspective(740px) rotateX(64deg) translateY(12vh);
            transform-origin: center top;
            filter: blur(.3px) saturate(1.12);
            animation: atmosphereWave 12s ease-in-out infinite alternate;
          }}

          @keyframes gridDrift {{
            from {{ background-position: 0 0, 0 0; }}
            to {{ background-position: 84px 84px, 84px 84px; }}
          }}

          @keyframes atmosphereWave {{
            0% {{ transform: perspective(740px) rotateX(64deg) translate3d(-2vw, 10vh, 0); background-position: 0 0, 0 0, 0 0, 0 0; }}
            100% {{ transform: perspective(740px) rotateX(66deg) translate3d(3vw, 15vh, 0); background-position: 60px 0, -40px 0, 120px 0, 180px 0; }}
          }}

          .block-container {{
            max-width: 1180px;
            padding-top: 1rem;
            padding-bottom: 3.5rem;
            position: relative;
            z-index: 2;
          }}

          h1, h2, h3 {{
            font-family: 'Archivo Black', 'Impact', sans-serif !important;
            color: var(--text) !important;
            letter-spacing: 0 !important;
          }}

          h2, h3 {{ margin-top: .8rem; }}
          p {{ line-height: 1.45; }}

          section[data-testid="stSidebar"] {{
            background: #071015;
            border-right: 1px solid rgba(214,226,228,.14);
            z-index: 5;
          }}

          section[data-testid="stSidebar"] label,
          section[data-testid="stSidebar"] p,
          section[data-testid="stSidebar"] span {{ color: var(--text) !important; }}

          div[data-testid="stPlotlyChart"] {{
            background: linear-gradient(180deg, rgba(255,248,234,.04), rgba(255,248,234,.015));
            border: 1px solid rgba(214,226,228,.13);
            border-radius: 8px;
            padding: .45rem;
            box-shadow: 0 18px 52px rgba(0,0,0,.28);
          }}

          div[data-testid="stDataFrame"] {{
            border: 1px solid rgba(214,226,228,.18);
            border-radius: 8px;
            overflow: hidden;
          }}

          .weather-stage {{
            position: relative;
            overflow: hidden;
            isolation: isolate;
            min-height: 342px;
            box-sizing: border-box;
            border: 1px solid rgba(255,248,234,.20);
            border-radius: 8px;
            padding: clamp(1.25rem, 2.8vw, 2.2rem) clamp(1.25rem, 2.8vw, 2.2rem) 4.35rem;
            background:
              radial-gradient(ellipse at 70% 8%, rgba(255,211,77,.20), transparent 28%),
              linear-gradient(140deg, rgba(255,90,54,.18), transparent 34%),
              linear-gradient(18deg, rgba(53,183,255,.16), transparent 44%),
              linear-gradient(180deg, #101A20 0%, #090D10 100%);
            background-size: 140% 140%, 150% 150%, 130% 130%, 100% 100%;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,.04), 0 28px 90px rgba(0,0,0,.38);
            animation: stageSkyShift 14s ease-in-out infinite alternate;
          }}

          .weather-stage::before {{
            content: "";
            position: absolute;
            inset: -20% -10% 20% 30%;
            z-index: 1;
            pointer-events: none;
            background:
              radial-gradient(ellipse at 45% 42%, rgba(255,211,77,.34), transparent 0 18%, rgba(255,90,54,.18) 19% 32%, transparent 54%),
              conic-gradient(from 210deg at 48% 44%, transparent 0 13%, rgba(255,211,77,.24) 14% 16%, transparent 17% 31%, rgba(53,183,255,.18) 32% 34%, transparent 35%);
            mix-blend-mode: screen;
            filter: blur(10px);
            transform: translate3d(0, 0, 0);
            animation: lightSweep 9s ease-in-out infinite alternate;
          }}

          .weather-stage::after {{
            content: "";
            position: absolute;
            inset: auto -10% 0 -10%;
            height: 34%;
            z-index: 1;
            pointer-events: none;
            background:
              repeating-linear-gradient(168deg, transparent 0 36px, rgba(255,211,77,.22) 37px 39px, transparent 40px 70px, rgba(53,183,255,.18) 71px 73px, transparent 74px 110px),
              linear-gradient(180deg, transparent, rgba(0,0,0,.26));
            transform: skewY(-4deg);
            transform-origin: 100% 100%;
            animation: horizonSlide 7.5s ease-in-out infinite alternate;
          }}

          @keyframes stageSkyShift {{
            0% {{ background-position: 0% 0%, 0% 0%, 100% 40%, 0 0; }}
            100% {{ background-position: 40% 12%, 75% 20%, 20% 70%, 0 0; }}
          }}

          @keyframes lightSweep {{
            0% {{ transform: translate3d(-4%, -2%, 0) rotate(-2deg) scale(.96); opacity: .66; }}
            100% {{ transform: translate3d(5%, 4%, 0) rotate(3deg) scale(1.08); opacity: .95; }}
          }}

          @keyframes horizonSlide {{
            0% {{ transform: skewY(-4deg) translateX(-2%); }}
            100% {{ transform: skewY(-6deg) translateX(3%); }}
          }}

          .stage-waves {{
            position: absolute;
            left: -8%;
            right: -8%;
            bottom: 6%;
            height: 54%;
            z-index: 1;
            pointer-events: none;
            transform: perspective(620px) rotateX(62deg) rotateZ(-3deg);
            transform-origin: center bottom;
            filter: drop-shadow(0 0 16px rgba(53,183,255,.18));
          }}

          .stage-wave {{
            position: absolute;
            left: 0;
            right: 0;
            height: 34%;
            border-radius: 999px;
            background:
              repeating-linear-gradient(90deg, transparent 0 42px, rgba(255,248,234,.20) 43px 44px, transparent 45px 86px),
              linear-gradient(90deg, transparent, rgba(53,183,255,.26), rgba(255,211,77,.22), rgba(255,90,54,.20), transparent);
            mask-image: linear-gradient(90deg, transparent, black 12%, black 88%, transparent);
            opacity: .58;
            animation: waveDrift 8s ease-in-out infinite alternate;
          }}

          .stage-wave:nth-child(1) {{ bottom: 0; transform: translateX(-3%) scaleY(.74); animation-duration: 9s; }}
          .stage-wave:nth-child(2) {{ bottom: 22%; transform: translateX(5%) scaleY(.58); animation-duration: 7s; animation-delay: -2s; opacity: .44; }}
          .stage-wave:nth-child(3) {{ bottom: 42%; transform: translateX(-6%) scaleY(.45); animation-duration: 11s; animation-delay: -4s; opacity: .34; }}

          @keyframes waveDrift {{
            0% {{ background-position: 0 0, 0 0; }}
            100% {{ background-position: 180px 0, -120px 0; }}
          }}

          .light-gate {{
            position: absolute;
            left: 54%;
            top: 17%;
            width: min(22vw, 230px);
            height: 38%;
            z-index: 1;
            pointer-events: none;
            opacity: .62;
            background:
              repeating-linear-gradient(90deg, rgba(255,211,77,.0) 0 14px, rgba(255,211,77,.34) 15px 17px, rgba(53,183,255,.22) 18px 20px, transparent 21px 34px),
              linear-gradient(180deg, rgba(255,211,77,.28), rgba(53,183,255,.12), transparent);
            clip-path: polygon(14% 0, 86% 0, 100% 100%, 0 100%);
            filter: blur(.2px) drop-shadow(0 0 22px rgba(255,211,77,.32));
            animation: gatePulse 5.6s ease-in-out infinite alternate;
          }}

          @keyframes gatePulse {{
            0% {{ transform: translateY(-3px) scaleY(.92); opacity: .45; }}
            100% {{ transform: translateY(9px) scaleY(1.08); opacity: .78; }}
          }}

          .hero-copy {{
            position: relative;
            z-index: 2;
            max-width: 830px;
          }}

          .eyebrow {{
            display: inline-flex;
            align-items: center;
            gap: .55rem;
            padding: .38rem .65rem;
            border: 1px solid rgba(255,248,234,.24);
            border-radius: 999px;
            color: var(--text);
            background: rgba(5,7,8,.48);
            font-size: .82rem;
            font-weight: 700;
          }}

          .pulse-dot {{
            width: .55rem;
            height: .55rem;
            border-radius: 50%;
            background: var(--clean);
            box-shadow: 0 0 0 0 rgba(120,242,160,.75);
            animation: pulse 1.65s infinite;
          }}

          @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(120,242,160,.78); }}
            70% {{ box-shadow: 0 0 0 12px rgba(120,242,160,0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(120,242,160,0); }}
          }}

          .hero-title {{
            margin: 1rem 0 .75rem;
            max-width: 13ch;
            font-family: 'Archivo Black', 'Impact', sans-serif;
            font-size: clamp(2.5rem, 5.2vw, 4.9rem);
            line-height: .98;
          }}

          .hero-subtitle {{
            max-width: 62ch;
            color: rgba(255,248,234,.78);
            font-size: clamp(1rem, 1.4vw, 1.18rem);
          }}

          .city-stream {{
            position: absolute;
            left: 0;
            right: 0;
            bottom: .9rem;
            z-index: 3;
            overflow: hidden;
            border-top: 1px solid rgba(255,248,234,.12);
            border-bottom: 1px solid rgba(255,248,234,.12);
            background: rgba(5,7,8,.42);
          }}

          .city-track {{
            display: flex;
            width: max-content;
            gap: .55rem;
            padding: .55rem .75rem;
            animation: citySweep 82s linear infinite;
          }}

          .city-track:hover {{ animation-play-state: paused; }}

          .city-pill {{
            flex: 0 0 auto;
            border: 1px solid rgba(255,248,234,.18);
            border-radius: 999px;
            padding: .34rem .65rem;
            color: rgba(255,248,234,.86);
            background: rgba(255,255,255,.05);
            font-size: .8rem;
            white-space: nowrap;
          }}

          @keyframes citySweep {{
            from {{ transform: translateX(0); }}
            to {{ transform: translateX(-50%); }}
          }}

          .sun-system {{
            position: absolute;
            right: 5%;
            top: 11%;
            width: 118px;
            height: 118px;
            border-radius: 50%;
            background: radial-gradient(circle, #FFF6A8 0 20%, var(--sun) 21% 55%, rgba(255,211,77,.18) 56% 100%);
            box-shadow: 0 0 44px rgba(255,211,77,.55), 0 0 110px rgba(255,90,54,.22);
            animation: sunBreathe 5.5s ease-in-out infinite;
            z-index: 1;
          }}

          .sun-system::before {{
            content: "";
            position: absolute;
            inset: -34px;
            border-radius: 50%;
            border: 2px dashed rgba(255,211,77,.26);
            animation: rotateSun 18s linear infinite;
          }}

          @keyframes sunBreathe {{
            0%, 100% {{ transform: scale(.96); filter: saturate(1); }}
            50% {{ transform: scale(1.06); filter: saturate(1.18); }}
          }}

          @keyframes rotateSun {{ to {{ transform: rotate(360deg); }} }}

          .rain-field {{
            position: absolute;
            right: 22%;
            top: 16%;
            width: 220px;
            height: 190px;
            transform: rotate(10deg);
            z-index: 2;
            opacity: .52;
          }}

          .drop {{
            position: absolute;
            top: -20px;
            width: 2px;
            height: 34px;
            border-radius: 99px;
            background: linear-gradient(180deg, transparent, var(--rain));
            animation: rainFall 1.1s linear infinite;
          }}

          .drop:nth-child(1) {{ left: 8%; animation-delay: 0s; }}
          .drop:nth-child(2) {{ left: 21%; animation-delay: .18s; }}
          .drop:nth-child(3) {{ left: 34%; animation-delay: .33s; }}
          .drop:nth-child(4) {{ left: 47%; animation-delay: .08s; }}
          .drop:nth-child(5) {{ left: 61%; animation-delay: .47s; }}
          .drop:nth-child(6) {{ left: 74%; animation-delay: .25s; }}
          .drop:nth-child(7) {{ left: 88%; animation-delay: .57s; }}

          @keyframes rainFall {{
            from {{ transform: translateY(0); opacity: 0; }}
            12% {{ opacity: .95; }}
            to {{ transform: translateY(205px); opacity: 0; }}
          }}

          .thermo {{
            position: absolute;
            right: clamp(1rem, 3vw, 2.4rem);
            bottom: 4.5rem;
            width: 42px;
            height: 162px;
            border: 2px solid rgba(255,248,234,.28);
            border-radius: 999px;
            background: rgba(5,7,8,.58);
            z-index: 4;
          }}

          .thermo::before {{
            content: "";
            position: absolute;
            left: 9px;
            right: 9px;
            bottom: 10px;
            height: var(--temp-fill);
            border-radius: 999px;
            background: linear-gradient(180deg, var(--sun), var(--heat));
            box-shadow: 0 0 28px rgba(255,90,54,.5);
            animation: tempRise 3.8s ease-in-out infinite alternate;
          }}

          .thermo::after {{
            content: "";
            position: absolute;
            left: 50%;
            bottom: -20px;
            width: 72px;
            height: 72px;
            border-radius: 50%;
            transform: translateX(-50%);
            background: radial-gradient(circle at 40% 35%, #FFF1A6, var(--heat) 56%, #6B1015 100%);
            box-shadow: 0 0 34px rgba(255,90,54,.55);
          }}

          @keyframes tempRise {{ to {{ filter: brightness(1.18); }} }}

          .metric-strip {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .85rem;
            margin: 1rem 0 1.1rem;
          }}

          .weather-card {{
            min-height: 92px;
            border: 1px solid rgba(214,226,228,.16);
            border-radius: 8px;
            padding: .85rem .95rem;
            background: linear-gradient(180deg, rgba(255,248,234,.06), rgba(255,248,234,.025));
            box-shadow: 0 18px 50px rgba(0,0,0,.26);
          }}

          .weather-card b {{
            display: block;
            color: rgba(255,248,234,.65);
            font-size: .82rem;
            font-weight: 700;
            margin-bottom: .35rem;
          }}

          .weather-card strong {{
            display: block;
            color: var(--text);
            font-family: 'Archivo Black', 'Impact', sans-serif;
            font-size: clamp(1.45rem, 2.15vw, 2.15rem);
            word-break: normal;
            overflow-wrap: normal;
            line-height: .98;
          }}

          .weather-card small {{ color: rgba(255,248,234,.62); }}

          .section-lede {{
            max-width: 72ch;
            color: rgba(255,248,234,.70);
            margin: -.35rem 0 1rem;
          }}

          .source-note {{
            border-left: 4px solid var(--rain);
            background: rgba(53,183,255,.08);
            border-radius: 8px;
            padding: .8rem 1rem;
            color: rgba(255,248,234,.78);
            font-size: .84rem;
            line-height: 1.45;
          }}

          .rank-row {{
            display: grid;
            grid-template-columns: minmax(90px, 150px) 1fr minmax(44px, 70px);
            align-items: center;
            gap: .75rem;
            margin: .65rem 0;
          }}

          .rank-name {{ color: var(--text); font-weight: 800; }}
          .rank-bar {{
            height: 18px;
            border-radius: 999px;
            background: rgba(255,255,255,.08);
            overflow: hidden;
            border: 1px solid rgba(255,255,255,.10);
          }}
          .rank-fill {{
            height: 100%;
            width: var(--bar-width);
            border-radius: inherit;
            background: linear-gradient(90deg, var(--rain), var(--sun), var(--heat));
            animation: fillIn 1.25s cubic-bezier(.2,.8,.2,1) both;
          }}
          @keyframes fillIn {{ from {{ width: 0; }} }}

          .footer-note {{
            color: rgba(255,248,234,.58);
            font-size: .86rem;
            line-height: 1.45;
            margin-top: 1rem;
          }}


          #MainMenu, footer, header [data-testid="stToolbar"] {{
            visibility: hidden;
          }}

          [data-baseweb="tag"] {{
            background: rgba(255,90,54,.92) !important;
            border-radius: 999px !important;
          }}

          [data-testid="stSidebar"] .stMarkdown code {{
            color: var(--clean);
            background: rgba(120,242,160,.08);
            border-radius: 4px;
            padding: .06rem .24rem;
          }}

          .stSlider [data-baseweb="slider"] {{
            filter: saturate(.9);
          }}


          .photo-backdrop {{
            position: absolute;
            inset: 0;
            z-index: 0;
            overflow: hidden;
          }}

          .photo-slide {{
            position: absolute;
            inset: 0;
            background-image: var(--photo);
            background-size: cover;
            background-position: center;
            opacity: 0;
            transform: scale(1.04);
            animation: cityPhotoFade 30s infinite;
          }}

          .photo-slide:nth-child(1) {{ animation-delay: 0s; }}
          .photo-slide:nth-child(2) {{ animation-delay: 6s; }}
          .photo-slide:nth-child(3) {{ animation-delay: 12s; }}
          .photo-slide:nth-child(4) {{ animation-delay: 18s; }}
          .photo-slide:nth-child(5) {{ animation-delay: 24s; }}

          .photo-backdrop::after {{
            content: "";
            position: absolute;
            inset: 0;
            background:
              linear-gradient(90deg, rgba(5,7,8,.92) 0%, rgba(5,7,8,.68) 45%, rgba(5,7,8,.24) 100%),
              linear-gradient(180deg, rgba(5,7,8,.12) 0%, rgba(5,7,8,.52) 100%);
          }}

          @keyframes cityPhotoFade {{
            0% {{ opacity: 0; transform: scale(1.04); }}
            7% {{ opacity: .86; }}
            26% {{ opacity: .86; }}
            34% {{ opacity: 0; transform: scale(1.12); }}
            100% {{ opacity: 0; transform: scale(1.12); }}
          }}

          .city-photo-grid {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: .85rem;
            margin: .35rem 0 1.25rem;
          }}

          .city-photo-card {{
            position: relative;
            min-height: 205px;
            overflow: hidden;
            border-radius: 8px;
            border: 1px solid rgba(214,226,228,.16);
            background-image:
              linear-gradient(180deg, rgba(5,7,8,.02), rgba(5,7,8,.88)),
              var(--photo);
            background-size: cover;
            background-position: center;
            box-shadow: 0 22px 58px rgba(0,0,0,.28);
          }}

          .city-photo-card::before {{
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(255,211,77,.12), transparent 38%, rgba(53,183,255,.14));
            opacity: .9;
          }}

          .city-photo-content {{
            position: absolute;
            inset: auto 0 0;
            padding: .95rem;
            z-index: 1;
          }}

          .city-photo-kicker {{
            display: inline-flex;
            padding: .24rem .45rem;
            border-radius: 999px;
            background: rgba(5,7,8,.56);
            border: 1px solid rgba(255,248,234,.22);
            color: rgba(255,248,234,.78);
            font-size: .72rem;
            font-weight: 700;
          }}

          .city-photo-name {{
            margin-top: .5rem;
            color: var(--text);
            font-family: 'Archivo Black', 'Impact', sans-serif;
            font-size: 1.5rem;
            line-height: .95;
            text-shadow: 0 4px 18px rgba(0,0,0,.55);
          }}

          .city-photo-stats {{
            display: flex;
            gap: .5rem;
            flex-wrap: wrap;
            margin-top: .65rem;
          }}

          .city-photo-stats span {{
            display: inline-flex;
            align-items: center;
            gap: .25rem;
            border-radius: 999px;
            background: rgba(255,248,234,.10);
            color: rgba(255,248,234,.86);
            padding: .22rem .45rem;
            font-size: .76rem;
            font-weight: 700;
          }}

          @media (max-width: 1400px) {{
            .metric-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .city-photo-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
          }}

          @media (max-width: 900px) {{
            .metric-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .city-photo-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .sun-system {{ right: -10px; top: 8%; opacity: .55; }}
            .rain-field {{ right: 8%; opacity: .45; }}
            .thermo {{ display: none; }}
            .weather-stage {{ min-height: 420px; }}
          }}

          @media (max-width: 620px) {{
            .metric-strip {{ grid-template-columns: 1fr; }}
            .city-photo-grid {{ grid-template-columns: 1fr; }}
            .hero-title {{ font-size: 3.2rem; }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def km_between(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius_km = 6371.0
    d_lat = radians(lat_b - lat_a)
    d_lon = radians(lon_b - lon_a)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(d_lon / 2) ** 2
    return 2 * radius_km * asin(sqrt(a))


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        st.error(
            f"DuckDB database not found at `{DB_PATH}`. Build it first with "
            "`python scripts/load_to_duckdb.py` and `dbt build`."
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
        """
        select city_name, air_quality_date, avg_european_aqi, avg_pm2_5
        from main.fct_air_quality_city_day
        """
    ).df()


@st.cache_data(ttl=600)
def atlas_base(summary: pd.DataFrame) -> pd.DataFrame:
    return summary[["city_name", "latitude", "longitude", "country"]].rename(
        columns={"city_name": "city", "latitude": "lat", "longitude": "lon", "country": "region"}
    )


def style_fig(fig: go.Figure, height: int = 380, show_legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=18, r=18, t=42, b=18),
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=12, color=TEXT),
        legend=dict(
            orientation="h",
            y=1.05,
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=MUTED, size=11),
        ),
        showlegend=show_legend,
        colorway=CITY_COLORS,
    )
    fig.update_xaxes(gridcolor="rgba(214,226,228,.10)", linecolor=LINE, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(214,226,228,.10)", linecolor=LINE, zeroline=False)
    return fig


def build_filtered_ranking(weather: pd.DataFrame, aqi: pd.DataFrame) -> pd.DataFrame:
    ranking = (
        weather.groupby("city_name")
        .agg(
            days=("weather_date", "count"),
            comfortable_days=("is_comfortable", "sum"),
            rainy_days=("is_rainy", "sum"),
            windy_days=("is_windy", "sum"),
            hot_days=("is_hot", "sum"),
            freezing_days=("is_freezing", "sum"),
            avg_temp=("temperature_2m_mean", "mean"),
            max_temp=("temperature_2m_max", "max"),
            min_temp=("temperature_2m_min", "min"),
            rain_mm=("precipitation_sum", "sum"),
            wind_kmh=("wind_speed_10m_max", "mean"),
        )
        .reset_index()
    )
    ranking["comfort_score"] = (100 * ranking["comfortable_days"] / ranking["days"]).round(1)
    aqi_by_city = aqi.groupby("city_name")["avg_european_aqi"].mean().reset_index()
    ranking = ranking.merge(aqi_by_city, on="city_name", how="left")
    ranking["avg_european_aqi"] = ranking["avg_european_aqi"].fillna(0)
    ranking["overall_comfort_index"] = (
        ranking["comfort_score"] - 0.5 * ranking["avg_european_aqi"]
    ).round(1)
    return ranking.sort_values("overall_comfort_index", ascending=False)


def build_atlas_animation(
    atlas: pd.DataFrame,
    weather_all: pd.DataFrame,
    summary: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    measured = summary[["city_name", "latitude", "longitude"]].dropna().copy()
    measured_weather = weather_all[
        weather_all["weather_date"].between(start_date, end_date)
    ].copy()

    if measured.empty or measured_weather.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for _, city in atlas.iterrows():
        distances = measured.apply(
            lambda r: km_between(city["lat"], city["lon"], r["latitude"], r["longitude"]), axis=1
        )
        source = measured.loc[distances.idxmin(), "city_name"]
        source_days = measured_weather[measured_weather["city_name"] == source].sort_values("weather_date")
        if source_days.empty:
            source_days = measured_weather.sort_values("weather_date")

        nearest = measured[measured["city_name"] == source].iloc[0]
        distance = float(distances.min())
        south_warmth = (40.4 - float(city["lat"])) * 0.42
        coast_cool = -0.8 if abs(float(city["lon"])) < 1.0 or city["region"] in {"Canarias", "Illes Balears"} else 0.0
        source_lat_adjust = (float(nearest["latitude"]) - float(city["lat"])) * 0.12
        phase = ((abs(hash(city["city"])) % 628) / 100.0)

        for day_number, (_, day) in enumerate(source_days.iterrows()):
            wave = sin(day_number * 0.92 + phase) * 0.9
            temp = float(day["temperature_2m_mean"]) + south_warmth + coast_cool + source_lat_adjust + wave
            rain = max(0.0, float(day["precipitation_sum"]) * (1 + min(distance, 850) / 2400))
            comfort = max(0.0, min(100.0, 100 - abs(temp - 22) * 5.2 - rain * 7.0))
            rows.append(
                {
                    "city": city["city"],
                    "region": city["region"],
                    "lat": city["lat"],
                    "lon": city["lon"],
                    "weather_date": day["weather_date"],
                    "frame": pd.Timestamp(day["weather_date"]).strftime("%d %b"),
                    "temperature_c": round(temp, 1),
                    "rain_mm": round(rain, 1),
                    "comfort": round(comfort, 1),
                    "signal_city": source,
                    "signal_distance_km": round(distance, 0),
                    "pulse_size": max(7.0, 13.0 + rain * 3.2 + max(0, temp - 25) * 0.5),
                }
            )
    return pd.DataFrame(rows)



def city_photo_url(city_name: str) -> str:
    return CITY_PHOTOS.get(city_name, DEFAULT_CITY_PHOTO)


def city_photo_gallery(ranking: pd.DataFrame) -> str:
    cards = []
    photo_cities = [city for city in CITY_PHOTOS if city in set(ranking["city_name"])]
    rows = ranking.set_index("city_name").loc[photo_cities].reset_index()
    for _, row in rows.iterrows():
        city = str(row["city_name"])
        cards.append(
            f'<article class="city-photo-card" style="--photo: url(&quot;{city_photo_url(city)}&quot;);">'
            f'<div class="city-photo-content">'
            f'<span class="city-photo-kicker">Measured city</span>'
            f'<div class="city-photo-name">{escape(city)}</div>'
            f'<div class="city-photo-stats">'
            f'<span>{float(row["avg_temp"]):.1f} C</span>'
            f'<span>{float(row["rain_mm"]):.1f} mm</span>'
            f'<span>{float(row["overall_comfort_index"]):.1f} comfort</span>'
            f'</div></div></article>'
        )
    return '<section class="city-photo-grid">' + ''.join(cards) + '</section>'


def metric_card(label: str, value: str, detail: str, color: str) -> str:
    return (
        f'<div class="weather-card" style="border-top: 4px solid {color};">'
        f'<b>{escape(label)}</b>'
        f'<strong>{escape(value)}</strong>'
        f'<small>{escape(detail)}</small>'
        "</div>"
    )


def render_hero(
    best_city: str,
    city_count: int,
    date_span: str,
    temp_fill: int,
    selected_cities: list[str],
    ticker_cities: list[str],
) -> None:
    city_names = [escape(city) for city in ticker_cities]
    city_pills = "".join(f'<span class="city-pill">{name}</span>' for name in city_names * 2)
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    hero_cities = [city for city in selected_cities if city in CITY_PHOTOS] or list(CITY_PHOTOS)
    hero_cities = (hero_cities + list(CITY_PHOTOS))[:5]
    photo_layers = "".join(
        f'<span class="photo-slide" style="--photo: url(&quot;{city_photo_url(city)}&quot;);"></span>'
        for city in hero_cities
    )
    st.markdown(
        f"""
        <section class="weather-stage" style="--temp-fill: {temp_fill}%;">
          <div class="photo-backdrop">{photo_layers}</div>
          <div class="stage-waves" aria-hidden="true">
            <span class="stage-wave"></span><span class="stage-wave"></span><span class="stage-wave"></span>
          </div>
          <div class="light-gate" aria-hidden="true"></div>
          <div class="hero-copy">
            <div class="eyebrow"><span class="pulse-dot"></span>Mart-powered weather signal - {now}</div>
            <div class="hero-title">Spain Climate Observatory</div>
            <p class="hero-subtitle">
              Real city backdrops, measured weather marts, and a Spanish city atlas moving through temperature, rain and air-quality signals across Spain.
            </p>
          </div>
          <div class="sun-system"></div>
          <div class="rain-field" aria-hidden="true">
            <span class="drop"></span><span class="drop"></span><span class="drop"></span>
            <span class="drop"></span><span class="drop"></span><span class="drop"></span><span class="drop"></span>
          </div>
          <div class="thermo" aria-hidden="true"></div>
          <div class="city-stream"><div class="city-track">{city_pills}</div></div>
        </section>
        <div class="metric-strip">
          {metric_card("Leading city", best_city, "Highest comfort index in the selected window", CLEAN)}
          {metric_card("Graph focus", f"{city_count} cities", "Add or remove measured cities in the sidebar", RAIN)}
          {metric_card("Window", date_span, "Filtered city-day evidence from dbt marts", SUN)}
          {metric_card("City stream", f"{len(ticker_cities)} cities", "Provincial capitals plus extra measured cities", HEAT)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def rank_html(ranking: pd.DataFrame) -> str:
    if ranking.empty:
        return ""
    low = float(ranking["overall_comfort_index"].min())
    high = float(ranking["overall_comfort_index"].max())
    spread = max(high - low, 1)
    rows = []
    for _, row in ranking.iterrows():
        width = 14 + ((float(row["overall_comfort_index"]) - low) / spread) * 86
        rows.append(
            f"""
            <div class="rank-row">
              <div class="rank-name">{escape(str(row['city_name']))}</div>
              <div class="rank-bar"><div class="rank-fill" style="--bar-width: {width:.1f}%"></div></div>
              <div>{row['overall_comfort_index']:.1f}</div>
            </div>
            """
        )
    return "".join(rows)


inject_css()

summary = load_summary()
weather = load_daily_weather()
aqi = load_daily_aqi()
atlas = atlas_base(summary)

weather["weather_date"] = pd.to_datetime(weather["weather_date"])
aqi["air_quality_date"] = pd.to_datetime(aqi["air_quality_date"])

st.sidebar.title("Signal controls")
all_cities = sorted(summary["city_name"].dropna().tolist())
available_demo_cities = [city for city in DEFAULT_DEMO_CITIES if city in all_cities]
city_checkbox_keys = {city: f"city_check_{idx}" for idx, city in enumerate(all_cities)}


def apply_city_selection(cities: list[str]) -> None:
    selected = [city for city in cities if city in all_cities]
    st.session_state.selected_cities = selected
    selected_set = set(selected)
    for city, key in city_checkbox_keys.items():
        st.session_state[key] = city in selected_set


if not st.session_state.get("city_selector_initialized"):
    apply_city_selection(available_demo_cities or all_cities[:5])
    st.session_state.city_selector_initialized = True
else:
    st.session_state.selected_cities = [
        city for city in st.session_state.selected_cities if city in all_cities
    ]
    selected_set = set(st.session_state.selected_cities)
    for city, key in city_checkbox_keys.items():
        if key not in st.session_state:
            st.session_state[key] = city in selected_set


def set_demo_cities() -> None:
    apply_city_selection(available_demo_cities or all_cities[:5])


def set_all_cities() -> None:
    apply_city_selection(list(all_cities))


def clear_city_selection() -> None:
    apply_city_selection([])

st.sidebar.markdown(
    f"""
    <div class="source-note">
      <b>Demo preset</b><br>
      Starts with the original {len(available_demo_cities) or min(5, len(all_cities))}-city view for readable flows.
      Add or remove any of the {len(all_cities)} measured cities below; the opening city stream still lists the full atlas.
    </div>
    """,
    unsafe_allow_html=True,
)

preset_left, preset_mid, preset_right = st.sidebar.columns(3)
preset_left.button("Demo 5", use_container_width=True, on_click=set_demo_cities)
preset_mid.button(f"All {len(all_cities)}", use_container_width=True, on_click=set_all_cities)
preset_right.button("Clear", use_container_width=True, on_click=clear_city_selection)

with st.sidebar.expander("Graph city checklist", expanded=True):
    st.caption("Tick cities on or off. The graphs update from this checklist.")
    for city in all_cities:
        st.checkbox(city, key=city_checkbox_keys[city])

selected_cities = [
    city for city in all_cities if st.session_state.get(city_checkbox_keys[city], False)
]
st.session_state.selected_cities = selected_cities
if not selected_cities:
    st.warning("Select at least one measured city to continue.")
    st.stop()

min_date = weather["weather_date"].min().date()
max_date = weather["weather_date"].max().date()
date_range = st.sidebar.slider(
    "Evidence window",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="DD MMM",
)
start_date, end_date = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])

st.sidebar.markdown(
    f"""
    <div class="source-note">
      <b>Data lineage</b><br>
      Measured values come from <code>mart_city_weather_summary</code>,
      <code>fct_city_weather_day</code> and <code>fct_air_quality_city_day</code>.
      Showing {len(selected_cities)} of {len(all_cities)} measured cities from <code>spain_cities.csv</code>.
      Graphs use this selected city set; the opening motion streams all {len(all_cities)} measured cities.
    </div>
    """,
    unsafe_allow_html=True,
)

w = weather[
    weather["city_name"].isin(selected_cities)
    & weather["weather_date"].between(start_date, end_date)
].copy()
a = aqi[
    aqi["city_name"].isin(selected_cities)
    & aqi["air_quality_date"].between(start_date, end_date)
].copy()

if w.empty:
    st.warning("No weather rows in this range. Widen the evidence window.")
    st.stop()

ranking = build_filtered_ranking(w, a)
best = ranking.iloc[0]
date_span = f"{start_date:%d %b} to {end_date:%d %b}"
mean_temp = float(w["temperature_2m_mean"].mean())
temp_fill = int(max(18, min(86, (mean_temp / 40) * 100)))

render_hero(str(best["city_name"]), len(selected_cities), date_span, temp_fill, selected_cities, all_cities)

st.markdown(city_photo_gallery(ranking), unsafe_allow_html=True)

selected_summary = summary[summary["city_name"].isin(selected_cities)].copy()
selected_atlas = atlas[atlas["city"].isin(selected_cities)].copy()
atlas_anim = build_atlas_animation(selected_atlas, w, selected_summary, start_date, end_date)

st.header("Spanish Weather Atlas")
st.markdown(
    f"<p class='section-lede'>Watch all {len(selected_cities)} selected Spanish cities evolve through the selected dates. "
    "Color shows temperature, marker size reacts to rain, and hover text reveals the measured "
    "mart signal for each city.</p>",
    unsafe_allow_html=True,
)

if not atlas_anim.empty:
    fig_atlas = px.scatter_geo(
        atlas_anim,
        lat="lat",
        lon="lon",
        hover_name="city",
        animation_frame="frame",
        color="temperature_c",
        size="pulse_size",
        size_max=24,
        color_continuous_scale=TEMP_SCALE,
        range_color=[atlas_anim["temperature_c"].min() - 1, atlas_anim["temperature_c"].max() + 1],
        hover_data={
            "region": True,
            "temperature_c": ":.1f",
            "rain_mm": ":.1f",
            "comfort": ":.1f",
            "signal_city": True,
            "signal_distance_km": ":.0f",
            "lat": False,
            "lon": False,
            "pulse_size": False,
            "frame": False,
        },
        labels={"temperature_c": "Temp C"},
    )
    fig_atlas.update_geos(
        visible=False,
        projection_type="natural earth",
        center=dict(lat=39.4, lon=-3.2),
        lataxis_range=[27.0, 44.7],
        lonaxis_range=[-18.5, 5.3],
        showcountries=True,
        countrycolor="rgba(214,226,228,.22)",
        showland=True,
        landcolor="#101A20",
        showocean=True,
        oceancolor="#07131A",
        showlakes=True,
        lakecolor="#07131A",
        coastlinecolor="rgba(214,226,228,.32)",
        bgcolor="rgba(0,0,0,0)",
    )
    fig_atlas.update_traces(marker=dict(line=dict(width=1, color="rgba(255,248,234,.72)"), opacity=.9))
    fig_atlas.update_layout(
        height=560,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", color=TEXT),
        coloraxis_colorbar=dict(title="Temp C", tickcolor=MUTED, tickfont=dict(color=MUTED)),
    )
    if fig_atlas.layout.updatemenus:
        fig_atlas.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 650
        fig_atlas.layout.updatemenus[0].buttons[0].args[1]["transition"]["duration"] = 450
    st.plotly_chart(fig_atlas, width="stretch")
else:
    st.info("The atlas animation needs measured mart rows in the selected date window.")

left, right = st.columns([.95, 1.05])
with left:
    st.subheader("Measured Comfort Race")
    st.markdown(rank_html(ranking), unsafe_allow_html=True)
    st.markdown(
        "<p class='footer-note'>Comfort index is recalculated from the selected mart city-days, "
        "then penalized by average European AQI.</p>",
        unsafe_allow_html=True,
    )

with right:
    st.subheader("Live Instruments")
    gauges = go.Figure()
    gauge_specs = [
        ("Comfort", float(ranking["overall_comfort_index"].mean()), -20, 80, CLEAN),
        ("Temp", mean_temp, 0, 42, SUN),
        ("AQI", float(a["avg_european_aqi"].mean()) if not a.empty else 0, 0, 100, RAIN),
    ]
    for index, (title, value, vmin, vmax, color) in enumerate(gauge_specs):
        gauges.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=round(value, 1),
                title={"text": title, "font": {"size": 18}},
                domain={"row": 0, "column": index},
                gauge={
                    "axis": {"range": [vmin, vmax], "tickcolor": MUTED},
                    "bar": {"color": color, "thickness": .28},
                    "bgcolor": "rgba(255,255,255,.03)",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [vmin, (vmax - vmin) * .33 + vmin], "color": "rgba(53,183,255,.10)"},
                        {"range": [(vmax - vmin) * .33 + vmin, (vmax - vmin) * .66 + vmin], "color": "rgba(255,211,77,.12)"},
                        {"range": [(vmax - vmin) * .66 + vmin, vmax], "color": "rgba(255,90,54,.12)"},
                    ],
                },
                number={"font": {"size": 28}},
            )
        )
    gauges.update_layout(
        grid={"rows": 1, "columns": 3, "pattern": "independent"},
        height=305,
        margin=dict(l=20, r=20, t=45, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family="IBM Plex Sans, Segoe UI, sans-serif"),
    )
    st.plotly_chart(gauges, width="stretch")

st.header("Measured City Signals")
st.markdown(
    "<p class='section-lede'>The next panels stay strictly on the measured mart rows: "
    "temperature trajectories, rain bursts, air quality drift and day-type composition.</p>",
    unsafe_allow_html=True,
)

trend_left, trend_right = st.columns([1.25, .95])
with trend_left:
    st.subheader("Temperature Flow")
    fig_front = go.Figure()
    for idx, city in enumerate(sorted(w["city_name"].unique())):
        d = w[w["city_name"] == city].sort_values("weather_date")
        color = CITY_COLORS[idx % len(CITY_COLORS)]
        fig_front.add_trace(
            go.Scatter(
                x=d["weather_date"],
                y=d["temperature_2m_mean"],
                name=city,
                mode="lines+markers",
                line=dict(color=color, width=3, shape="spline"),
                marker=dict(size=7, color=color, line=dict(width=1, color=TEXT)),
                fill="tozeroy",
                fillcolor=rgba(color, .10),
            )
        )
    fig_front.update_layout(yaxis_title="Mean temp C", xaxis_title="")
    st.plotly_chart(style_fig(fig_front, 410), width="stretch")

with trend_right:
    st.subheader("Rain Cells")
    rain = w.groupby(["weather_date", "city_name"], as_index=False)["precipitation_sum"].sum()
    fig_rain = px.scatter(
        rain,
        x="weather_date",
        y="city_name",
        size="precipitation_sum",
        color="precipitation_sum",
        size_max=36,
        color_continuous_scale=RAIN_SCALE,
        labels={"precipitation_sum": "Rain mm", "weather_date": "", "city_name": ""},
    )
    fig_rain.update_traces(marker=dict(line=dict(width=1, color="rgba(255,248,234,.45)")))
    st.plotly_chart(style_fig(fig_rain, 410, show_legend=False), width="stretch")

heat_left, heat_right = st.columns([1.05, 1.05])
with heat_left:
    st.subheader("Thermal Grid")
    pivot = w.pivot_table(
        index="city_name",
        columns="weather_date",
        values="temperature_2m_mean",
        aggfunc="mean",
    )
    fig_heat = px.imshow(
        pivot,
        color_continuous_scale=TEMP_SCALE,
        aspect="auto",
        labels={"x": "", "y": "", "color": "Temp C"},
    )
    fig_heat.update_xaxes(tickformat="%d %b", nticks=10)
    st.plotly_chart(style_fig(fig_heat, 330, show_legend=False), width="stretch")

with heat_right:
    st.subheader("Air Quality Drift")
    if not a.empty:
        fig_aqi = px.line(
            a.sort_values("air_quality_date"),
            x="air_quality_date",
            y="avg_european_aqi",
            color="city_name",
            markers=True,
            color_discrete_sequence=CITY_COLORS,
            labels={"air_quality_date": "", "avg_european_aqi": "European AQI", "city_name": ""},
        )
        fig_aqi.update_traces(line=dict(width=3), marker=dict(size=7, line=dict(width=1, color=TEXT)))
        st.plotly_chart(style_fig(fig_aqi, 330), width="stretch")
    else:
        st.info("No air-quality rows in this selection.")

composition_left, composition_right = st.columns([.9, 1.1])
with composition_left:
    st.subheader("Day Types")
    melted = ranking.melt(
        id_vars="city_name",
        value_vars=["comfortable_days", "rainy_days", "windy_days", "hot_days", "freezing_days"],
        var_name="condition",
        value_name="day_count",
    )
    melted["condition"] = melted["condition"].map(
        {
            "comfortable_days": "Comfortable",
            "rainy_days": "Rainy",
            "windy_days": "Windy",
            "hot_days": "Hot",
            "freezing_days": "Freezing",
        }
    )
    fig_types = px.bar(
        melted,
        x="day_count",
        y="city_name",
        color="condition",
        orientation="h",
        color_discrete_map={
            "Comfortable": CLEAN,
            "Rainy": RAIN,
            "Windy": FOG,
            "Hot": HEAT,
            "Freezing": "#7FB5FF",
        },
        labels={"day_count": "Days", "city_name": "", "condition": ""},
    )
    st.plotly_chart(style_fig(fig_types, 360), width="stretch")

with composition_right:
    st.subheader("Comfort Profile")
    radar = go.Figure()
    aqi_max = max(float(ranking["avg_european_aqi"].max()), 1.0)
    for idx, (_, r) in enumerate(ranking.iterrows()):
        values = [
            min(100, max(0, (float(r["avg_temp"]) / 30) * 100)),
            float(r["comfort_score"]),
            100 - min(100, float(r["avg_european_aqi"]) / aqi_max * 100),
            100 - float(r["windy_days"]) / float(r["days"]) * 100,
            100 - float(r["rainy_days"]) / float(r["days"]) * 100,
        ]
        color = CITY_COLORS[idx % len(CITY_COLORS)]
        radar.add_trace(
            go.Scatterpolar(
                r=values,
                theta=["Warmth", "Comfort", "Clean air", "Calm", "Dry"],
                fill="toself",
                name=str(r["city_name"]),
                line=dict(color=color, width=2),
                fillcolor=rgba(color, .10),
            )
        )
    radar.update_layout(
        template="plotly_dark",
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", color=TEXT, size=12),
        margin=dict(l=28, r=28, t=44, b=20),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], gridcolor="rgba(214,226,228,.13)", showticklabels=False),
            angularaxis=dict(gridcolor="rgba(214,226,228,.13)"),
        ),
        legend=dict(orientation="h", y=1.13, x=0, bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(radar, width="stretch")

st.header("Evidence Table")
table = ranking[
    [
        "city_name",
        "days",
        "avg_temp",
        "max_temp",
        "rain_mm",
        "comfortable_days",
        "rainy_days",
        "windy_days",
        "hot_days",
        "comfort_score",
        "avg_european_aqi",
        "overall_comfort_index",
    ]
].rename(
    columns={
        "city_name": "City",
        "days": "Days",
        "avg_temp": "Avg temp C",
        "max_temp": "Max temp C",
        "rain_mm": "Rain mm",
        "comfortable_days": "Comfortable",
        "rainy_days": "Rainy",
        "windy_days": "Windy",
        "hot_days": "Hot",
        "comfort_score": "Comfort score",
        "avg_european_aqi": "Avg AQI",
        "overall_comfort_index": "Overall index",
    }
)
st.dataframe(
    table.style.format(
        {
            "Avg temp C": "{:.1f}",
            "Max temp C": "{:.1f}",
            "Rain mm": "{:.1f}",
            "Comfort score": "{:.1f}",
            "Avg AQI": "{:.1f}",
            "Overall index": "{:.1f}",
        }
    ),
    hide_index=True,
    width="stretch",
)

with st.expander("Metric definitions and lineage"):
    st.markdown(
        """
        - Comfortable day: mean temperature from 18 to 26 C, with no rain, wind, heat or freezing flags.
        - Comfort score: 100 * comfortable days / total days.
        - Overall comfort index: comfort score - 0.5 * average European AQI.
        - Spanish atlas: measured dbt mart cities from `spain_cities.csv`; visual smoothing is used only for animated transitions.
        - Measured analysis: all KPIs, rankings and charts after the atlas read only from dbt mart tables in DuckDB.
        """
    )

st.markdown(
    "<p class='footer-note'>Source: Open-Meteo APIs to DuckDB to dbt marts to Streamlit. "
    "Dashboard generated from mart models only; no raw API tables are queried here.</p>",
    unsafe_allow_html=True,
)

