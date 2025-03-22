import sys
import json
import os
import logging
import uuid
import subprocess
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr
)

#######################################
# Minimal dbtCoreClient Stub with Lazy Asynchronous Metrics Cache
#######################################
class DBTCoreClient:
    """
    A minimal stub for demonstrating how you'd communicate with dbt Core.
    In a real environment, parse the manifest or run `dbt compile`, etc.
    This version loads the metrics cache in a background thread.
    """
    def __init__(self):
        self._query_store = {}  # A dict to store query_id -> query_params
        # Use the directory of the current script to find the `coindbt` path
        self.project_dir = os.path.join(os.path.dirname(__file__), "coindbt")
        self.manifest_path = os.path.join(self.project_dir, "target", "manifest.json")
        self._metrics_cache = None  # will store {"metrics": [ ... ]}
        self._cache_lock = threading.Lock()
        self._cache_loading = False
        # Start background thread to build the cache.
        self._start_background_cache_loading()

    def _start_background_cache_loading(self):
        with self._cache_lock:
            if not self._cache_loading:
                self._cache_loading = True
                logging.info("Starting background thread to build metrics cache...")
                thread = threading.Thread(target=self._build_metrics_cache_background, daemon=True)
                thread.start()

    def _build_metrics_cache_background(self):
        try:
            self._build_metrics_cache()
        except Exception as e:
            logging.error(f"Background cache build failed: {e}")
        finally:
            with self._cache_lock:
                self._cache_loading = False

    def _build_metrics_cache(self):
        logging.info("Building metrics cache...")
        # 1) Gather all metrics from dbt ls
        metrics_from_ls = self._get_all_metrics_info()

        # 2) Load manifest.json (for better descriptions, etc.)
        manifest_data = {}
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, "r") as f:
                manifest_data = json.load(f)
        else:
            logging.warning("No manifest.json found. Run dbt compile or dbt build first.")

        manifest_metrics = manifest_data.get("metrics", {})

        # 3) Use a thread pool to concurrently fetch dimensions for each metric
        def process_metric(unique_id, metric_info):
            metric_name = metric_info.get("name", "unknown_metric")
            manifest_def = manifest_metrics.get(unique_id, {})
            description = manifest_def.get("description") or metric_info.get("description", "")
            dimensions = self._fetch_dimensions_for_metric(metric_name)
            return {
                "name": metric_name,
                "description": description,
                "dimensions": dimensions,
            }

        metrics_list = []
        with ThreadPoolExecutor() as executor:
            future_to_uid = {executor.submit(process_metric, uid, info): uid for uid, info in metrics_from_ls.items()}
            for future in as_completed(future_to_uid):
                try:
                    result = future.result()
                    metrics_list.append(result)
                except Exception as e:
                    uid = future_to_uid[future]
                    logging.error(f"Error processing metric {uid}: {e}")

        # 4) Store the results in our cache.
        self._metrics_cache = {"metrics": metrics_list}
        logging.info("Metrics cache built successfully.")

    def _get_all_metrics_info(self):
        logging.info("Fetching metrics from dbt with `dbt ls`...")
        command = [
            "dbt",
            "ls",
            "--resource-type", "metric",
            "--output", "json",
            "--quiet"
        ]
        result = subprocess.run(
            command,
            cwd=self.project_dir,
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.strip().split("\n")
        metrics_map = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            metric_data = json.loads(line)
            unique_id = metric_data.get("unique_id")
            if unique_id:
                metrics_map[unique_id] = metric_data
        return metrics_map

    def _fetch_dimensions_for_metric(self, metric_name: str):
        command = ["mf", "list", "dimensions", "--metrics", metric_name]
        logging.info(f"Running: {command}")
        result = subprocess.run(
            command,
            cwd=self.project_dir,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            logging.warning(f"MetricFlow command failed for metric={metric_name}. "
                            f"Return code={result.returncode}, stderr={result.stderr}")
            return []
        lines = result.stdout.strip().split("\n")
        dimension_list = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("✔"):
                continue
            if line.startswith("• "):
                dim_name = line.replace("• ", "").strip()
                dimension_list.append(dim_name)
        return dimension_list

    def fetchMetrics(self):
        """
        Returns the cached metrics info. If the cache isn't ready, logs a warning and returns an empty result.
        """
        if self._metrics_cache is None:
            logging.warning("Metrics cache not ready yet. Returning empty result.")
            return {"metrics": []}
        return self._metrics_cache

    def refreshMetrics(self):
        logging.info("Refreshing metrics cache...")
        self._build_metrics_cache()
        return self._metrics_cache

    def getQueryResult(self, query_id: str):
        if query_id not in self._query_store:
            return {
                "queryId": query_id,
                "status": "ERROR",
                "results": [],
                "error": f"No query found for ID: {query_id}"
            }
        query_params = self._query_store[query_id]
        metrics_list = query_params.get("metrics", [])
        group_bys = query_params.get("groupBy", [])
        filters = query_params.get("where", [])
        limit = query_params.get("limit", None)
        command = ["mf", "query"]
        if metrics_list:
            metric_names = [m["name"] for m in metrics_list]
            command.append("--metrics")
            command.append(",".join(metric_names))
        if group_bys:
            transformed_dims = []
            for g in group_bys:
                dim_name = g["name"]
                transformed_dims.append(dim_name)
            command.append("--group-by")
            command.append(",".join(transformed_dims))
        if filters:
            filter_strs = []
            for f in filters:
                raw_sql = f.get("sql", "")
                if not raw_sql:
                    continue
                if "Dimension(" not in raw_sql:
                    raw_sql = raw_sql.replace(
                        "product__product_name",
                        "{{ Dimension('product__product_name') }}"
                    )
                filter_strs.append(raw_sql)
            if filter_strs:
                combined_where = " and ".join(filter_strs)
                command.append("--where")
                command.append(combined_where)
        if limit is not None:
            command.append("--limit")
            command.append(str(limit))
        command.append("--csv")
        command.append("-")
        logging.info(f"Submitting MetricFlow command: {command}")
        try:
            result = subprocess.run(
                command,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                return {
                    "queryId": query_id,
                    "status": "ERROR",
                    "results": [],
                    "error": f"Command failed with code {result.returncode}: {result.stderr}"
                }
            lines = result.stdout.strip().split("\n")
            reader = csv.DictReader(lines)
            rows = list(reader)
            return {
                "queryId": query_id,
                "status": "SUCCESSFUL",
                "results": rows,
                "error": None
            }
        except Exception as e:
            logging.error(f"error with processing {result.stderr}")
            return {
                "queryId": query_id,
                "status": "ERROR",
                "results": [],
                "error": str(e)
            }

    def _find_dimensions_for_metric(self, metric_name: str):
        if not self._metrics_cache:
            return []  # or build the cache
        for m in self._metrics_cache["metrics"]:
            if m["name"] == metric_name:
                return m["dimensions"]
        return []

    def createQuery(self, query_params):
        """
        Create a query in your local environment. 
        Return a queryId so the caller can poll for results.
        """
        import uuid
        query_id = str(uuid.uuid4())

        # 1) Validate the dimensions here
        metrics_list = query_params.get("metrics", [])
        group_bys = query_params.get("groupBy", [])

        invalid_dims = []

        for metric_dict in metrics_list:
            metric_name = metric_dict["name"]
            # Pull valid dimensions from the cache
            valid_dims = self._find_dimensions_for_metric(metric_name)

            for g in group_bys:
                requested_dim = g["name"]
                # First, check if the full dimension is valid
                if requested_dim in valid_dims:
                    base_dim = requested_dim
                else:
                    parts = requested_dim.split("__")
                    if len(parts) > 1:
                        # If the full string is not valid, assume the last part might be an interval
                        base_dim = "__".join(parts[:-1])
                    else:
                        base_dim = requested_dim

                if base_dim not in valid_dims:
                    invalid_dims.append((metric_name, requested_dim))


        # 2) If there are invalid dimensions, return an error response
        if invalid_dims:
            lines = []
            for (m, d) in invalid_dims:
                suggestions = self._find_dimensions_for_metric(m)
                lines.append(
                    f"Dimension '{d}' is not valid for metric '{m}'.\n"
                    f"Valid dimensions include: {suggestions}"
                )

            error_msg = "\n\n".join(lines)

            return {
                "queryId": None,      # no valid query ID in this scenario
                "status": "ERROR",
                "error": error_msg,
                "queryParams": query_params
            }

        # 3) If no invalid dimensions, store the query and return success
        self._query_store[query_id] = query_params
        return {
            "queryId": query_id,
            "status": "CREATED",
            "queryParams": query_params
        }

# Instantiate the dbt client
dbt_client = DBTCoreClient()

#######################################
# JSON-RPC helpers and main loop remain unchanged...
#######################################
def build_success_response(request_id, result_obj):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result_obj
    }

def build_error_response(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }

def handle_initialize_request(_params):
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "dbt-semantic-layer-mcp-python",
            "version": "0.1.0"
        }
    }

