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

    def format_list_to_name_only(self, items: Optional[List]) -> List[Dict[str, str]]:
            """
            Convert a list of strings/dicts into a list of dicts 
            with the single key {"name": ...}.
            Any extraneous keys are dropped.
            """
            if not items:
                return []
            formatted = []
            for item in items:
                if isinstance(item, str):
                    formatted.append({"name": item})
                elif isinstance(item, dict):
                    # If we have "name" in the dict, keep only that
                    if "name" in item:
                        formatted.append({"name": item["name"]})
                    else:
                        # fallback/ignore or handle an error
                        pass
                # else ignore or handle errors
            return formatted

    def _run(
        self,
        metrics: List[Dict[str, str]],  # each item => { "name": "some_metric" }
        groupBy: Optional[List[Dict[str, str]]] = None,
        where: Optional[List[Dict[str, str]]] = None,
        limit: Optional[int] = None,
        orderBy: List[Dict[str, str]]= None
    ):
         # Fix up metrics to only have "name" keys, if desired
        formatted_metrics = self.format_list_to_name_only(metrics)
        
        # groupBy, orderBy similarly
        formatted_groupBy = self.format_list_to_name_only(groupBy)
        formatted_orderBy = self.format_list_to_name_only(orderBy)

        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "create_query",
                "arguments": {
                    "metrics": formatted_metrics,
                    "groupBy": groupBy or [],
                    #"where": where or [],
                    #"limit": limit,
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