with source as (

    select * from {{ source('open_meteo', 'raw_locations') }}

),

renamed as (

    select
        cast(location_id as integer) as location_id,
        cast(city_name as varchar) as city_name,
        cast(country as varchar) as country,
        cast(country_code as varchar) as country_code,
        cast(admin1 as varchar) as admin1,
        cast(latitude as double) as latitude,
        cast(longitude as double) as longitude,
        cast(timezone as varchar) as timezone,
        cast(elevation as double) as elevation,
        cast(population as integer) as population,
        cast(extracted_at as timestamp) as extracted_at,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk

    from source

)

select * from renamed
