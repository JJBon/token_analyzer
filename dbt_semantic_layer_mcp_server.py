import sys
import json
import os
import logging
import uuid
import subprocess
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr
)

#######################################
# Minimal dbtCoreClient Stub 
# with File-based Metrics Cache (unchanged)
#######################################
class DBTCoreClient:
    def __init__(self):
        self.project_dir = os.path.join(os.path.dirname(__file__), "coindbt")
        self.manifest_path = os.path.join(self.project_dir, "target", "manifest.json")
        
        # Path to store metrics JSON file
        self.metrics_cache_file = os.path.join(self.project_dir, "target", "metrics_cache.json")

        self._metrics_cache = None  # will store {"metrics": [ ... ]}
        self._cache_lock = threading.Lock()
        self._cache_loading = False

        # Attempt to load from file on init
        self._try_load_metrics_from_file()
        if self._metrics_cache is None:
            self._start_background_cache_loading()

    def _try_load_metrics_from_file(self):
        """Load metrics from a JSON file if it exists."""
        if os.path.exists(self.metrics_cache_file):
            try:
                with open(self.metrics_cache_file, "r") as f:
                    data = json.load(f)
                    if "metrics" in data:
                        self._metrics_cache = data
                        logging.info(f"Loaded metrics from file: {self.metrics_cache_file}")
            except Exception as e:
                logging.error(f"Failed to load metrics from file: {e}")

    def _write_metrics_to_file(self):
        """Write the current metrics cache to a JSON file."""
        if self._metrics_cache is None:
            return
        try:
            with open(self.metrics_cache_file, "w") as f:
                json.dump(self._metrics_cache, f, indent=2)
            logging.info(f"Wrote metrics cache to file: {self.metrics_cache_file}")
        except Exception as e:
            logging.error(f"Failed to write metrics to file: {e}")

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
            future_to_uid = {
                executor.submit(process_metric, uid, info): uid 
                for uid, info in metrics_from_ls.items()
            }
            for future in as_completed(future_to_uid):
                try:
                    result = future.result()
                    metrics_list.append(result)
                except Exception as e:
                    uid = future_to_uid[future]
                    logging.error(f"Error processing metric {uid}: {e}")

        # 4) Store the results in our cache and write them to file
        self._metrics_cache = {"metrics": metrics_list}
        logging.info("Metrics cache built successfully.")
        self._write_metrics_to_file()

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
        return list(set(dimension_list))

    def fetchMetrics(self):
        """Return the metrics from our in-memory or file-based cache."""
        if self._metrics_cache is None:
            logging.warning("Metrics cache not ready in memory.")
            self._try_load_metrics_from_file()

        if self._metrics_cache is None:
            logging.warning("Metrics cache still not ready. Returning empty result.")
            return {"metrics": []}

        return self._metrics_cache

    def refreshMetrics(self):
        """Forcibly re-build the metrics cache (synchronously)."""
        logging.info("Refreshing metrics cache (synchronously)...")
        with self._cache_lock:
            self._build_metrics_cache()
        return self._metrics_cache

    def _find_dimensions_for_metric(self, metric_name: str):
        """Return the valid dimensions for a given metric."""
        if not self._metrics_cache:
            return []
        for m in self._metrics_cache["metrics"]:
            if m["name"] == metric_name:
                return m["dimensions"]
        return []

    #######################################
    # createQuery returns the *structure*
    # we want to pass to fetch_query_result
    #######################################
    def createQuery(self, query_params):
        """
        This returns a JSON structure (no queryId).
        For example:
        {
          "status": "CREATED",
          "query": {
             "metrics": [...],
             "groupBy": [...],
             "limit": 123,
             "orderBy": [...]
          }
        }
        """
        # Extract arrays of strings
        metrics_list = query_params.get("metrics", [])
        group_bys = query_params.get("groupBy", [])
        limit = query_params.get("limit", None)
        order_by = query_params.get("orderBy", [])

        # Validate presence of metrics
        if not metrics_list:
            return {
                "status": "ERROR",
                "error": "Missing required 'metrics' array",
                "query": query_params
            }

        # Validate groupBys for each metric
        invalid_dims = []
        for metric_name in metrics_list:
            valid_dims = self._find_dimensions_for_metric(metric_name)
            for requested_dim in group_bys:
                if requested_dim in valid_dims:
                    continue
                # If there's a time-suffix, try to remove it
                parts = requested_dim.split("__")
                if len(parts) > 1:
                    base_dim = "__".join(parts[:-1])
                else:
                    base_dim = requested_dim
                if base_dim not in valid_dims:
                    invalid_dims.append((metric_name, requested_dim))

        if invalid_dims:
            lines = []
            for (m, d) in invalid_dims:
                suggestions = self._find_dimensions_for_metric(m)
                lines.append(f"Dimension '{d}' not valid for metric '{m}'. Valid dims: {suggestions}")
            return {
                "status": "ERROR",
                "error": "\n\n".join(lines),
                "query": query_params
            }

        # Return a query dict (the user can feed this directly to fetch_query_result)
        return {
            "status": "CREATED",
            "query": {
                "metrics": metrics_list,
                "groupBy": group_bys,
                "limit": limit,
                "orderBy": order_by
            }
        }

    #######################################
    # Instead of referencing a stored queryId,
    # we run the query from the provided dict
    #######################################

    import re

    def parse_metricflow_table(self,raw_output: str) -> list[dict]:
        """
        Parse space-aligned MetricFlow table output like:

            metric_time__month      max_price_volatility_all_coins    min_price_volatility_all_coins ...
            --------------------    ------------------------------     -------------------------------
            2024-03-01T00:00:00     0.119452                          0.0220735
            ...

        Returns a list of dict rows, e.g.:
        [
        {
            "metric_time__month": "2024-03-01T00:00:00",
            "max_price_volatility_all_coins": "0.119452",
            "min_price_volatility_all_coins": "0.0220735",
            ...
        },
        ...
        ]
        """
        lines = raw_output.strip().split("\n")

        # 1) Strip out spinner/log lines, e.g. containing “✔” or “Success” or “Initiating query”:
        #    (Adjust as needed)
        data_lines = [
            line for line in lines
            if line and not any(sub in line for sub in ["⠋", "✔", "🖨", "Initiating query", "Success", "written query"])
        ]

        # 2) If there’s nothing left, return empty
        if not data_lines:
            return []

        # The first non-dashed line should be the header (e.g. "metric_time__month      max_price...")
        header_line = data_lines[0]

        # The second line is usually the dashed "----" line. We can skip it:
        #   --------------------  ------------------------------  ...
        #   But let's be robust in case sometimes there's no dashed line.
        #   We'll look for the first "----" line in data_lines.
        dashed_line_idx = None
        for idx, line in enumerate(data_lines):
            if re.match(r"^\s*-+\s*-+\s*", line):
                dashed_line_idx = idx
                break

        # If we found a dashed line, the data lines start after that line
        data_start_idx = dashed_line_idx + 1 if dashed_line_idx is not None else 1

        # 3) Split the header line on 2+ spaces to get column names
        #    e.g. "metric_time__month      max_price_volatility_all_coins" -> columns
        header_cols = re.split(r"\s{2,}", header_line.strip())

        # 4) For each subsequent line, split on 2+ spaces and map to the corresponding column
        table_rows = []
        for line in data_lines[data_start_idx:]:
            # If it's another dashed line or blank, skip
            if re.match(r"^\s*-+\s*$", line):
                continue

            cols = re.split(r"\s{2,}", line.strip())

            # If the line doesn't have the same number of columns as the header,
            # skip or handle gracefully
            if len(cols) != len(header_cols):
                continue

            row_dict = {}
            for col_name, value in zip(header_cols, cols):
                row_dict[col_name] = value

            table_rows.append(row_dict)

        return table_rows
    
    def run_query_from_dict(self, query_dict):
        """
        Takes a dict like:
          {
             "metrics": [...],
             "groupBy": [...],
             "limit": 123,
             "orderBy": [...]
          }
        Then runs 'mf query' accordingly and returns rows or error.
        """
        metrics_list = query_dict.get("metrics", [])
        group_bys = query_dict.get("groupBy", [])
        limit_value = query_dict.get("limit", None)
        # For demonstration, ignoring 'orderBy' unless needed
        # order_by = query_dict.get("orderBy", [])

        # Must have metrics
        if not metrics_list:
            return {
                "status": "ERROR",
                "results": [],
                "error": "No metrics provided"
            }

        command = ["mf", "query"]
        command.extend(["--metrics", ",".join(metrics_list)])

        if group_bys:
            command.extend(["--group-by", ",".join(group_bys)])
        if limit_value is not None:
            if isinstance(limit_value, float):
                limit_value = int(limit_value)  # e.g. 10.0 -> 10
            if limit_value is not None:
                command.extend(["--limit", str(limit_value)])

        # Possibly handle filters or orderBy if desired
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
                    "status": "ERROR",
                    "results": [],
                    "error": f"Command failed with code {result.returncode}: {result.stderr}"
                }
            
            parsed_rows = self.parse_metricflow_table(result.stdout)


         
            return {
                "status": "SUCCESSFUL",
                "results": [parsed_rows],
                "error": {
                    "stdout": result.stdout,
                    "sterror": result.stderr,
                    "command": command
                }
            }


        except Exception as e:
            logging.exception("Unexpected error running query")
            return {
                "status": "ERROR",
                "results": [],
                "error": str(e)
            }

