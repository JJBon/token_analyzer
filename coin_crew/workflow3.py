from crewai import Crew, Task
from agents import bi_agent
from crewai.tools import BaseTool
import json

# ---------------- Mock Tools ---------------- #
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
from typing import List, Dict, Optional
from typing import Type
from dotenv import load_dotenv




gen_task = ("Use the `CreateQueryTool` to generate a query using the metrics "
        "`coin_with_max_market_cap_volatility` and `max_market_cap_volatility_all_coins`, "
        "grouped by `metric_time__month`. Then, use the `FetchQueryResultTool` to retrieve results. "
        "Analyze the results and identify the coin with the highest volatility for any given month. "
        "Return that coin, the month, and the volatility value in your final answer.")

task = Task(
    description=gen_task,
    expected_output="Do trend analisis for the volatilities on the last 10 months"
        "Explain what this might mean for a potential investor.",
    agent=bi_agent
)

crew = Crew(
    agents=[bi_agent],
    tasks=[task],
    verbose=True
)


# ---------------- Run the Crew ---------------- #

if __name__ == "__main__":
    result = crew.kickoff()
    print("\n\n=== Final Output ===\n", result)
