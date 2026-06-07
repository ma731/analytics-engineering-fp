with weather as (

    select * from {{ ref('int_city_day_weather') }}

),

final as (

    select
        city_day_weather_sk as city_weather_day_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        weather_date,
        temperature_2m_max,
        temperature_2m_min,
        temperature_2m_mean,
        temp_range_c,
        precipitation_sum,
        rain_sum,
        snowfall_sum,
        wind_speed_10m_max,
        is_rainy,
        is_windy,
        is_hot,
        is_freezing,
        (
            temperature_2m_mean between 18.0 and 26.0
            and not is_rainy
            and not is_windy
            and not is_hot
            and not is_freezing
        ) as is_comfortable

    from weather

)

select * from final
