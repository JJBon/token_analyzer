{{ config(
    materialized='table'
) }}

{% set coin_list = var('coins', 'bitcoin,sui').split(',') %}

with coin_data as (

    {% for coin in coin_list %}
    select
        date,
        '{{ coin }}' as token,
        current_price_usd as price,
        market_cap_usd as market_cap
    from {{ ref('denorm_' ~ coin ~ '_history') }}

    {% if not loop.last %}
    union all
    {% endif %}

    {% endfor %}

)

select *
from coin_data
{% if is_incremental() %}
  where date > (select max(date) from {{ this }})
{% endif %}
