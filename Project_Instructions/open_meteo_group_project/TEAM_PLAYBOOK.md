# Team Playbook — Open-Meteo Weather Analytics

A concrete, opinionated plan for executing the group assignment with a **4-person team** over ~3 weeks. This document covers roles, ownership boundaries, the engineering practices we want to demonstrate, and a sprint-by-sprint workflow.

We will use the **Open-Meteo** suggested topic. The starter extraction script is already provided; we extend it rather than rewrite it.

---

## 1. Team Composition

| # | Person | Claude Max? | Role |
|---|---|---|---|
| 1 | TBD | ✅ Yes | **Data Platform Lead** |
| 2 | TBD | ✅ Yes | **Analytics Modeling Lead** |
| 3 | TBD | ❌ No  | **Dimensional & Data Quality Lead** |
| 4 | TBD | ❌ No  | **Dashboard & Reproducibility Lead** |

**Why this split?** The two Claude Max seats own the most open-ended surfaces (extraction/infra and the staging/intermediate transformation graph) where rapid scaffolding and iterative SQL refactors pay off. The two non-Max seats own scopes with **clearer specifications and acceptance criteria** (mart grain, dashboard layout) — they can ship excellent work without needing autonomous agent loops.

> Everyone reviews everyone else's PRs. Roles are about *ownership*, not exclusivity.

---

## 2. Engineering Principles (the "MLOps-ish" bar we hold ourselves to)

These are non-negotiable for the final grade. Each is owned by a specific person below.

1. **Modularity** — extraction, loading, transformation, and presentation are separate modules. No SQL inside Python and no API calls inside dbt.
2. **Reproducibility** — anyone with a clean checkout runs 4 commands and gets a working dashboard.
3. **Idempotency** — re-running extraction or `dbt build` never breaks state. The pipeline is a function of inputs, not history.
4. **Tests at every layer**
   - Source freshness checks
   - Schema tests (`unique`, `not_null`, `relationships`, `accepted_values`)
   - Range/expectation tests via `dbt_expectations`
   - At least one **singular test** (custom SQL test)
   - Python `pytest` on the extraction module
5. **Documentation** — every model has a `description` and every primary/foreign key has a column-level doc. `dbt docs generate` runs clean.
6. **Environments** — `dev` and `prod` targets in `profiles.yml`. CI runs against `dev`.
7. **CI/CD** — GitHub Actions workflow runs `dbt build` + `sqlfluff lint` + `pytest` on every PR.
8. **Style/lint** — `sqlfluff` for SQL, `ruff` for Python. Pre-commit hook enforces both before commit.
9. **Versioning** — `uv.lock` is committed. `packages.yml` pins exact versions. No "latest".
10. **Branching** — `main` is protected. All work goes through feature branches and PRs with ≥1 reviewer.

---

## 3. Roles in Detail

### Role 1 — Data Platform Lead (Claude Max)

**Owns the inputs and the infrastructure.** This person makes sure data lands reliably and that everyone else's environment works.

**Deliverables**
- `scripts/extract_open_meteo.py` — extended from the starter to:
  - Split into modules: `geocode.py`, `weather.py`, `air_quality.py`, `io.py`
  - Add a `--snapshot-mode` flag that appends timestamped Parquet partitions (enables forecast-vs-actual analysis later)
  - Log to stderr in structured form (JSON lines)
  - Retry with exponential backoff on 5xx
- `scripts/load_to_duckdb.py` — reads `data/raw/open_meteo/*.csv` (or `*.parquet`) and registers them as DuckDB tables in a `raw` schema.
- `scripts/run_pipeline.sh` — one-liner that runs extract → load → `dbt build`.
- `pyproject.toml` + `uv.lock` — pinned dependencies. `dbt-duckdb`, `duckdb`, `streamlit`, `polars`, `dbt-expectations` (via `packages.yml`), `certifi`, `pytest`, `ruff`, `sqlfluff`.
- `.github/workflows/ci.yml` — runs on PR: install with `uv`, `dbt deps`, `sqlfluff lint`, `pytest`, `dbt build --target dev`.
- `.pre-commit-config.yaml` — `ruff`, `sqlfluff`, `end-of-file-fixer`, `trailing-whitespace`.
- `tests/test_extract.py` — `pytest` for the extraction module (mock the HTTP layer, test row-shaping functions).

