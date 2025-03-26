# agents.py (continued)
from crewai import Agent
from crewai.tools import BaseTool
import requests
from llm_config import openai_gpt4,  ollama_llama2, openai_gpt35
from typing import Dict, List, Optional
from pydantic import  BaseModel, PrivateAttr

# Define a custom tool for the Data Engineer to fetch data from CoinGecko API
class CoinGeckoAPITool(BaseTool):
    def __init__(self):
        super().__init__(name="CoinGeckoAPI", description="Fetch crypto market data from CoinGecko")
    def run(self, coin_ids=None):
        # Fetch top 5 coins data (or specific coin_ids if provided)
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 5,
            "page": 1,
            "price_change_percentage": "7d"
        }
        if coin_ids:
            params["ids"] = ",".join(coin_ids)
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data  # returns a Python list of coin data dicts

# Instantiate the Data Engineer Agent with an OpenAI GPT-4 model and the API tool
# data_engineer_agent = Agent(
#     role="Data Engineer",
#     goal="Gather cryptocurrency data from external sources and provide it for ingestion.",
#     backstory=("An expert data engineer who knows where to get the best crypto data. "
#                "Can fetch data via APIs or other sources as needed."),
#     llm=openai_gpt4,
#     tools=[CoinGeckoAPITool()]  # allow this agent to use the CoinGecko API tool
# )

# agents.py (continued)
dbt_model_agent = Agent(
    role="DBT Model Generator",
    goal="Transform raw crypto data into a refined table using dbt (generate SQL models).",
    backstory=("A data analyst proficient in dbt. Takes raw data and creates cleaned, structured models for analytics."),
    llm=ollama_llama2,
    tools=[]  # This agent doesn't need external tools, just uses the LLM for SQL generation
)

# agents.py (continued)
semantic_layer_agent = Agent(
    role="Semantic Layer Engineer",
    goal="Define metrics, dimensions, and entities for the dbt semantic layer based on the available data.",
    backstory=("An analytics engineer expert in MetricFlow and dbt metrics. Creates metric definitions so downstream tools can query them easily."),
    llm=openai_gpt4,  # Using Claude (Anthropic) via Bedrock
    tools=[]  # This agent might not need external tools; it generates config files.
)

# agents.py (continued)
class SemanticQueryTool(BaseTool):
    name: str = "SemanticQuery"
    description: str = (
        "Query the dbt semantic layer via MCP (create_query and fetch_result)."
    )

    # Mark these as private attributes so Pydantic doesn't complain
    _mcp_url: str = PrivateAttr()
    _headers: dict = PrivateAttr()

    def __init__(self, mcp_url: str):
        super().__init__()
        self._mcp_url = mcp_url
        self._headers = {"Content-Type": "application/json"}

    def _run(
        self,
        metric_name: str,                    # <--- typed
        dimensions: Optional[List[str]] = None,
        filters: Optional[List[str]] = None
    ):
        """
        CrewAI sees this signature and knows it needs:
        {
          "metric_name": string,
          "dimensions": array of strings,
          "filters": array of strings
        }
        """
        # 1) Build JSON-RPC payload
        params = {"metrics": [metric_name]}
        if dimensions:
            params["dimensions"] = dimensions
        if filters:
            params["filters"] = filters
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "create_query",
            "params": params
        }
        # 2) Create query
        res = requests.post(self._mcp_url, json=payload, headers=self._headers).json()
        query_id = res.get("result", {}).get("query_id")
        if not query_id:
            raise ValueError(f"Query creation failed: {res}")

        # 3) Poll fetch_query_result
        result = None
        fetch_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "fetch_query_result",
            "params": {"query_id": query_id}
        }
        for _ in range(10):
            result_res = requests.post(
                self._mcp_url, 
                json=fetch_payload, 
                headers=self._headers
            ).json()
            result = result_res.get("result", {})
            if result.get("status") == "SUCCESSFUL":
                break
        return result

    async def _arun(self, *args, **kwargs):
        """If CrewAI tries to call your tool in an async context, you need this too."""
        raise NotImplementedError("Async usage not implemented for SemanticQueryTool")

# Instantiate BI agent with the semantic query tool
MCP_SERVER_URL = "http://localhost:8000/mcp"  # Example URL for MCP server
bi_agent = Agent(
    role="Business Intelligence Analyst",
    goal="Analyze the metric data and recommend which coins to invest in.",
    backstory=("A data analyst who uses metrics to drive investment decisions. "
               "Can query the semantic layer for metrics and interpret the results."),
    llm=openai_gpt35,
    tools=[SemanticQueryTool(MCP_SERVER_URL)]
)

