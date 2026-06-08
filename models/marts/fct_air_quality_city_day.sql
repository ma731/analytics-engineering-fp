with air_quality as (

    select * from {{ ref('int_air_quality_daily') }}

),

final as (

    select
        air_quality_daily_sk as air_quality_city_day_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        air_quality_date,
        avg_pm10,
        max_pm10,
        p95_pm10,
        avg_pm2_5,
        max_pm2_5,
        p95_pm2_5,
        avg_carbon_monoxide,
        max_carbon_monoxide,
        avg_nitrogen_dioxide,
        max_nitrogen_dioxide,
        avg_ozone,
        max_ozone,
        avg_european_aqi,
        max_european_aqi,
        p95_european_aqi,
        hourly_readings_count

    from air_quality

)

select * from final
