{{ config(
    materialized='incremental',
    unique_key='date'
) }}

{# 
    Pass the coin name as a variable (default: "bitcoin") and the fields to extract as a dictionary.
    You can override these via the command line or your dbt_project.yml.
#}
{% set coin = var('coin', '{{COIN}}') %}
{% set source_table = coin_history_table(coin) %}

{% set extraction_fields = var('extraction_fields', {
    "current_price_usd": "try_cast(json_extract(market_data, '$.current_price.usd') as DOUBLE)",
    "market_cap_usd": "try_cast(json_extract(market_data, '$.market_cap.usd') as DOUBLE)",
    "forks": "try_cast(json_extract(developer_data, '$.forks') as INTEGER)",
    "stars": "try_cast(json_extract(developer_data, '$.stars') as INTEGER)",
    "alexa_rank": "try_cast(json_extract(public_interest_stats, '$.alexa_rank') as INTEGER)"
}) %}

with source_data as (
    select
        date,
        id,
        symbol,
        name,
        market_data,
        developer_data,
        public_interest_stats
    from {{ source_table }}
)

select
    date,
    id,
    symbol,
    name,
    {{ coin_history_fields(extraction_fields) }}
from source_data
{% if is_incremental() %}
    where date > (select max(date) from {{ this }})
{% endif %}
