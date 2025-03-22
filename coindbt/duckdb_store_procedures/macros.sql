CREATE MACRO greatest_coin(coin_names, volatilities) AS (
    WITH data AS (
         SELECT 
            coin_names[i] AS coin, 
            volatilities[i] AS vol
         FROM generate_series(1, array_length(coin_names)) AS t(i)
    )
    SELECT max_by(coin, vol) FROM data
);


CREATE MACRO least_coin(coin_names, volatilities) AS (
  WITH data AS (
    SELECT
      coin_names[i] AS coin,
      volatilities[i] AS vol
    FROM
      generate_series(1, array_length(coin_names)) AS t(i)
    WHERE
      volatilities[i] IS NOT NULL AND volatilities[i] != 0
  )
  SELECT
    CASE
      WHEN COUNT(*) > 0 THEN min_by(coin, vol)
      ELSE NULL  -- or another appropriate default value if no valid coin
    END
  FROM data
);

CREATE MACRO safe_division(numerator, denominator, default_value) AS (
  COALESCE(
    CASE 
      WHEN denominator = 0 OR numerator IS NULL OR denominator IS NULL THEN default_value
      ELSE numerator / denominator
    END,
  default_value)
);


CREATE MACRO nonzero_least(values) AS (
  WITH filtered_values AS (
    SELECT
      values[i] AS val
    FROM generate_series(1, array_length(values)) AS t(i)
    WHERE values[i] IS NOT NULL AND values[i] != 0
  )
  SELECT
    CASE
      WHEN COUNT(*) > 0 THEN MIN(val)
      ELSE 0
    END
  FROM filtered_values
);