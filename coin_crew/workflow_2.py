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


from mcpadapt.core import MCPAdapt
from mcpadapt.crewai_adapter import CrewAIAdapter
import os
import time
from mcp import StdioServerParameters

if __name__ == "__main__":
    with MCPAdapt(
        StdioServerParameters(
            command="uv",
            args = [
            "run",
            "--python",
            "/home/juanjbon/dev/token_analyzer/venv/bin/python",
            "/home/juanjbon/dev/token_analyzer/dbt_semantic_layer_mcp_server.py"
            ],
            env={**os.environ},
        ),
        CrewAIAdapter()
    ) as tools:

        bi_agent.tools = tools

        volatility_task = Task(
            description=(
            "Use only the `create_query` and `fetch_query_result` tools. "
            "Perform exactly one call to `create_query` with the following metrics and parameters:\n"
            "- metrics: [max_market_cap_volatility_all_coins, coin_with_max_market_cap_volatility, "
            "min_market_cap_volatility_all_coins, coin_with_min_market_cap_volatility, "
            "max_price_volatility_all_coins, coin_with_max_price_volatility, "
            "min_price_volatility_all_coins, coin_with_min_price_volatility]\n"
            "- groupBy: [metric_time__month]\n"
            "- limit: 10\n"
            "- orderBy: [-metric_time]\n\n"
            "Then, once you have created this query, call `fetch_query_result` with the same query object.\n\n"
            "If any tool call fails, respond with 'metrics not found for all questions'. "
            "After you receive the query results, analyze the returned data for trends and insights "
            "about coin market cap and price volatility, summarizing potential implications for investors."
        ),
            expected_output="Do trend analisis for the volatilities in price and market caps of all coins on the last 10 months"
                "Explain what this might mean for a potential investor.",
            agent=bi_agent
        )

        price_growth_task = Task(
            description=(
                "Use only the `create_query` and `fetch_query_result` tools. "
                "Perform exactly one call to `create_query` with the following metrics and parameters:\n"
                "- metrics: [coin_with_max_price_growth_rate, max_price_growth_rate, "
                "coin_with_min_price_growth_rate, min_price_growth_rate]\n"
                "- groupBy: [metric_time__week]\n"
                "- limit: 24\n"
                "- orderBy: [-metric_time]\n\n"
                "Then, once you have created this query, call `fetch_query_result` with the same query object.\n\n"
                "If any tool call fails, respond with 'metrics not found for all questions'. "
                "After you receive the query results, analyze the returned data for trends and insights "
                "about how coin price growth rates have changed over the last 24 weeks, "
                "summarizing potential implications for investors."
            ),
            expected_output=(
                "Perform a trend analysis of coin price growth rates over the last 24 weeks, "
                "highlighting which coins grew fastest or slowest. "
                "Offer insights on what this might mean for an investor's strategy."
            ),
            agent=bi_agent
        )

        crew = Crew(
            agents=[bi_agent],
            tasks=[volatility_task,price_growth_task],
            verbose=True
        )


# ---------------- Run the Crew ---------------- #
        result = crew.kickoff()
        print("\n\n=== Final Output ===\n", result)
