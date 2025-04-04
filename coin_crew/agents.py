# agents.py (continued)
from crewai import Agent
from crewai.tools import BaseTool
import requests
from coin_crew.llm_config import openai_gpt4,  ollama_llama2, openai_gpt35, bedrock_llm
from typing import Dict, List, Optional
from pydantic import  BaseModel, PrivateAttr
import json
from typing import Type
from typing import Union
from coin_crew.tools.dbt_tools import FetchMetricsTool, FetchQueryResultTool, CreateQueryTool
from crewai import Agent, Crew, Task 
from mcp import StdioServerParameters



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



# Instantiate BI agent with the semantic query tool
MCP_SERVER_URL = "http://localhost:8000/mcp"  # Example URL for MCP server
# tools=[
#         FetchMetricsTool(MCP_SERVER_URL),
#         CreateQueryTool(MCP_SERVER_URL),
#         FetchQueryResultTool(MCP_SERVER_URL),
#     ]


bi_agent = Agent(
    role="Business Intelligence Analyst",
    goal=(
        "Analyze and interpret metric data for executive decision-making. "
        "Generate queries using the CreateQuery tool, and extract meaningful patterns from the result."
    ),
    llm=bedrock_llm,
    #llm=ollama_llama2,
    backstory=(
        "You are a data-savvy analyst with strong knowledge of the dbt Semantic Layer. "
        "Your job is to create accurate queries and interpret results clearly and concisely."
    ),
    verbose=True,
    allow_delegation=False,
    system_message = """
        You have NO knowledge unless you call these 3 tools **in order**:
        1)get documentation
        2) get metrics 
        3) create query
        4) fetch query results 
        If you fail or skip any step, you will have no data and must not produce a final answer.
        """.strip(),

)