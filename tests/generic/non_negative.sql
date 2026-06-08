{#
    Custom generic (reusable) test: fails for any row where the column is
    negative. Reusable across models via `tests: [non_negative]` on a column,
    unlike the project's singular tests which target one model each.
#}
{% test non_negative(model, column_name) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} < 0

{% endtest %}
