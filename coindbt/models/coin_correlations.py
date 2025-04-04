def model(dbt, session):
    """
    This Python model will:
    1) Load coin data from denorm_all_coins
    2) Only select columns named *_current_price_usd
    3) Compute correlation for:
       - overall (all rows)
       - yearly
       - quarterly
    4) Return a long-format correlation table with:
       coin1, coin2, correlation, time_period_type, time_period
    """
    import pandas as pd
    
    # 1) Load the table
    df = dbt.ref("denorm_all_coins").to_df()
    
    date_col = "date"
    # Convert to datetime if needed
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # 2) Identify only the columns that end with '_current_price_usd'
    price_cols = [
        c for c in df.columns 
        if c.endswith("_current_price_usd")
    ]

    # Build a numeric dataframe with only these price columns
    df_price_only = df[price_cols]

    # ----------------------------
    # A helper to convert a correlation matrix to long format
    # with additional fields
    # ----------------------------
    def corr_matrix_to_long(corr_matrix, time_period_type, time_period):
        corr_long = corr_matrix.reset_index().melt(
            id_vars='index',
            var_name='coin2',
            value_name='correlation'
        )
        corr_long.rename(columns={'index': 'coin1'}, inplace=True)
        corr_long["time_period_type"] = time_period_type
        corr_long["time_period"] = time_period
        return corr_long
    
    # ----------------------------
    # 3A) Overall correlation
    # ----------------------------
    overall_corr = df_price_only.corr()  # By default, Pearson correlation
    overall_long = corr_matrix_to_long(
        overall_corr,
        time_period_type="overall",
        time_period=None
    )

    # ----------------------------
    # 3B) Yearly correlation
    # ----------------------------
    # Extract year from date
    df["year"] = df[date_col].dt.year
    yearly_results = []

    for year_val, group_df in df.groupby("year"):
        # Build numeric subset for that year
        group_numeric = group_df[price_cols]
        corr_mat = group_numeric.corr()
        
        # Convert wide correlation matrix to long
        corr_long = corr_matrix_to_long(
            corr_mat,
            time_period_type="yearly",
            time_period=str(year_val)  # e.g. "2024"
        )
        yearly_results.append(corr_long)

    yearly_long = pd.concat(yearly_results, ignore_index=True) if yearly_results else pd.DataFrame()

    # ----------------------------
    # 3C) Quarterly correlation
    # ----------------------------
    # Make a "year-quarter" string, e.g. "2024Q1"
    df["quarter"] = df[date_col].dt.to_period("Q").astype(str)
    quarterly_results = []

    for q_val, group_df in df.groupby("quarter"):
        group_numeric = group_df[price_cols]
        corr_mat = group_numeric.corr()
        
        corr_long = corr_matrix_to_long(
            corr_mat,
            time_period_type="quarterly",
            time_period=q_val  # e.g. "2024Q1"
        )
        quarterly_results.append(corr_long)

    quarterly_long = pd.concat(quarterly_results, ignore_index=True) if quarterly_results else pd.DataFrame()

    # ----------------------------
    # 4) Combine all
    # ----------------------------
    corr_combined = pd.concat([overall_long, yearly_long, quarterly_long], ignore_index=True)

    # Return the final DataFrame
    return corr_combined
