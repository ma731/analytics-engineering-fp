with forecast as (

    select * from {{ ref('stg_forecast_daily') }}

),

actual as (

    select * from {{ ref('stg_weather_daily') }}

),

aligned as (

    select
        forecast.location_id,
        forecast.city_name,
        forecast.country_code,
        forecast.forecast_date,
        forecast.extracted_at as forecast_extracted_at,
        forecast.temperature_2m_max as forecast_temp_max,
        forecast.temperature_2m_min as forecast_temp_min,
        forecast.temperature_2m_mean as forecast_temp_mean,
        forecast.precipitation_sum as forecast_precipitation,
        forecast.wind_speed_10m_max as forecast_wind_speed_max,
        actual.temperature_2m_max as actual_temp_max,
        actual.temperature_2m_min as actual_temp_min,
        actual.temperature_2m_mean as actual_temp_mean,
        actual.precipitation_sum as actual_precipitation,
        actual.wind_speed_10m_max as actual_wind_speed_max,
        forecast.temperature_2m_max - actual.temperature_2m_max as temperature_max_error,
        forecast.temperature_2m_min - actual.temperature_2m_min as temperature_min_error,
        forecast.temperature_2m_mean - actual.temperature_2m_mean as temperature_mean_error,
        forecast.precipitation_sum - actual.precipitation_sum as precipitation_error,
        forecast.wind_speed_10m_max - actual.wind_speed_10m_max as wind_speed_error,
        abs(forecast.temperature_2m_mean - actual.temperature_2m_mean) as abs_temperature_error,
        abs(forecast.precipitation_sum - actual.precipitation_sum) as abs_precipitation_error,
        {{ dbt_utils.generate_surrogate_key(['forecast.location_id', 'forecast.forecast_date', 'forecast.extracted_at']) }} as forecast_vs_actual_sk

    from forecast
    inner join actual
        on forecast.location_id = actual.location_id
        and forecast.forecast_date = actual.weather_date

)

select * from aligned