**Acceptance criteria**
- A teammate on a clean machine can run `uv sync && bash scripts/run_pipeline.sh` and see a populated DuckDB.
- CI is green on `main`.
- The extraction module has ≥80% line coverage on pure functions (parsers, shape transforms).

---

### Role 2 — Analytics Modeling Lead (Claude Max)

**Owns the transformation graph from sources through intermediate.** This person decides the shape of every column the marts layer will consume.

**Deliverables**
- `models/sources.yml` — 4 source tables with `freshness` thresholds and descriptions.
- `models/staging/` — one `stg_*` view per source:
  - `stg_locations.sql`
  - `stg_weather_daily.sql`
  - `stg_forecast_daily.sql`
  - `stg_air_quality_hourly.sql`
  - Each renames to snake_case, casts types explicitly, adds a surrogate key via `dbt_utils.generate_surrogate_key`.
- `models/intermediate/` — at least 3 models that prepare facts:
  - `int_air_quality_daily.sql` — aggregate hourly → daily AQI (avg + max + p95)
  - `int_city_day_weather.sql` — join locations to weather, derive `is_rainy`, `is_windy`, `is_hot`, `temp_range_c`
  - `int_forecast_vs_actual.sql` — align `forecast_daily` snapshots with `weather_daily` actuals, compute `temperature_error`, `precipitation_error`
- `models/staging/docs/` + `models/intermediate/docs/` — YAML files with column-level descriptions and **generic tests on every primary key** (`unique`, `not_null`).
- `.sqlfluff` rules followed; no warnings.

**Acceptance criteria**
- `dbt build -s staging+ intermediate+` is green.
- Every staging model has at least one `not_null` test and one `unique` test on the surrogate key.
- All column casts are explicit (no implicit `::` chains).

---

### Role 3 — Dimensional & Data Quality Lead

**Owns the marts layer and the test suite.** This person defines what "correct" means.

**Deliverables**
- `models/marts/dim_location.sql` — one row per city, includes `city_name`, `country`, `latitude`, `longitude`, `timezone`, `population`, `elevation`. Surrogate `location_sk`.
- `models/marts/fct_city_weather_day.sql` — grain: **one row per `location_sk` per `weather_date`**. Carries daily metrics and `is_*` flags.
- `models/marts/fct_air_quality_city_day.sql` — grain: one row per `location_sk` per `air_quality_date`. Avg/max pollutant readings + dominant pollutant.
- `models/marts/fct_forecast_city_day.sql` — grain: one row per `location_sk` per `forecast_date` per `extracted_at` (snapshot). Errors against actuals where available.
- `models/marts/mart_city_weather_summary.sql` — denormalized wide table the dashboard reads from.
- `models/marts/docs/` — column-level docs **for every column** in dims/facts; relationships tests linking facts → `dim_location`.
- **Custom tests** (in `tests/`):
  - `assert_temperature_within_realistic_range.sql` — singular test, fails if `temperature_2m_max > 60` or `< -50`.
  - `assert_aqi_non_negative.sql` — singular test.
- **dbt_expectations** tests on key columns:
  - `expect_column_values_to_be_between` on temperature, precipitation, AQI
  - `expect_column_values_to_not_be_null` on grain keys
  - `expect_table_row_count_to_be_between` on `dim_location`

**Acceptance criteria**
- `dbt test` runs ≥25 tests, all passing.
- Every fact has a unique grain test (compound `unique` on the natural key combo).
- Every fact has a `relationships` test to `dim_location`.

---

### Role 4 — Dashboard & Reproducibility Lead

