{{ config(materialized='view') }}

with base as (
    select
        date,
        current_price_usd,
        market_cap_usd
    from {{ ref('denorm_sui_history') }}
)

select YEAR(date) as analysis_date,
    count(*) as record_count,
    avg(current_price_usd) as avg_current_price_usd,
    variance(current_price_usd) as current_price_variance,
    avg(market_cap_usd) as avg_market_cap_usd,
    variance(market_cap_usd) as market_cap_variance
from base
group by YEAR(date)
order by YEAR(date)
