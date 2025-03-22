import duckdb

def greatest_custom(*args):
    """
    Accepts a variable number of tuple arguments, where each argument is (coin, value).
    Returns the coin name corresponding to the maximum numeric value.
    """
    max_val = None
    max_coin = None
    for coin, val in args:
        if max_val is None or val > max_val:
            max_val = val
            max_coin = coin
    return max_coin

# Connect to a DuckDB file
con = duckdb.connect('/Users/jbonilla/Documents/Development/token_analizer/meltano/token_importer/output/warehouse.duckdb')

# Register the function as a scalar UDF with an explicit return type
con.create_function("greatest_custom", greatest_custom, return_type="VARCHAR")

# Now you can use your UDF in queries:
result = con.execute("SELECT greatest_custom(('coin_a', 1), ('coin_b', 2))").fetchall()
print(result)
