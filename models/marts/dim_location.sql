with locations as (

    select * from {{ ref('stg_locations') }}

),

final as (

    select
        location_sk,
        location_id,
        city_name,
        country,
        country_code,
        admin1,
        latitude,
        longitude,
        timezone,
        elevation,
        population

    from locations

)

select * from final
