# Coin Data Pipeline

## Overview

This project is designed to fetch historical cryptocurrency data from CoinGecko, store it in a DuckDB database, and generate data models and metrics using dbt (Data Build Tool). It supports multiple cryptocurrencies and utilizes a virtual environment to manage dependencies.

## Prerequisites

Before setting up the project, ensure you have the following installed on your system:

- Python 3.x
- Make
- Virtualenv (optional but recommended)
- DuckDB
- dbt

## Setup Instructions

1. **Clone the Repository:**

   Clone this repository to your local machine.

   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```

2. **Environment Variables:**

   Create a `.env` file in the root directory to store your API key:

   ```plaintext
   COINGECKO_API_KEY=your_actual_api_key_here
   ```

3. **Install Dependencies:**

   install the required Python packages in the `requirements.txt` using the `Makefile`:

   ```bash
   make install-requirements
   ```

## Available Makefile Commands

The Makefile defines several targets that automate different aspects of the project:

### 1. Setup Environment

Initial setup and installation of Python dependencies:

```bash
make setup-env
```

### 2. Download Data

Fetch historical data for the specified cryptocurrencies, defaulting to "bitcoin" if no other coins are specified:

```bash
make download
```

To specify different coins, set the `COINS` environment variable:

```bash
COINS=bitcoin,ethereum make download
```

### 3. Generate Models and Semantics

- Generate per-coin denormalized model files:

  ```bash
  make generate-denorm
  ```

- Generate a master denormalized model for all coins:

  ```bash
  make generate-denorm-all-coins
  ```

- Generate semantic YAML files for specified coins:

  ```bash
  make generate-semantics
  ```

- Generate all coins metrics YAML file:

  ```bash
  make generate-all-coins-metrics
  ```

### 4. Build and Run dbt Models

Execute dbt to process the generated SQL models and create updated tables in your DuckDB data warehouse:

```bash
make dbt-run
```

Generate dbt documentation:

```bash
make dbt-docs
```

### 5. Complete Process

Run all the tasks to update everything from downloading the data to generating dbt documentation:

```bash
make all
```

## Contribution

Feel free to contribute to this project by submitting issues or pull requests. Follow the existing code style and ensure tests pass before submitting.


## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.