def handle_list_tools_request():
    return {
        "tools": [
            {
                "name": "get_documentation",
                "description": "Get a comprehensive user guide on using the dbt Semantic Layer MCP Server.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "fetch_metrics",
                "description": "Fetch a list of metrics from dbt Core’s semantic layer.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "create_query",
                "description": "Create a query for specific metrics/dimensions in dbt Core’s semantic layer.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "metrics": {
                            "type": "array",
                            "description": "List of metrics to query",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"}
                                },
                                "required": ["name"]
                            }
                        },
                        "groupBy": {
                            "type": "array",
                            "description": "List of dimension objects",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"}
                                },
                                "required": ["name"]
                            }
                        },
                        "where": {
                            "type": "array",
                            "description": "List of filter objects",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "sql": {"type": "string"}
                                },
                                "required": ["sql"]
                            }
                        },
                        "limit": {
                            "type": "number",
                            "description": "Limit on the number of rows to return"
                        },
                        "orderBy": {
                            "type": "array",
                            "description": "List of ordering objects",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "descending": {"type": "boolean"},
                                    "groupBy": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"}
                                        }
                                    },
                                    "metric": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"}
                                        }
                                    }
                                },
                                "required": ["descending"]
                            }
                        }
                    },
                    "required": ["metrics"]
                }
            },
            {
                "name": "fetch_query_result",
                "description": "Fetch results for a previously created query. Poll until status=SUCCESSFUL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "queryId": {
                            "type": "string",
                            "description": "ID of the query to fetch"
                        }
                    },
                    "required": ["queryId"]
                }
            }
        ]
    }

