{% macro get_all_coin_metric_list(metric_suffix) -%}
  {%- set coin_names = [] -%}
  {%- for node in graph.nodes.values() if node.resource_type == 'model' and node.alias.startswith('denorm_') and node.alias.endswith('_history') -%}
    {%- set coin_name = node.alias | replace("denorm_", "") | replace("_history", "") | trim -%}
    {%- if coin_name not in coin_names -%}
      {%- do coin_names.append(coin_name) -%}
    {%- endif -%}
  {%- endfor -%}
  {%- set metric_names = [] -%}
  {%- for coin in coin_names -%}
    {%- set metric = coin ~ metric_suffix -%}
    {%- do metric_names.append('"' ~ metric ~ '"') -%}
  {%- endfor -%}
  {{ metric_names | join(', ') | trim }}
{%- endmacro %}

