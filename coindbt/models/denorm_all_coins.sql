{{ config(
    materialized='incremental',
    unique_key='date'
) }}

{# 
  Split the comma‐separated coin list into an array.
  Adjust the default list as needed.
#}
{% set coin_list = var('coins', 'coredao,bitcoin,sui,solayer,chainlink,uniswap,deep,ripple,polkadot,mocaverse,bittorrent,stellar,ethereum,sushi,solana,dogecoin,cardano,litecoin').split(',') %}

{# 
  For each coin, we build a CTE that extracts:
    - date
    - coin price as <coin>_current_price_usd
    - coin market cap as <coin>_market_cap_usd
  These CTEs reference the corresponding coin_history table via dbt ref.
#}
with
{% for coin in coin_list %}
    {{ coin }} as (
        select
            date,
            current_price_usd as {{ coin }}_current_price_usd,
            market_cap_usd as {{ coin }}_market_cap_usd
        from {{ ref('denorm_' ~ coin ~ '_history') }}
    ){% if not loop.last %},{% endif %}
{% endfor %},

{# 
  Build a base time spine from the first coin's table.
  (You might also have a dedicated time spine model that covers all dates.)
#}
base as (
    select distinct date
    from {{ ref('denorm_' ~ coin_list[0] ~ '_history') }}
)

select
    base.date,
    {% for coin in coin_list %}
      {{ coin }}.{{ coin }}_current_price_usd as {{ coin }}_current_price_usd,
      {{ coin }}.{{ coin }}_market_cap_usd as {{ coin }}_market_cap_usd{% if not loop.last %},{% endif %}
    {% endfor %}
from base
    {% for coin in coin_list %}
    left join {{ coin }} on base.date = {{ coin }}.date
    {% endfor %}
{% if is_incremental() %}
  where base.date > (select max(date) from {{ this }})
{% endif %}
