with source as (

    select * from {{ source('open_meteo', 'raw_air_quality_hourly') }}

),

renamed as (

    select
        cast(location_id as integer) as location_id,
        cast(city_name as varchar) as city_name,
        cast(country_code as varchar) as country_code,
        cast(timestamp as timestamp) as reading_timestamp,
        cast(latitude as double) as latitude,
        cast(longitude as double) as longitude,
        cast(timezone as varchar) as timezone,
        cast(pm10 as double) as pm10,
        cast(pm2_5 as double) as pm2_5,
        cast(carbon_monoxide as double) as carbon_monoxide,
        cast(nitrogen_dioxide as double) as nitrogen_dioxide,
        cast(ozone as double) as ozone,
        cast(european_aqi as double) as european_aqi,
        cast(extracted_at as timestamp) as extracted_at,
        {{ dbt_utils.generate_surrogate_key(['location_id', 'timestamp']) }} as air_quality_hourly_sk

    from source

)

select * from renamed
