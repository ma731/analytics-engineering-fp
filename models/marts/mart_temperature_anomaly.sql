-- Daily temperature anomaly, grain: one row per city per day.
-- Each day's mean temperature is compared against that city's average for the
-- same meteorological season, using window functions. anomaly_z expresses the
-- deviation in standard deviations (a "how unusual was this day" score).
-- is_extreme_day flags days at or beyond the extreme_anomaly_stddev var
-- (default 2 standard deviations) instead of a hardcoded degree threshold,
-- so the cutoff is statistically grounded and reproducible across cities/seasons.

with daily as (

    select
        location_id,
        city_name,
        country_code,
        weather_date,
        season,
        temperature_2m_mean
    from {{ ref('fct_city_weather_day') }}

),

stats as (

    select
        *,
        avg(temperature_2m_mean) over (partition by location_id, season) as season_mean,
        stddev_samp(temperature_2m_mean) over (partition by location_id, season) as season_sd
    from daily

)

select
    {{ dbt_utils.generate_surrogate_key(['location_id', 'weather_date']) }} as anomaly_sk,
    {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
    location_id,
    city_name,
    country_code,
    weather_date,
    season,
    temperature_2m_mean,
    round(season_mean, 1) as season_mean_c,
    round(temperature_2m_mean - season_mean, 1) as anomaly_c,
    round((temperature_2m_mean - season_mean) / nullif(season_sd, 0), 2) as anomaly_z,
    abs(temperature_2m_mean - season_mean) / nullif(season_sd, 0)
        >= {{ var('extreme_anomaly_stddev', 2) }} as is_extreme_day

from stats
