# minimal_http_wrapper.py
from flask import Flask, request, jsonify
import subprocess
import json
import os

app = Flask(__name__)

venv_dir = "coindbt/venv"
base_dir = os.path.dirname(os.path.abspath(__file__))
mcp_script_path = os.path.join(base_dir, "dbt_semantic_layer_mcp_server.py")
print(f"mcp_script_path: {mcp_script_path}")

# Start your MCP server code in a subprocess
python_path = os.path.join(base_dir, venv_dir, "bin", "python")
mcp_process = subprocess.Popen(
    ["python", str(mcp_script_path)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)

@app.route("/mcp", methods=["POST"])
def handle_mcp():
    req_body = request.get_json()
    # forward it to the MCP server’s stdin
    mcp_process.stdin.write(json.dumps(req_body) + "\n")
    mcp_process.stdin.flush()
    # read one line of output from server stdout
    resp_line = mcp_process.stdout.readline().strip()
    # parse and return
    try:
        resp_json = json.loads(resp_line)
        return jsonify(resp_json)
    except Exception as e:
        return jsonify({"error": f"Failed to parse MCP response: {e}"}), 500

if __name__ == "__main__":
    app.run(port=8000)
