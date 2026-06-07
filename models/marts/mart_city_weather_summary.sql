with weather as (

    select * from {{ ref('fct_city_weather_day') }}

),

air_quality as (

    select * from {{ ref('fct_air_quality_city_day') }}

),

locations as (

    select * from {{ ref('dim_location') }}

),

weather_summary as (

    select
        location_sk,
        location_id,
        count(*) as total_days,
        min(weather_date) as first_date,
        max(weather_date) as last_date,
        round(avg(temperature_2m_mean), 1) as avg_temperature_c,
        round(avg(temperature_2m_max), 1) as avg_max_temperature_c,
        round(avg(temperature_2m_min), 1) as avg_min_temperature_c,
        round(sum(precipitation_sum), 1) as total_precipitation_mm,
        count(*) filter (where is_comfortable) as comfortable_days,
        count(*) filter (where is_rainy) as rainy_days,
        count(*) filter (where is_windy) as windy_days,
        count(*) filter (where is_hot) as hot_days,
        count(*) filter (where is_freezing) as freezing_days

    from weather
    group by location_sk, location_id

),

air_quality_summary as (

    select
        location_sk,
        round(avg(avg_european_aqi), 1) as avg_air_quality_index,
        round(avg(avg_pm2_5), 1) as avg_pm2_5,
        round(max(max_european_aqi), 1) as worst_air_quality_index

    from air_quality
    group by location_sk

),

final as (

    select
        locations.location_sk,
        locations.location_id,
        locations.city_name,
        locations.country,
        locations.country_code,
        locations.latitude,
        locations.longitude,
        locations.population,
        weather_summary.total_days,
        weather_summary.first_date,
        weather_summary.last_date,
        weather_summary.avg_temperature_c,
        weather_summary.avg_max_temperature_c,
        weather_summary.avg_min_temperature_c,
        weather_summary.total_precipitation_mm,
        weather_summary.comfortable_days,
        weather_summary.rainy_days,
        weather_summary.windy_days,
        weather_summary.hot_days,
        weather_summary.freezing_days,
        air_quality_summary.avg_air_quality_index,
        air_quality_summary.avg_pm2_5,
        air_quality_summary.worst_air_quality_index,
        round(
            100.0 * weather_summary.comfortable_days
            / nullif(weather_summary.total_days, 0),
            1
        ) as comfort_score,
        round(
            (
                100.0 * weather_summary.comfortable_days
                / nullif(weather_summary.total_days, 0)
            )
            - coalesce(air_quality_summary.avg_air_quality_index, 0) * 0.5,
            1
        ) as overall_comfort_index

    from locations
    left join weather_summary
        on locations.location_sk = weather_summary.location_sk
    left join air_quality_summary
        on locations.location_sk = air_quality_summary.location_sk

)

select * from final
