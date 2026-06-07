-- Air quality concentrations and indices can never be negative.
-- This test fails if any aggregated pollutant or AQI value is below zero.

select
    location_id,
    air_quality_date,
    avg_pm10,
    avg_pm2_5,
    avg_carbon_monoxide,
    avg_nitrogen_dioxide,
    avg_ozone,
    avg_european_aqi

from {{ ref('fct_air_quality_city_day') }}

where avg_pm10 < 0
   or avg_pm2_5 < 0
   or avg_carbon_monoxide < 0
   or avg_nitrogen_dioxide < 0
   or avg_ozone < 0
   or avg_european_aqi < 0
