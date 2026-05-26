with weather as (

    select * from {{ ref('stg_weather_daily') }}

),

locations as (

    select * from {{ ref('stg_locations') }}

),

joined as (

    select
        weather.location_id,
        locations.city_name,
        locations.country,
        locations.country_code,
        locations.latitude,
        locations.longitude,
        locations.timezone,
        locations.population,
        locations.elevation,
        weather.weather_date,
        weather.temperature_2m_max,
        weather.temperature_2m_min,
        weather.temperature_2m_mean,
        weather.precipitation_sum,
        weather.rain_sum,
        weather.snowfall_sum,
        weather.wind_speed_10m_max,
        weather.temperature_2m_max - weather.temperature_2m_min as temp_range_c,
        weather.rain_sum > 1.0 as is_rainy,
        weather.wind_speed_10m_max > 40.0 as is_windy,
        weather.temperature_2m_max > 35.0 as is_hot,
        weather.temperature_2m_min < 0.0 as is_freezing,
        weather.extracted_at,
        weather.weather_daily_sk as city_day_weather_sk

    from weather
    inner join locations
        on weather.location_id = locations.location_id

)

select * from joined