def handle_call_tool_request(params):
    tool_name = params.get("name")
    args = params.get("arguments", {})
    if tool_name == "get_documentation":
        return handle_get_documentation()
    elif tool_name == "fetch_metrics":
        return handle_fetch_metrics()
    elif tool_name == "create_query":
        return handle_create_query(args)
    elif tool_name == "fetch_query_result":
        return handle_fetch_query_result(args)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

def handle_get_documentation():
    guide_text = (
        "# Guide: Using the dbt Semantic Layer MCP Server (Python)\n\n"
        "This guide explains how to use the dbt Semantic Layer MCP Server, "
        "which exposes convenient JSON-RPC 'tools' for querying dbt Core.\n\n"
        "## Tools\n"
        "1. **get_documentation**: Shows this guide.\n"
        "2. **fetch_metrics**: Retrieves all metrics known to dbt.\n"
        "3. **create_query**: Creates a query for given metrics/dimensions.\n"
        "4. ** When using a date/time dimension add time interval as suffix __period for example metric_time__week.\n"
        "5. **fetch_query_result**: Fetches results for a created query.\n\n"
        "## Example Usage\n\n"
        "1. **fetch_metrics**: to see available metrics.\n"
        "2. **create_query**: specifying metrics, optional groupBy, where, etc.\n"
        "3. **fetch_query_result**: poll until the status is SUCCESSFUL.\n\n"
        "## Troubleshooting\n"
        "- Ensure metric/dimension names match what is returned by fetch_metrics.\n"
        "- If a query fails, check logs or your dbt setup.\n"
    )
    return [{"type": "text", "text": guide_text}]

def handle_fetch_metrics():
    result = dbt_client.fetchMetrics()
    return [{"type": "text", "text": json.dumps(result, indent=2)}]

def handle_create_query(args):
    created_query = dbt_client.createQuery(args)
    return [{"type": "text", "text": json.dumps(created_query, indent=2)}]

def handle_fetch_query_result(args):
    query_id = args.get("queryId")
    if not query_id:
        raise ValueError("queryId is required")
    results = dbt_client.getQueryResult(query_id)
    return [{"type": "text", "text": json.dumps(results, indent=2)}]

def build_success_response(request_id, result_obj):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result_obj
    }

def build_error_response(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
       

def main():
    logging.info("dbt Semantic Layer MCP Python server starting up. Listening on stdin for JSON-RPC requests...")
    for line in sys.stdin:
        raw_line = line.strip()
        if not raw_line:
            continue
        logging.debug(f"Raw input: {raw_line}")
        try:
            request_json = json.loads(raw_line)
        except Exception as e:
            logging.exception("JSON parse error")
            continue
        request_id = request_json.get("id")
        method = request_json.get("method")
        params = request_json.get("params", {})
        logging.debug(f"method='{method}', id={request_id}, params={params}")
        if request_id is None:
            if method == "notifications/initialized":
                logging.info("Received notifications/initialized. Doing nothing.")
            elif method == "notifications/cancelled":
                logging.info("Received notifications/cancelled. Doing nothing.")
            else:
                logging.info(f"Unknown notification method '{method}', ignoring.")
            continue
        try:
            if method == "initialize":
                response_obj = handle_initialize_request(params)
                output = build_success_response(request_id, response_obj)
            elif method == "tools/list":
                response_obj = handle_list_tools_request()
                output = build_success_response(request_id, response_obj)
            elif method == "tools/call":
                response_obj = handle_call_tool_request(params)
                output = build_success_response(request_id, {"content": response_obj})
            else:
                logging.warning(f"Unknown method: {method}")
                output = build_error_response(request_id, -32601, f"Unknown method: {method}")
        except Exception as e:
            logging.exception(f"Exception handling request {method}")
            output = build_error_response(request_id, -32603, f"Internal error: {str(e)}")
        response_str = json.dumps(output)
        logging.debug(f"Sending response: {response_str}")
        print(response_str)
        sys.stdout.flush()

if __name__ == "__main__":
    main()
