-- metricflow_time_spine.sql
with 
base_days as (
    {{ dbt_date.get_base_dates(n_dateparts=365*10, datepart="day") }}
),

future_days as (
    select 
        i::date as date_day
    from generate_series(
        (select max(date_day)::date from base_days) + interval '1 day',
        (select max(date_day)::date from base_days) + interval '30 day',
        interval '1 day'
    ) as t(i)
),

all_days as (
    select * from base_days
    union all
    select * from future_days
)

select 
    date_day,
    date_day as metric_time,
    date_trunc('quarter', date_day) as almost_fiscal_quarter
from all_days
