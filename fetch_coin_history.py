import os
import requests
import duckdb
import datetime
import time
import json
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the API key from the environment
API_KEY = os.getenv("COINGECKO_API_KEY")

# Parse command-line arguments.
parser = argparse.ArgumentParser(
    description="Fetch historical coin data from CoinGecko and store in DuckDB"
)
parser.add_argument(
    "--coins",
    type=str,
    default="bitcoin",
    help="Comma separated list of coin IDs (e.g. bitcoin,ethereum)"
)
args = parser.parse_args()

# Create a list of coin IDs stripping any extra whitespace.
coins = [coin.strip() for coin in args.coins.split(',') if coin.strip()]

# Define the period: one year from (today - 365 days) to today.
start_date = datetime.date.today() - datetime.timedelta(days=365)
end_date = datetime.date.today()

# Maximum number of retries for 429 responses.
max_retries = 5
retry_delay = 5  # seconds to wait between retries

# Construct the database path relative to the root of the project
db_path = os.path.join("coindbt", "warehouse.duckdb")

# Connect to (or create) the DuckDB database.
conn = duckdb.connect(db_path)

# Iterate over each coin.
for original_coin in coins:
    # Use the original name with hyphens for API and prepare a safe SQL identifier
    api_coin = original_coin
    sql_coin = original_coin.replace("-", "_")

    # Create (or update) the table to store historical data.
    conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {sql_coin}_history (
        date DATE,
        id TEXT,
        symbol TEXT,
        name TEXT,
        market_data TEXT,
        developer_data TEXT,
        public_interest_stats TEXT
    )
    """)
    print(f"Processing coin: {api_coin}")
    
    current_date = start_date
    while current_date <= end_date:
        # Check if data for this coin on this date already exists.
        existing = conn.execute(
            f"SELECT * FROM {sql_coin}_history WHERE date = ? AND id = ?",
            (current_date, original_coin)
        ).fetchone()
        
        # Determine if current_date is within one week from today.
        within_last_week = current_date >= (end_date - datetime.timedelta(days=1))
        
        if existing is not None:
            if within_last_week:
                print(f"Record for {api_coin} on {current_date} exists and is within last week, updating it...")
            else:
                print(f"Record for {api_coin} on {current_date} already exists, skipping API call.")
            current_date += datetime.timedelta(days=1)
            continue

        date_str = current_date.strftime("%d-%m-%Y")  # API requires dd-mm-yyyy format.
        headers = {
            "accept": "application/json",
            "x-cg-demo-api-key": API_KEY
        }
        
        url = f"https://api.coingecko.com/api/v3/coins/{api_coin}/history?date={date_str}"
        print(f"Fetching data for {api_coin} on {current_date}...")

        retry_count = 0
        while True:
            try:
                response = requests.get(url, headers=headers)
            except Exception as e:
                print(f"Exception on {api_coin} for {current_date}: {str(e)}")
                break

            if response.status_code == 200:
                data = response.json()
                # Extract basic coin data.
                coin_id = data.get("id")
                symbol = data.get("symbol")
                name = data.get("name")
                # Extract additional fields and convert to JSON string if available.
                market_data = data.get("market_data")
                developer_data = data.get("developer_data")
                public_interest_stats = data.get("public_interest_stats")
                market_data_str = json.dumps(market_data) if market_data else None
                developer_data_str = json.dumps(developer_data) if developer_data else None
                public_interest_stats_str = json.dumps(public_interest_stats) if public_interest_stats else None

                if existing is not None and within_last_week:
                    # Update the existing record.
                    conn.execute(
                        f"""
                        UPDATE {sql_coin}_history 
                        SET id = ?, symbol = ?, name = ?, market_data = ?, developer_data = ?, public_interest_stats = ?
                        WHERE date = ?
                        """,
                        (coin_id, symbol, name, market_data_str, developer_data_str, public_interest_stats_str, current_date)
                    )
                    print(f"Updated record for {api_coin} on {current_date}")
                else:
                    # Insert a new record.
                    conn.execute(
                        f"INSERT INTO {sql_coin}_history VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (current_date, coin_id, symbol, name, market_data_str, developer_data_str, public_interest_stats_str)
                    )
                    print(f"Inserted new record for {api_coin} on {current_date}")
                break  # exit retry loop on success
            elif response.status_code == 429:
                retry_count += 1
                if retry_count > max_retries:
                    print(f"Too many retries for {api_coin} on {current_date} (HTTP 429). Skipping this date.")
                    break
                print(f"HTTP 429 received for {api_coin} on {current_date}. Retrying in {retry_delay} seconds (retry {retry_count}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                print(f"Error fetching data for {api_coin} on {current_date}: HTTP {response.status_code}. Skipping this date.")
                break

        # Pause for a second to respect API rate limits.
        time.sleep(1)
        current_date += datetime.timedelta(days=1)

# Commit changes and close the connection.
conn.commit()
conn.close()

print("Data retrieval complete and stored in DuckDB database.")