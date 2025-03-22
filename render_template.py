import os
from jinja2 import Environment, FileSystemLoader

# Set up the template environment
env = Environment(loader=FileSystemLoader('templates'))

# Load the template
template = env.get_template('all_coins_metrics_template.yml')

# Variables
coin_list = ['coredao', 'bitcoin', 'sui', 'solayer', 'chainlink', 'uniswap', 'deep']

# Prepare the required values for the template
coin_array = ', '.join(coin_list)
coin_volatility_metrics = ', '.join([f"cast({coin}_price_volatility as DOUBLE)" for coin in coin_list])
coin_volatility_metrics_list = '\n'.join([f"- name: {coin}_price_volatility" for coin in coin_list])

# Context to inject into the template
context = {
    'COIN_ARRAY': coin_array,
    'COIN_VOLATILITY_METRICS': coin_volatility_metrics,
    'COIN_VOLATILITY_METRICS_LIST': coin_volatility_metrics_list
}

# Render the template with the context values
output = template.render(context)

# Output file
output_file = "generated_all_coins_metrics.yml"
with open(output_file, 'w') as f:
    f.write(output)

print(f"Template rendered and written to {output_file}")
