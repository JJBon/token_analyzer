# custom_udf_module.py

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
