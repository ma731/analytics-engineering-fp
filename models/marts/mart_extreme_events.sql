with streaks as (

    select * from {{ ref('int_weather_extreme_streaks') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        count(*) as total_days,
        count(*) filter (where is_hot) as hot_days,
        count(*) filter (where in_heatwave) as heatwave_days,
        max(heat_streak) as longest_heatwave,
        count(*) filter (where is_freezing) as freezing_days,
        count(*) filter (where in_cold_snap) as cold_snap_days,
        max(cold_streak) as longest_cold_snap,
        count(*) filter (where is_heavy_rain) as heavy_rain_days,
        max(wet_streak) as longest_wet_spell

    from streaks
    group by location_id, city_name, country_code

)

select * from final
