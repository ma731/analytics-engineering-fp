{#
    Classify a date into its meteorological season (Northern Hemisphere).
    Meteorological seasons group whole months, which is the convention used
    for climate/weather aggregation: Winter = Dec-Feb, Spring = Mar-May,
    Summer = Jun-Aug, Autumn = Sep-Nov.
#}
{% macro season_from_date(date_column) %}
    case
        when extract(month from {{ date_column }}) in (12, 1, 2) then 'Winter'
        when extract(month from {{ date_column }}) in (3, 4, 5) then 'Spring'
        when extract(month from {{ date_column }}) in (6, 7, 8) then 'Summer'
        else 'Autumn'
    end
{% endmacro %}