#######################################
# Instance
#######################################
dbt_client = DBTCoreClient()


#######################################
# JSON-RPC method handlers
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
    """
    Notice that 'fetch_query_result' no longer requires 'queryId'
    but a 'query' dict with the same structure from create_query.
    """
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
                "description": "Create a query for specific metrics/dimensions in dbt Core’s semantic layer (no queryId).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "metrics": {
                            "type": "array",
                            "description": "List of metrics to query",
                            "items": {"type": "string"}
                        },
                        "groupBy": {
                            "type": "array",
                            "description": "List of dimension names",
                            "items": {"type": "string"}
                        },
                        "limit": {
                            "type": "number",
                            "description": "Limit on the number of rows to return"
                        },
                        "orderBy": {
                            "type": "array",
                            "description": "List of ordering dimension names",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["metrics"]
                }
            },
            {
                "name": "fetch_query_result",
                "description": "Fetch results by providing the same 'query' object from create_query. (No queryId needed.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "object",
                            "description": "Exact query dict from create_query output, e.g. { metrics:[...], groupBy:[...], ... }",
                            "properties": {
                                "metrics": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "groupBy": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "limit": {
                                    "type": "number"
                                },
                                "orderBy": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["metrics"]
                        }
                    },
                    "required": ["query"]
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
        "## Tools\n"
        "1. **get_documentation** – This guide.\n"
        "2. **fetch_metrics** – Get a list of known metrics.\n"
        "3. **create_query** – Build a query object (no ID).\n"
        "4. **fetch_query_result** – Provide the query object and run it.\n\n"
        "### Example:\n"
        "1. fetch_metrics -> see what's available\n"
        "2. create_query -> get {status, query}\n"
        "3. fetch_query_result -> pass that same `query` to get results\n"
    )
    return [{"type": "text", "text": guide_text}]

def handle_fetch_metrics():
    result = dbt_client.fetchMetrics()
    return [{"type": "text", "text": json.dumps(result, indent=2)}]

def handle_create_query(args):
    # Return { "status": "...", "query": {...} }
    created = dbt_client.createQuery(args)
    return [{"type": "text", "text": json.dumps(created, indent=2)}]

def handle_fetch_query_result(args):
    """
    Instead of a queryId, we expect a 'query' object:
      {
        "query": {
           "metrics": [...],
           "groupBy": [...],
           "limit": 123,
           "orderBy": [...]
        }
      }
    """
    query_obj = args.get("query")
    if not query_obj:
        raise ValueError("'query' is required, with shape { metrics: [...], groupBy: [...], ... }")

    results = dbt_client.run_query_from_dict(query_obj)
    return [{"type": "text", "text": json.dumps(results, indent=2)}]


#######################################
# Main loop
#######################################
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
            # Notification / no response needed
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