**Owns what the grader actually clicks on.** This person makes the project legible to an outsider.

**Deliverables**
- `streamlit_app/app.py` — reads **only from `mart_city_weather_summary`** (not raw, not staging). Includes:
  - Sidebar: city multi-select, date range, metric selector
  - KPIs row: avg temp, total precipitation, worst-AQI day, comfort score
  - Chart 1: line chart of daily temperature per city
  - Chart 2: bar chart of rainy/windy/hot day counts per city
  - Chart 3: forecast-vs-actual error scatter (when snapshot data exists)
  - Footer block: "Grain of `mart_city_weather_summary`: one row per city per date. Last refresh: {value from extracted_at}."
- `streamlit_app/components/` — reusable chart functions (don't put 600 lines in `app.py`).
- `README.md` (project root, not the assignment README) — answers these in order:
  1. How do I run the extraction?
  2. How do I load the data?
  3. How do I run dbt?
  4. How do I launch the dashboard?
  5. What final models power the dashboard?
  6. What modeling choices did we make and why?
- `docs/screenshots/` — at least 3 PNGs.
- `docs/modeling_decisions.md` — 1-2 page write-up of grain choices, why the mart is denormalized, why certain flags exist.
- **Deploy to Streamlit Community Cloud** + paste URL in the README.

**Acceptance criteria**
- The dashboard runs from a clean checkout with `streamlit run streamlit_app/app.py` after `dbt build`.
- All charts have axis labels and titles. No raw column names visible to the user.
- The README walks a first-time reader from zero to dashboard in <10 minutes.

---

## 4. Project Structure

```text
weather-analytics/                  ← group's GitHub repo
├── .github/
│   └── workflows/
│       └── ci.yml                   ← Role 1
├── .pre-commit-config.yaml          ← Role 1
├── .sqlfluff                        ← Role 2
├── scripts/
│   ├── extract_open_meteo.py        ← Role 1 (extends starter)
│   ├── load_to_duckdb.py            ← Role 1
│   └── run_pipeline.sh              ← Role 1
├── data/
│   └── raw/open_meteo/              ← extraction output (gitignored except .gitkeep)
├── models/
│   ├── sources.yml                  ← Role 2
│   ├── staging/                     ← Role 2
│   ├── intermediate/                ← Role 2
│   └── marts/                       ← Role 3
├── tests/                           ← Role 3 (singular tests)
├── streamlit_app/
│   ├── app.py                       ← Role 4
│   └── components/                  ← Role 4
├── tests_python/
│   └── test_extract.py              ← Role 1
├── docs/
│   ├── screenshots/                 ← Role 4
│   └── modeling_decisions.md        ← Role 4 (with input from Role 3)
├── dbt_project.yml
├── packages.yml
├── profiles.yml
├── pyproject.toml
├── uv.lock
└── README.md                        ← Role 4
```

---

## 5. Sprint Plan (3 weeks)

### Week 1 — Foundations
**Goal: data lands in DuckDB and the staging layer compiles.**

| Owner | Tasks |
|---|---|
| Role 1 | Repo scaffold, `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, CI workflow skeleton, extend extraction script with modular structure, `load_to_duckdb.py`. |
| Role 2 | `sources.yml`, all 4 staging models compiling with explicit casts, basic `unique`/`not_null` tests. |
| Role 3 | Draft `dim_location` (placeholder columns OK), agree on grain of each planned fact in `docs/modeling_decisions.md`. |
| Role 4 | Start the README skeleton, set up `streamlit_app/app.py` reading a hardcoded sample, get Streamlit Cloud account ready. |

**Week 1 demo:** `dbt run -s staging` works end-to-end on a clean machine.

---

### Week 2 — Marts, Tests, Dashboard skeleton
**Goal: the dashboard reads from real marts.**

| Owner | Tasks |
|---|---|
| Role 1 | `pytest` for extraction, CI runs `dbt build` on PR, snapshot-mode flag for forecast tracking, exponential-backoff retries. |
| Role 2 | All 3 intermediate models, docs YAML for staging + intermediate, sqlfluff clean. |
| Role 3 | All facts + `mart_city_weather_summary`, ≥25 tests including dbt_expectations, 2 singular tests. |
| Role 4 | Connect Streamlit to `mart_city_weather_summary`, ship the 3 required charts, sidebar filters working. |

**Week 2 demo:** `dbt build && streamlit run streamlit_app/app.py` produces a working dashboard locally.

---

### Week 3 — Polish, deploy, document
**Goal: a grader can clone and run in 10 minutes.**

| Owner | Tasks |
|---|---|
| Role 1 | Green CI on `main`, branch protection enabled, `run_pipeline.sh` works on Windows + macOS + Linux, retries verified. |
| Role 2 | `dbt docs generate` produces clean docs site, all column descriptions filled in. |
| Role 3 | Coverage check: every PK has a test, every FK has a `relationships` test, range tests in place. Final review of grain. |
| Role 4 | Streamlit deployed to Community Cloud, README complete, screenshots committed, `modeling_decisions.md` finalized, dry-run with a non-team-member who follows the README. |

**Week 3 demo:** Clean clone → 4 commands → live dashboard URL.

---

## 6. Workflow Rules

- **Branch naming**: `<role-number>-<short-description>` (e.g., `2-stg-air-quality`).
- **Commit style**: imperative present (`add stg_air_quality model`). Roles 1 and 2 may use Claude Code to draft commits but **must read the diff before pushing**.
- **PRs**: small (<400 lines if possible), with a description listing models touched and tests added.
- **Reviews**: at least one approval before merge. Roles 1 and 2 review each other; Roles 3 and 4 review each other; cross-reviews welcome.
- **Sync**: 30-minute standup twice a week (Mondays + Thursdays). Async updates in the team channel otherwise.
- **Blockers**: if blocked for >4 hours, post in the team channel. Don't burn a day stuck.

---

## 7. Definition of Done (final submission checklist)

Before submitting the GitHub URL:

- [ ] `uv sync && bash scripts/run_pipeline.sh` succeeds from a clean clone.
- [ ] `dbt build` runs all models + tests with zero failures.
- [ ] `pytest tests_python/` is green.
- [ ] `sqlfluff lint models/` returns no errors.
- [ ] CI is green on `main`.
- [ ] `dbt docs generate` produces a docs site without missing descriptions.
- [ ] Streamlit Cloud URL is live and the URL is in the root README.
- [ ] All 4 required charts/filters from the assignment README are present.
- [ ] `docs/modeling_decisions.md` explains grain and denormalization choices.
- [ ] At least 3 screenshots in `docs/screenshots/`.
- [ ] Every fact table has a unique-grain test and a relationships test to `dim_location`.
- [ ] No raw API files in git (they are reproducible via the script).
- [ ] `.env`-style secrets are not present (Open-Meteo doesn't need keys, so this should be trivially true).

---

## 8. How the Claude Max seats add leverage

For Roles 1 and 2, the high-leverage uses of Claude Max are:

- **Role 1**: scaffolding the CI workflow, drafting `pytest` fixtures that mock the HTTP layer, refactoring the extraction script into modules without breaking the CSV outputs.
- **Role 2**: generating staging model boilerplate from `sources.yml` with `codegen.generate_base_model`, then refactoring; bulk-writing docs YAML; iterating on intermediate model SQL with the schema in context.

For Roles 3 and 4, Claude (Free/Pro tier or Claude Code without Max) is still useful but in **shorter, well-scoped prompts**:

- **Role 3**: "given this fact grain, write the schema YAML with `relationships` tests" — predictable, one-shot.
- **Role 4**: "convert this DataFrame into a Streamlit bar chart with these labels" — predictable, one-shot.

The principle: Claude Max pays off when the work involves **multi-file refactors, iterative debugging, or building up a graph of related changes**. The other two roles have crisper specs and don't need that headroom.
