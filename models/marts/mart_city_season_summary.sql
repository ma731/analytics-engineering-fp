with weather as (

    select * from {{ ref('fct_city_weather_day') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['location_id', 'season']) }} as city_season_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        season,
        count(*) as total_days,
        round(avg(temperature_2m_mean), 1) as avg_temperature_c,
        round(avg(temperature_2m_max), 1) as avg_max_temperature_c,
        round(avg(temperature_2m_min), 1) as avg_min_temperature_c,
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
    group by location_id, city_name, country_code, season

)

select * from final
