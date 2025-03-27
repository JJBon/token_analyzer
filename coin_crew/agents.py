# agents.py (continued)
from crewai import Agent
from crewai.tools import BaseTool
import requests
from llm_config import openai_gpt4,  ollama_llama2, openai_gpt35, bedrock_llm
from typing import Dict, List, Optional
from pydantic import  BaseModel, PrivateAttr
import json
from typing import Type
from typing import Union


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


# ============================
# SCHEMAS
# ============================

class CreateQueryToolSchema(BaseModel):
    metrics: List[Dict[str, str]]  # each item => { "name": "some_metric" }
    groupBy: Optional[List[Dict[str, str]]] = None
    where: Optional[List[Dict[str, str]]] = None
    limit: Optional[int] = None
    orderBy: List[Dict[str, str]]= None

class FetchQueryResultToolSchema(BaseModel):
    query_id: str

# ============================
# TOOLS
# ============================
class FetchMetricsTool(BaseTool):
    name: str = "FetchMetrics"
    description: str = "Fetch a list of available metrics and their descriptions."

    def __init__(self, mcp_url: str):
        super().__init__()
        self._mcp_url = mcp_url
        self._headers = {"Content-Type": "application/json"}

    def _run(self):
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "fetch_metrics", "arguments": {}}
        }

        try:
            response = requests.post(self._mcp_url, json=payload, headers=self._headers)
            response.raise_for_status()
            result = response.json().get("result", {}).get("content", [{}])[0]
            text_content = result.get("text")

            if not text_content:
                return {"error": "'text' field missing in response content"}

            parsed = json.loads(text_content)
            return {"metrics": parsed.get("metrics", [])}

        except Exception as e:
            return {"error": f"[FetchMetricsTool] Error: {e}"}


class CreateQueryTool(BaseTool):
    name: str = "CreateQuery"
    description: str = "Create a query given metrics, groupBy, and filters."
    args_schema: Type[BaseModel] = CreateQueryToolSchema

    def __init__(self, mcp_url: str):
        super().__init__()
        self._mcp_url = mcp_url
        self._headers = {"Content-Type": "application/json"}

    def _run(
        self,
        metrics: List[Dict[str, str]],  # each item => { "name": "some_metric" }
        groupBy: Optional[List[Dict[str, str]]] = None,
        where: Optional[List[Dict[str, str]]] = None,
        limit: Optional[int] = None,
        orderBy: List[Dict[str, str]]= None
    ):
        # Normalize metrics to list of dicts
        formatted_metrics = [
            {"name": m} if isinstance(m, str) else m for m in metrics
        ]

        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "create_query",
                "arguments": {
                    "metrics": formatted_metrics,
                    "groupBy": groupBy or [],
                    "where": where or [],
                    "limit": limit,
                    "orderBy": orderBy or []
                }
            }
        }

        try:
            response = requests.post(self._mcp_url, json=payload, headers=self._headers)
            response.raise_for_status()
            content = response.json().get("result", {}).get("content", [{}])[0]
            if "text" in content:
                return json.loads(content["text"])
            return {"error": "[CreateQueryTool] Unexpected response format", "raw_response": content}
        except Exception as e:
            return {"error": f"[CreateQueryTool] Error: {e}"}
            

class FetchQueryResultTool(BaseTool):
    name: str = "FetchQueryResult"
    description: str = "Fetch the results of a query using a query ID."
    args_schema: Type[BaseModel] = FetchQueryResultToolSchema

    def __init__(self, mcp_url: str):
        super().__init__()
        self._mcp_url = mcp_url
        self._headers = {"Content-Type": "application/json"}

    def _run(self, query_id: str):
        payload = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "fetch_query_result",
                "arguments": {"queryId": query_id}
            }
        }

        try:
            response = requests.post(self._mcp_url, json=payload, headers=self._headers)
            response.raise_for_status()

            # Extract and decode the inner result
            raw_text = response.json().get("result", {}).get("content", [{}])[0].get("text", "")
            if not raw_text:
                return {"error": "[FetchQueryResultTool] No text field in response content"}

            parsed = json.loads(raw_text)
            return {
                "status": parsed.get("status"),
                "results": parsed.get("results", []),
                "error": parsed.get("error")
            }

        except Exception as e:
            return {"error": f"[FetchQueryResultTool] Error: {e}"}



# Instantiate BI agent with the semantic query tool
MCP_SERVER_URL = "http://localhost:8000/mcp"  # Example URL for MCP server
tools=[
        FetchMetricsTool(MCP_SERVER_URL),
        CreateQueryTool(MCP_SERVER_URL),
        FetchQueryResultTool(MCP_SERVER_URL),
    ]


bi_agent = Agent(
    role="Business Intelligence Analyst",
    goal=(
        "Analyze and interpret metric data for executive decision-making. "
        "Generate queries using the CreateQuery tool, and extract meaningful patterns from the result."
    ),
    llm=bedrock_llm,
    backstory=(
        "You are a data-savvy analyst with strong knowledge of the dbt Semantic Layer. "
        "Your job is to create accurate queries and interpret results clearly and concisely."
    ),
    verbose=True,
    allow_delegation=False,
    tools=tools,
    system_message = (
    'When using the `CreateQuery` tool, ALWAYS follow this exact format:\n\n'
    '"{\"metrics\": [{\"name\": \"coin_with_max_market_cap_volatility}], \"groupBy\": [{\"name\": \"metric_time__month\"}],\"orderBy\": [{\"name\": \"metric_time__month\"}]}"\n\n'
    '❌ Do NOT include descriptions, types, or use JSON schema-like structures.\n'
    '✅ Only provide direct, valid argument values for the tool call.'
    )

)