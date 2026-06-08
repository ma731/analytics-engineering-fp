-- Monthly comfort summary, grain: one row per city per calendar month.
-- The two partial Junes (2025 and 2026) collapse into one "typical June", so
-- the table holds up to 12 months per city — the basis for the best-month picker.

with weather as (

    select * from {{ ref('fct_city_weather_day') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['location_id', 'extract(month from weather_date)']) }}
            as city_month_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        cast(extract(month from weather_date) as integer) as month_num,
        strftime(weather_date, '%B') as month_name,
        season,
        count(*) as total_days,
        round(avg(temperature_2m_mean), 1) as avg_temperature_c,
        round(avg(temperature_2m_max), 1) as avg_max_temperature_c,
        round(sum(precipitation_sum), 1) as total_precipitation_mm,
        count(*) filter (where is_comfortable) as comfortable_days,
        count(*) filter (where is_rainy) as rainy_days,
        count(*) filter (where is_hot) as hot_days,
        count(*) filter (where is_freezing) as freezing_days,
        round(
            100.0 * count(*) filter (where is_comfortable) / nullif(count(*), 0),
            1
        ) as comfort_score

    from weather
    group by
        location_id,
        city_name,
        country_code,
        extract(month from weather_date),
        strftime(weather_date, '%B'),
        season

)

select * from final
