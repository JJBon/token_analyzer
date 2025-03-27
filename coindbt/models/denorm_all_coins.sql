{{ config(
    materialized='table',
    unique_key='date'
) }}

{% set coin_list = var('coins', 'bitcoin,sui').split(',') %}

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

base as (
    select distinct date
    from {{ coin_list[0] }}
)

select
    base.date,
    {% for coin in coin_list %}
      {{ coin }}.{{ coin }}_current_price_usd,
      {{ coin }}.{{ coin }}_market_cap_usd{% if not loop.last %},{% endif %}
    {% endfor %}
from base
    {% for coin in coin_list %}
    left join {{ coin }} on base.date = {{ coin }}.date
    {% endfor %}
{% if is_incremental() %}
  where base.date > (select max(date) from {{ this }})
{% endif %}
