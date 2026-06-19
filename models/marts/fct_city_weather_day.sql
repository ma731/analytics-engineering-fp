-- =============================================================================
-- fct_city_weather_day
-- Fact table for daily weather observations per city.
-- Grain: one row per city per day.
-- Adds derived boolean flags and a comfort indicator on top of the intermediate
-- weather aggregates. These flags power downstream mart aggregations and filters.
-- =============================================================================
 
with weather as (
 
    -- Daily weather aggregates (min/max/mean temperature, precipitation,
    -- wind speed, and pre-computed condition flags) from the intermediate layer
    select * from {{ ref('int_city_day_weather') }}
 
),
 
final as (
 
    select
        city_day_weather_sk as city_weather_day_sk,
        -- Derive location_sk from location_id to enable joins with dim_location
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        weather_date,
        -- Meteorological season derived via macro: Winter/Spring/Summer/Autumn
        -- (Dec-Feb/Mar-May/Jun-Aug/Sep-Nov), used for seasonal groupings in
        -- mart and anomaly models
        {{ season_from_date('weather_date') }} as season,
 
        -- Temperature metrics (Celsius)
        temperature_2m_max,
        temperature_2m_min,
        temperature_2m_mean,
        temp_range_c,         -- Daily swing: max - min
 
        -- Precipitation metrics (mm)
        precipitation_sum,
        rain_sum,
        snowfall_sum,
 
        wind_speed_10m_max,   -- Peak wind speed for the day, measured at 10m (km/h)
 
        -- Boolean condition flags (defined thresholds in intermediate model)
        is_rainy,
        is_windy,
        is_hot,
        is_freezing,
 
        -- Composite comfort flag: a day is comfortable when it is mild
        -- (mean temp 18–26 °C) and none of the adverse conditions apply.
        -- Used to compute comfort_score and overall_comfort_index in marts.
        (
            temperature_2m_mean between 18.0 and 26.0
            and not is_rainy
            and not is_windy
            and not is_hot
            and not is_freezing
        ) as is_comfortable
 
    from weather
 
)
 
select * from final
