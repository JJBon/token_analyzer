{% macro coin_history_fields(fields) -%}
    {%- set field_expressions = [] -%}
    {%- for alias, expression in fields.items() -%}
        {%- set _ = field_expressions.append(expression ~ " as " ~ alias) -%}
    {%- endfor -%}
    {{ field_expressions | join(',\n    ') }}
{%- endmacro %}
