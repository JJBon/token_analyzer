{% macro d_greatest_coin(metric_suffix) -%}
  {%- set coins_str = var('coins', 'coredao,bitcoin,sui,solayer,chainlink,uniswap,deep') -%}
  {%- set coins = coins_str.split(',') -%}
  {%- set coin_array = [] -%}
  {%- set expr_array = [] -%}
  {%- for coin in coins -%}
    {%- set coin_clean = coin | trim -%}
    {%- do coin_array.append("'" ~ coin_clean ~ "'") -%}
    {%- do expr_array.append("cast(" ~ coin_clean ~ metric_suffix ~ " as DOUBLE)") -%}
  {%- endfor -%}
  greatest_coin(
    ARRAY[{{ coin_array | join(', ') }}],
    ARRAY[{{ expr_array | join(', ') }}]
  )
{%- endmacro %}