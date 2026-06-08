with air_quality as (

    select * from {{ ref('int_air_quality_daily') }}

),

bands as (

    select * from {{ ref('aqi_health_bands') }}

),

final as (

    select
        air_quality.air_quality_daily_sk as air_quality_city_day_sk,
        {{ dbt_utils.generate_surrogate_key(['air_quality.location_id']) }} as location_sk,
        air_quality.location_id,
        air_quality.city_name,
        air_quality.country_code,
        air_quality.air_quality_date,
        air_quality.avg_pm10,
        air_quality.max_pm10,
        air_quality.p95_pm10,
        air_quality.avg_pm2_5,
        air_quality.max_pm2_5,
        air_quality.p95_pm2_5,
        air_quality.avg_carbon_monoxide,
        air_quality.max_carbon_monoxide,
        air_quality.avg_nitrogen_dioxide,
        air_quality.max_nitrogen_dioxide,
        air_quality.avg_ozone,
        air_quality.max_ozone,
        air_quality.avg_european_aqi,
        air_quality.max_european_aqi,
        air_quality.p95_european_aqi,
        air_quality.hourly_readings_count,
        bands.aqi_band,
        bands.band_order as aqi_band_order

    from air_quality
    left join bands
        on air_quality.avg_european_aqi >= bands.aqi_min
        and air_quality.avg_european_aqi < bands.aqi_max

)

select * from final
