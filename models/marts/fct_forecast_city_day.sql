with forecast_vs_actual as (

    select * from {{ ref('int_forecast_vs_actual') }}

),

final as (

    select
        forecast_vs_actual_sk as forecast_city_day_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        forecast_date,
        forecast_extracted_at,
        forecast_temp_max,
        forecast_temp_min,
        forecast_temp_mean,
        forecast_precipitation,
        forecast_wind_speed_max,
        actual_temp_max,
        actual_temp_min,
        actual_temp_mean,
        actual_precipitation,
        actual_wind_speed_max,
        temperature_max_error,
        temperature_min_error,
        temperature_mean_error,
        precipitation_error,
        wind_speed_error,
        abs_temperature_error,
        abs_precipitation_error

    from forecast_vs_actual

)

select * from final
