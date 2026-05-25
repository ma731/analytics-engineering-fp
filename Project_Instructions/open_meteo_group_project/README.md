# Group Assignment: Weather Analytics Engineering with Open-Meteo

## Objective

Build an end-to-end analytics engineering project using data extracted from the Open-Meteo API.

Your group will:

1. Extract raw data from public API endpoints.
2. Load the extracted files into your warehouse.
3. Register the raw files or tables as dbt sources.
4. Build `stg`, `int`, `dim`, `fct`, and mart models.
5. Create a Streamlit dashboard from your final dbt models.
6. Publish your work in a GitHub repository with clear instructions for running or viewing the dashboard.

The recommended stack is:

- DuckDB
- dbt Core
- Streamlit
- Python

You may use another warehouse if your group prefers, such as BigQuery, Snowflake, Postgres, or MotherDuck. If you do, your README must explain how I can run or inspect the project.

---

## API

Use Open-Meteo:

- Main API documentation: <https://open-meteo.com/en/docs>
- Forecast API: <https://open-meteo.com/en/docs>
- Air Quality API: <https://open-meteo.com/en/docs/air-quality-api>
- Geocoding API: <https://open-meteo.com/en/docs/geocoding-api>
- Historical Weather API, optional extension: <https://open-meteo.com/en/docs/historical-weather-api>

Open-Meteo is suitable for this assignment because:

- It does not require an API key for non-commercial usage.
- It returns JSON.
- It supports location search, historical weather, forecasts, and air quality.
- It has clear query parameters and predictable response structures.

---

## Starter Extraction Script

A starter script is provided in:

```text
scripts/extract_open_meteo.py
```

Run it from this assignment folder:

```bash
uv run python scripts/extract_open_meteo.py
```

If you are not using `uv`, use your active Python environment:

```bash
python scripts/extract_open_meteo.py
```

By default, it extracts data for:

- Madrid
- Barcelona
- Valencia
- Sevilla
- Bilbao

It writes CSV files to:

```text
data/raw/open_meteo/
```

Expected output files:

```text
raw_locations.csv
raw_weather_daily.csv
raw_forecast_daily.csv
raw_air_quality_hourly.csv
```

You can choose your own cities and dates:

```bash
uv run python scripts/extract_open_meteo.py \
  --cities Madrid Barcelona Paris Berlin Lisbon \
  --past-days 60 \
  --forecast-days 7
```

The script uses the Python standard library and will automatically use `certifi` for SSL certificates if it is available in your environment. You may replace or extend the script with `requests`, `pandas`, `polars`, Airflow, Dagster, or another tool if you document your approach.

---

## How the API Connection Works

The extraction process has four steps.

### 1. Convert City Names to Coordinates

Open-Meteo weather APIs require latitude and longitude, not just city names.

Example geocoding request:

```text
https://geocoding-api.open-meteo.com/v1/search?name=Madrid&count=1&language=en&format=json
```

The script stores the selected result in `raw_locations.csv`.

### 2. Extract Recent Daily Weather

The starter script uses the Forecast API with `past_days`. This gives recent daily weather data and avoids API keys or separate historical archive infrastructure.

Example recent weather request:

```text
https://api.open-meteo.com/v1/forecast?latitude=40.4168&longitude=-3.7038&past_days=30&forecast_days=1&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,rain_sum,snowfall_sum,wind_speed_10m_max&timezone=Europe/Madrid
```

The script stores this in `raw_weather_daily.csv`.

If your group wants a longer historical period, you can extend the script to use the Historical Weather API.

### 3. Extract Daily Forecasts

Example forecast request:

```text
https://api.open-meteo.com/v1/forecast?latitude=40.4168&longitude=-3.7038&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,rain_sum,snowfall_sum,wind_speed_10m_max&timezone=Europe/Madrid
```

The script stores this in `raw_forecast_daily.csv`.

Each row includes `extracted_at`, so repeated runs can be kept as different forecast snapshots.

### 4. Extract Hourly Air Quality

Example air quality request:

```text
https://air-quality-api.open-meteo.com/v1/air-quality?latitude=40.4168&longitude=-3.7038&hourly=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone,european_aqi&timezone=Europe/Madrid
```

The script stores this in `raw_air_quality_hourly.csv`.

---

## Suggested Raw Sources

Use the extracted files as raw dbt sources.

Suggested source tables:

| Source table | Grain | Description |
|---|---:|---|
| `raw_locations` | one row per selected city | City metadata from the Geocoding API |
| `raw_weather_daily` | one row per city per day | Recent daily weather from the Forecast API `past_days` parameter |
| `raw_forecast_daily` | one row per city per forecast date per extraction run | Forecasted daily weather |
| `raw_air_quality_hourly` | one row per city per hour | Air quality forecast observations |

If you use DuckDB, you can load the CSV files directly into DuckDB tables, or define them as external sources depending on your project setup.

---

