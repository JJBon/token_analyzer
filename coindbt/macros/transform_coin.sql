{% macro transform_coin(coin_name) %}
  WITH raw AS (
      SELECT *
      FROM {{ source("warehouse_" ~ coin_name, "market_chart") }}
  ),
  with_indexes AS (
      SELECT
          raw.*,
          range(CAST(0 AS BIGINT), CAST(json_array_length(prices) - 1 AS BIGINT)) AS idx_array
      FROM raw
  ),
  transformed AS (
      SELECT
          timestamp 'epoch'
            + ((json_extract(prices, '$[' || t.idx || '][0]')::BIGINT / 1000)::BIGINT * interval '1 second') AS date,
          json_extract(prices, '$[' || t.idx || '][1]')::DOUBLE AS price,
          json_extract(market_caps, '$[' || t.idx || '][1]')::DOUBLE AS market_cap,
          json_extract(total_volumes, '$[' || t.idx || '][1]')::DOUBLE AS total_volume
      FROM with_indexes
      CROSS JOIN UNNEST(idx_array) AS t(idx)
  ),
  dedup AS (
      SELECT
          date,
          first_value(price) OVER (PARTITION BY date ORDER BY date) AS price,
          first_value(market_cap) OVER (PARTITION BY date ORDER BY date) AS market_cap,
          first_value(total_volume) OVER (PARTITION BY date ORDER BY date) AS total_volume,
          row_number() OVER (PARTITION BY date ORDER BY date) AS rn
      FROM transformed
  )
  SELECT date, price, market_cap, total_volume
  FROM dedup
  WHERE rn = 1
{% endmacro %}
