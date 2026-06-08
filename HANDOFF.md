# HANDOFF — analytics-engineering-fp

> Purpose: let another person or AI tool understand what was done, the current
> state, and **verify it independently**. Updated 2026-06-08.

## 1. What this project is

IE "Analytics Engineering" final group project. End-to-end pipeline over the
Open-Meteo API for **58 Spanish cities** (from `spain_cities.csv` — province
capitals + major cities):

```
Open-Meteo APIs → Python extract → DuckDB → dbt (staging → intermediate → marts) → Streamlit
```

- Team repo: `https://github.com/moanv2/analytics-engineering-fp`
- Working branch: `feat/marts-tests-dashboard` (PR into protected `main`, needs review)
- Grading rubric (source of truth): upstream `dgarhdez/dbt-ie` →
  `assignments/open_meteo_group_project/README.md`

## 2. Current state

- **dbt**: 4 staging + 3 intermediate + 5 mart models. `dbt build` =
  **12 models, 72 tests, 84/84 passing** on the 58-city data.
- **Marts** (what the dashboard reads): `dim_location` (one row per city),
  `fct_city_weather_day`, `fct_air_quality_city_day`, `fct_forecast_city_day`
  (one row per city per day), `mart_city_weather_summary` (one row per city).
- **Dashboard**: `streamlit_app/app.py` — light "brutalist website" design
  (white canvas, terracotta hero, thick ink borders, hard offset shadows,
  Darker Grotesque + JetBrains Mono). Sections: site top bar + hero, pulsing
  LIVE bar, KPI cards, gauge instruments, comfort ranking + map, animated
  play-button scatter, gradient area trend, radar profiles, temperature heatmap,
  day-types, table. Reads **only from the mart models**. Defaults to the 5 major
  cities for a clean view; per-city charts adapt when more of the 58 are selected.
  - An alternate cinematic "Spain Climate Observatory" design is preserved at
    `streamlit_app/variants/observatory.py`.
- **Raw data**: 58-city CSVs committed at `data/raw/open_meteo/` (the DuckDB file
  is git-ignored). `spain_cities.csv` drives extraction.
- **Quality**: GitHub Actions CI (`.github/workflows/ci.yml`: pytest + dbt build +
  advisory lint), `.pre-commit-config.yaml`, `tests_python/test_extract.py` (5 tests).

## 3. How to verify (copy-paste, from repo root)

The committed CSVs let you skip extraction.

```bash
pip install -e .                      # deps (Python 3.10–3.12 for dbt-core)
python scripts/load_to_duckdb.py      # expect: raw_locations 58 rows ... Done!
export DBT_PROFILES_DIR="$PWD"        # profiles.yml is in repo root
dbt deps && dbt build                 # EXPECT: 12 models, 72 tests, 84/84 pass
pytest tests_python/ -v               # EXPECT: 5 passed
python -m streamlit run streamlit_app/app.py   # open http://localhost:8501
```

Data sanity check (after load + build):
```bash
python -c "import duckdb; c=duckdb.connect('data/weather_analytics.duckdb', read_only=True); print(c.sql('select count(*) cities from main.mart_city_weather_summary').df()); print(c.sql('select city_name, overall_comfort_index from main.mart_city_weather_summary order by overall_comfort_index desc limit 5').df())"
# EXPECT: cities = 58; a ranked list of the most-comfortable cities.
```

## 4. Rubric coverage

| # | Criterion | Where |
|---|---|---|
| 1 | API extraction (4 endpoints) | `scripts/extract_open_meteo.py`; CSVs in `data/raw/open_meteo/` |
| 2 | Source definitions | `models/sources.yml` (4 sources) |
| 3 | Staging (rename/cast/snake_case, 4 models) | `models/staging/` |
| 4 | Intermediate (≥2) | `models/intermediate/` (3 models) |
| 5 | Fact + dim, clear grain, relationships | `models/marts/` (5 models) + FK tests |
| 6 | Tests + docs | `models/marts/docs/marts.yml` + `tests/`; 72 dbt tests pass |
| 7 | Dashboard (≥1 filter, ≥3 charts, reads marts) | `streamlit_app/app.py` |
| 8 | Reproducibility | `README.md`, `scripts/run_pipeline.sh`, committed CSVs |
| 9 | Organization / README | `README.md`, `docs/modeling_decisions.md` |

## 5. Known limitation (intentional, documented)

`fct_forecast_city_day` / `int_forecast_vs_actual` are correct and tested but can
return 0 rows in a single extraction: the Forecast API returns *future* dates
while the weather actuals are *past* days, so the join may not overlap. A real
forecast-vs-actual comparison needs forecast snapshots accumulated over time. It
is a *recommended* (bonus) model, not a mandatory one. See `README.md` and
`docs/modeling_decisions.md`.

## 6. Toolchain quirks (so verification doesn't trip)

- **Two dbt flavors work**: the dev machine has **dbt-fusion 2.0** (requires generic
  test args nested under `arguments:` — already done in `marts.yml`). Stock
  **dbt-core ≥1.10** also parses `arguments:` (verified, 84/84). dbt-core ≤1.9 will NOT.
- **`profiles.yml` is in the repo root** → set `DBT_PROFILES_DIR=$PWD` or `--profiles-dir .`.
- **DuckDB single-writer lock**: stop any Streamlit/Python holding
  `data/weather_analytics.duckdb` before `dbt build`.
- **Run Streamlit via `python -m streamlit`** if a bare `streamlit` launcher resolves
  to an interpreter without `duckdb`.
- CI's `dbt build` job uses dbt-core via `pip install -e .` (verified locally). Lint
  job is advisory (`continue-on-error`).

## 7. Open items / next steps

- [ ] Get the PR reviewed + approved (protected `main`).
- [ ] Confirm GitHub Actions is green on first run (Actions couldn't be run locally;
      equivalent steps verified with dbt-core 1.11).
- [ ] Optional: deploy to Streamlit Community Cloud and paste the URL in `README.md`.
- [ ] Optional: capture live forecast-vs-actual data over multiple days.
- [ ] Optional: decide whether to keep both dashboard designs or drop
      `streamlit_app/variants/observatory.py`.
