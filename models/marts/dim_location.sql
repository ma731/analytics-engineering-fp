-- =============================================================================
-- dim_location
-- Dimension table for city/location attributes.
-- Grain: one row per unique location (city).
-- Used as the primary lookup for location metadata across all fact and mart
-- models via location_sk joins.
-- =============================================================================

with locations as (

    -- Pull all staged location records from the staging layer
    
    select * from {{ ref('stg_locations') }}

),

final as (

    select
        location_sk, -- Surrogate key (hashed, used for joins)
        location_id, -- Natural/source key for the location
        city_name,
        country,
        country_code,
        admin1, -- First-level administrative division (e.g. state/province)
        latitude,
        longitude,
        timezone,
        elevation,
        population

    from locations

)

select * from final
