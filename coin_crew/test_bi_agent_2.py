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



class EmptyArgsSchema(BaseModel):
    pass


class FetchQueryResultToolSchema(BaseModel):
    query_id: str


class CreateQueryToolSchema(BaseModel):
    metric: str
    dimensions: List[str]
    filters: Optional[Dict[str, str]] = None


class MockFetchMetricsTool(BaseTool):
    name: str = "FetchMetrics"
    description: str = "Mock FetchMetrics tool"
    args_schema: Type[BaseModel] = EmptyArgsSchema  # ✅ Type annotation added

    def _run(self):
        print("[Mocked Tool] FetchMetrics called")
        return {"metrics": [{"name": "uniswap_price_volatility", "description": "Volatility for Uniswap prices", "dimensions": ["token", "date"]}]}


class MockCreateQueryTool(BaseTool):
    name: str = "CreateQuery"
    description: str = "Mock CreateQuery tool"
    args_schema: Type[BaseModel] = CreateQueryToolSchema  # ✅ Type annotation added

    def _run(self, metric: str, dimensions: List[str], filters: Optional[Dict[str, str]] = None):
        print("[Mocked Tool] CreateQuery called")
        return {"query_id": "1234-abcd"}


class MockFetchQueryResultTool(BaseTool):
    name: str = "FetchQueryResult"
    description: str = "Mock FetchQueryResult tool"
    args_schema: Type[BaseModel] = FetchQueryResultToolSchema  # ✅ Type annotation added

    def _run(self, query_id: str):
        print("[Mocked Tool] FetchQueryResult called with ID:", query_id)
        return '{"results": [{"token": "UNI", "volatility": 0.85}]}'

# ---------------- Setup Agent with Mocked Tools ---------------- #

# bi_agent.tools = [
#     MockFetchMetricsTool(),
#     MockCreateQueryTool(),
#     MockFetchQueryResultTool(),
# ]


# ---------------- Define Task and Crew ---------------- #

identify_coin_with_max_volatity = Task(
    description="Fetch metric that specifies which coin has the highest volatility",
    expected_output="Identify coin_with_max_price_volatility as the ideal metric to answer ",
    agent=bi_agent,
)

create_query= Task(
    description="Structure a query with the CreateQuery tool ",
    expected_output="Query should be valid",
    agent=bi_agent,
)

exececute_query = Task(
    description="Execute query with FetchQueryResultToo tool ",
    expected_output="Perform analisis based on query output",
    agent=bi_agent,
)

gen_task = ("Use the `CreateQueryTool` to generate a query using the metrics "
        "`coin_with_max_market_cap_volatility` and `max_market_cap_volatility_all_coins`, "
        "grouped by `metric_time__month`. Then, use the `FetchQueryResultTool` to retrieve results. "
        "Analyze the results and identify the coin with the highest volatility for any given month. "
        "Return that coin, the month, and the volatility value in your final answer.")

gen_task = ("Use the `FetchMetricsTool` to check available metrics "
        "Select metrics relevant to the user query"
        "Create query with relevant metrics"
        "Execute query"
        "Analyze the results and gather business insights")

task = Task(
    description=gen_task,
    expected_output="Do trend analisis for the volatilities in price and market caps of all coins on the last 10 months"
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
