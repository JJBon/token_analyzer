{{ config(
    materialized='incremental',
    unique_key='date'
) }}

{# 
  Split the comma‐separated coin list into an array.
  Adjust the default list as needed.
#}
{% set coin_list = var('coins', 'bitcoin,sui') | split(',') %}

{# 
  For each coin, we build a CTE that extracts:
    - date
    - coin price as <coin>_price
    - coin market cap as <coin>_market_cap
  These CTEs reference the corresponding coin_history table via dbt ref.
#}
with
{% for coin in coin_list %}
    {{ coin }} as (
        select
            date,
            try_cast(json_extract(market_data, '$.current_price.usd') as DOUBLE) as {{ coin }}_price,
            try_cast(json_extract(market_data, '$.market_cap.usd') as DOUBLE) as {{ coin }}_market_cap
        from {{ ref(coin ~ '_history') }}
    ){% if not loop.last %},{% endif %}
{% endfor %},

{# 
  Build a base time spine from the first coin's table.
  (You might also have a dedicated time spine model that covers all dates.)
#}
base as (
    select distinct date
    from {{ coin_list[0] }}
)

select
    base.date,
    {% for coin in coin_list %}
      {{ coin }}.{{ coin }}_price,
      {{ coin }}.{{ coin }}_market_cap{% if not loop.last %},{% endif %}
    {% endfor %}
from base
    {% for coin in coin_list %}
    left join {{ coin }} on base.date = {{ coin }}.date
    {% endfor %}
{% if is_incremental() %}
  where base.date > (select max(date) from {{ this }})
{% endif %}
