with hourly as (

    select * from {{ ref('stg_air_quality_hourly') }}

),

daily_aggregated as (

    select
        location_id,
        city_name,
        country_code,
        cast(reading_timestamp as date) as air_quality_date,
        avg(pm10) as avg_pm10,
        max(pm10) as max_pm10,
        percentile_cont(0.95) within group (order by pm10) as p95_pm10,
        avg(pm2_5) as avg_pm2_5,
        max(pm2_5) as max_pm2_5,
        percentile_cont(0.95) within group (order by pm2_5) as p95_pm2_5,
        avg(carbon_monoxide) as avg_carbon_monoxide,
        max(carbon_monoxide) as max_carbon_monoxide,
        avg(nitrogen_dioxide) as avg_nitrogen_dioxide,
        max(nitrogen_dioxide) as max_nitrogen_dioxide,
        avg(ozone) as avg_ozone,
        max(ozone) as max_ozone,
        avg(european_aqi) as avg_european_aqi,
        max(european_aqi) as max_european_aqi,
        percentile_cont(0.95) within group (order by european_aqi) as p95_european_aqi,
        count(*) as hourly_readings_count,
        {{ dbt_utils.generate_surrogate_key(['location_id', 'cast(reading_timestamp as date)']) }} as air_quality_daily_sk

    from hourly
    where pm10 is not null
       or pm2_5 is not null
       or european_aqi is not null
    group by
        location_id,
        city_name,
        country_code,
        cast(reading_timestamp as date)

)

select * from daily_aggregated
