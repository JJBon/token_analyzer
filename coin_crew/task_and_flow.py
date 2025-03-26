# tasks_and_flow.py
from crewai import Task, Crew, Process
from agents import *

# Define tasks for each step of the pipeline
data_ingestion_task = Task(
    description="Fetch the latest crypto market data for the top coins and provide it in JSON format.",
    agent=data_engineer_agent,
    output_key="raw_data"  # label this output for downstream reference
)

dbt_model_task = Task(
    description=(
        "Using the raw crypto data provided above, generate a dbt model SQL. "
        "The model should be named 'crypto_top5' and include columns: coin_id, coin_name, current_price, market_cap, price_change_7d. "
        "If any data cleaning or type casting is needed, include it in the SQL. Provide the SQL as the output."
    ),
    agent=dbt_model_agent,
    output_key="dbt_sql"
)

semantic_def_task = Task(
    description=(
        "We have a new dbt model 'crypto_top5' with columns: coin_id, coin_name, current_price, market_cap, price_change_7d. "
        "Define a metric called 'coin_price_change_7d' in YAML format for the dbt semantic layer. "
        "The metric should represent the average 7-day price change, use 'crypto_top5' model, and have 'coin_name' as a dimension. "
        "Provide the YAML definition for the metric."
    ),
    agent=semantic_layer_agent,
    output_key="metric_yaml"
)

analysis_task = Task(
    description=(
        "We have defined a metric 'coin_price_change_7d'. Use the SemanticQuery tool to create a query for this metric, grouped by coin_name. "
        "After getting the results, analyze which coin has the highest 7-day price change percentage and explain whether it looks like a good investment. "
        "Finally, provide a recommendation on which coin to invest in, based on the metric."
    ),
    agent=bi_agent,
    output_key="recommendation"
)

# Create a Crew to run tasks sequentially
crypto_crew = Crew(
    agents=[data_engineer_agent, dbt_model_agent, semantic_layer_agent, bi_agent],
    tasks=[data_ingestion_task, dbt_model_task, semantic_def_task, analysis_task],
    process=Process.sequential  # ensure tasks run one after the other in order
)

# Run the crew workflow
result = crypto_crew.run()

# After execution, gather the outputs (for demonstration purposes)
raw_data = data_ingestion_task.output  # or result["raw_data"]
sql_model = dbt_model_task.output
metric_yaml = semantic_def_task.output
recommendation = analysis_task.output

print("Final Recommendation:\n", recommendation)
