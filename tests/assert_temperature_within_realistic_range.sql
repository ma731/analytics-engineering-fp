-- Daily temperatures should fall within a physically realistic range for our cities.
-- This test fails if any observed temperature is outside [-40C, 55C]
-- or if the daily minimum is greater than the daily maximum.

select
    location_id,
    weather_date,
    temperature_2m_min,
    temperature_2m_max,
    temperature_2m_mean

from {{ ref('fct_city_weather_day') }}

where temperature_2m_min < -40.0
   or temperature_2m_max > 55.0
   or temperature_2m_min > temperature_2m_max
