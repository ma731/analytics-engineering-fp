with source as (

    select * from {{ source('open_meteo', 'raw_weather_daily') }}

),

renamed as (

    select
        cast(location_id as integer) as location_id,
        cast(city_name as varchar) as city_name,
        cast(country_code as varchar) as country_code,
        cast(date as date) as weather_date,
        cast(latitude as double) as latitude,
        cast(longitude as double) as longitude,
        cast(timezone as varchar) as timezone,
        cast(temperature_2m_max as double) as temperature_2m_max,
        cast(temperature_2m_min as double) as temperature_2m_min,
        cast(temperature_2m_mean as double) as temperature_2m_mean,
        cast(precipitation_sum as double) as precipitation_sum,
        cast(rain_sum as double) as rain_sum,
        cast(snowfall_sum as double) as snowfall_sum,
        cast(wind_speed_10m_max as double) as wind_speed_10m_max,
        cast(extracted_at as timestamp) as extracted_at,
        {{ dbt_utils.generate_surrogate_key(['location_id', 'date']) }} as weather_daily_sk

    from source

)

select * from renamed
