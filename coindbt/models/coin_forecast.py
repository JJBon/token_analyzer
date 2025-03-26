# models/coin_forecast.py

import pandas as pd
import numpy as np
from datetime import timedelta
from statsmodels.tsa.stattools import adfuller
import pmdarima as pm

def model(dbt, session):
    """
    A dbt Python model (DuckDB) that:
      1) Reads daily price data for ONE coin from a DuckDB table
      2) Performs an ADF stationarity test
      3) Trains an ARIMA model (auto_arima)
      4) Forecasts next 7, 30, and 90 days
      5) Returns a final DataFrame that dbt will store as a table in DuckDB
    """

    # ------------------------------------------------------------------------------
    # 1) Read daily data for a single coin (e.g., 'Bitcoin')
    #    Replace 'my_coin_data' with your actual table or ref(...)
    #    Ensure it's sorted by date
    # ------------------------------------------------------------------------------
    coin_symbol = 'Bitcoin'
    query = f"""
        SELECT date, price
        FROM dbt.denorm_all_coins_2
        WHERE token = 'bitcoin'
        ORDER BY date
    """
    df = session.execute(query).df()  # returns a Pandas DF

    # If needed, drop rows with nulls, rename columns for convenience
    df = df.dropna(subset=['price']).rename(columns={'date': 'ds', 'price': 'y'})

    # ------------------------------------------------------------------------------
    # 2) Check stationarity with ADF test
    #    We'll store the p-value & conclusion to log or put in final output
    # ------------------------------------------------------------------------------
    adf_result = adfuller(df['y'], autolag='AIC')
    adf_stat = adf_result[0]
    p_value = adf_result[1]
    # Quick conclusion: if p_value < 0.05, we consider it stationary
    stationarity = 'Stationary' if p_value < 0.05 else 'Not Stationary'

    # ------------------------------------------------------------------------------
    # 3) Train an ARIMA model using pmdarima.auto_arima
    #    (If the series is non-stationary, auto_arima will difference it as needed)
    # ------------------------------------------------------------------------------
    # We only pass the 'y' column. We're ignoring exogenous variables for simplicity.
    model = pm.auto_arima(
        df['y'], 
        seasonal=False,      # no seasonal factor for daily data here
        trace=False,         # set to True to see model selection logs
        error_action='ignore',
        suppress_warnings=True
    )

    # ------------------------------------------------------------------------------
    # 4) Forecast for next 7 days, 30 days, and 90 days
    #    We'll do them separately for demonstration, each time from the same model.
    # ------------------------------------------------------------------------------
    forecast_horizons = {
        '7d': 7,
        '30d': 30,
        '90d': 90
    }

    # We'll store them all in a single DataFrame with a 'forecast_horizon' column
    all_forecasts = []

    # The last date in our historical data
    last_date = df['ds'].iloc[-1]

    for horizon_label, n_periods in forecast_horizons.items():
        fc = model.predict(n_periods=n_periods)
        # fc is a numpy array of forecasted values

        # Create a date range for these forecast periods
        future_dates = pd.date_range(start=last_date + timedelta(days=1),
                                     periods=n_periods, freq='D')

        fc_df = pd.DataFrame({
            'ds': future_dates,
            'yhat': fc,
            'forecast_horizon': horizon_label
        })
        all_forecasts.append(fc_df)

    forecast_df = pd.concat(all_forecasts, ignore_index=True)

    # ------------------------------------------------------------------------------
    # 5) Optionally include the ADF results. 
    #    We can unify them into the forecast or create a separate table.
    #    Below, we just add them as columns to each row for demonstration.
    # ------------------------------------------------------------------------------
    forecast_df['coin'] = coin_symbol
    forecast_df['adf_stat'] = adf_stat
    forecast_df['p_value'] = p_value
    forecast_df['stationarity'] = stationarity

    # Final shape: [ds, yhat, forecast_horizon, coin, adf_stat, p_value, stationarity]
    # Return this DataFrame to dbt so it can be materialized in DuckDB
    return forecast_df