## Required dbt Modeling Layers

Your project must include at least:

### Staging Models

Create one staging model per raw source.

Examples:

```text
models/staging/stg_locations.sql
models/staging/stg_weather_daily.sql
models/staging/stg_forecast_daily.sql
models/staging/stg_air_quality_hourly.sql
```

Staging models should:

- rename fields into clear snake_case names
- cast dates, timestamps, numbers, and booleans
- remove duplicate rows if needed
- keep the same grain as the raw source
- avoid business logic beyond light cleaning

### Intermediate Models

Create models that combine or enrich staging data.

Examples:

```text
models/intermediate/int_air_quality_daily.sql
models/intermediate/int_city_day_weather.sql
models/intermediate/int_forecast_accuracy.sql
models/intermediate/int_weather_flags.sql
```

Intermediate models should answer analytical preparation questions, such as:

- What is the daily average air quality per city?
- Which city-days were rainy, hot, windy, or polluted?
- How accurate was the forecast compared with historical weather once actuals are available?

### Fact and Dimension Models

Create at least:

```text
models/marts/dim_location.sql
models/marts/fct_city_weather_day.sql
```

Recommended additional models:

```text
models/marts/fct_air_quality_city_day.sql
models/marts/fct_forecast_city_day.sql
models/marts/mart_city_weather_summary.sql
```

Your fact tables should have a clear grain. For example:

```text
fct_city_weather_day: one row per city per date
```

### Data Tests

Add dbt tests for important assumptions:

- primary keys are unique and not null
- dates are not null
- city/location keys are not null
- relationships between fact tables and `dim_location`
- accepted values for categorical fields, if you create any
- reasonable ranges for weather metrics where useful

---

## Dashboard Requirements

Build a Streamlit dashboard that reads from your final mart models, not from the raw API files.

Your dashboard should include:

- at least one filter, such as city, country, date range, or metric
- at least three charts or tables
- clear metric definitions
- a short note explaining the grain of the main model used
- a clear way for me to run or view the dashboard

Good delivery options:

1. Deploy the dashboard to Streamlit Community Cloud and include the public URL in your README.
2. Provide exact local run instructions, including environment setup and `streamlit run ...`.
3. Provide both a public URL and local run instructions.

---

## Dashboard Ideas

Choose one of these, combine them, or propose your own.

### 1. City Comfort Index

Question:

Which cities had the most comfortable weather during the selected period?

Possible metrics:

- average temperature
- number of comfortable days
- rainy days
- windy days
- extreme heat days
- air quality score
- overall comfort score

Possible charts:

- city ranking table
- monthly comfort trend
- map of selected cities
- distribution of daily temperatures

### 2. Weather Risk Monitor

Question:

Which cities experienced the most disruptive weather conditions?

Possible metrics:

- heavy rain days
- high wind days
- extreme heat days
- poor air quality hours
- longest streak of risky days

Possible charts:

- risk score by city
- calendar heatmap
- daily risk timeline
- top 10 most extreme city-days

### 3. Forecast vs Actual Performance

Question:

How close were weather forecasts to observed historical weather?

Possible metrics:

- forecast temperature error
- forecast precipitation error
- days where forecast missed rain
- mean absolute error by city
- error by forecast horizon, if your extraction captures repeated runs over time

Possible charts:

- actual vs forecast line chart
- error by city
- error by month
- worst forecast misses

Note: This dashboard works best if your group runs the extraction multiple times over several days, or if you design your extraction process to preserve `extracted_at` as a forecast run timestamp.

---

## Suggested Project Structure

Your group repository can follow this structure:

```text
.
├── data/
│   └── raw/
│       └── open_meteo/
├── scripts/
│   └── extract_open_meteo.py
├── models/
│   ├── staging/
│   ├── intermediate/
│   └── marts/
├── streamlit_app/
│   └── app.py
├── dbt_project.yml
├── profiles.yml
├── packages.yml
├── pyproject.toml
└── README.md
```

You may choose a different structure, but it must be easy to understand.

---

## Final Deliverable

Submit a GitHub repository link.

Your repository must include:

- the extraction script or pipeline code
- the raw source files, or instructions to reproduce them
- the dbt project
- a Streamlit dashboard
- a README with setup instructions
- a clear command or link for viewing the dashboard
- a short explanation of your modeling choices
- screenshots are optional but recommended

The README should make this obvious:

```text
How do I run the extraction?
How do I load the data?
How do I run dbt?
How do I launch or view the dashboard?
What final models power the dashboard?
```

---

## Evaluation Criteria

Your project will be evaluated on:

- Correct extraction from the API
- Clear source definitions
- Clean staging models
- Meaningful intermediate transformations
- Well-designed fact and dimension models
- dbt tests and documentation
- Dashboard usefulness and clarity
- Reproducibility from the GitHub repository
- Code organization and readability

Focus on a small, well-modeled project rather than a large project with unclear logic.
