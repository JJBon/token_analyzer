import pytest
import os
import json
from unittest.mock import patch, MagicMock

from crewai import Crew, Task
from coin_crew.agents import bi_agent
from mcpadapt.core import MCPAdapt
from mcpadapt.crewai_adapter import CrewAIAdapter
from mcp import StdioServerParameters

# We import your code that spawns the agent & tasks
# from the script that you want to test. For instance:
# from your_script import run_crew   # if you encapsulate the run logic in a function

@pytest.fixture
def mock_dbt_semantic_layer_server():
    """
    Example fixture to mock the underlying responses from the dbt semantic layer.
    You can also let it run for real if you want a 'live' integration test.
    """
    with patch("subprocess.run") as mock_subproc:
        # Set up a default "success" response from the server
        # e.g. simulating "fetch_metrics" returning some JSON
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = (
            # This is a pretend CSV or JSON for your tests
            'id,dimension,metric\n'
            '1,sample_dim,sample_metric\n'
        )
        mock_subproc.return_value = mock_process
        yield mock_subproc  # yield to the test
    # after test, teardown if needed

def test_full_crew_flow(mock_dbt_semantic_layer_server):
    """
    A sample test that runs your entire Crew environment with an agent & tasks,
    verifying the final output under controlled mocks.
    """

    # 1) Create your "MCPAdapt" environment
    with MCPAdapt(
        StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--python",
                "/home/juanjbon/dev/token_analyzer/venv/bin/python",
                "/home/juanjbon/dev/token_analyzer/dbt_semantic_layer_mcp_server.py"
            ],
            env={**os.environ},
        ),
        CrewAIAdapter()
    ) as tools:

        # 2) Attach the tools to your agent
        bi_agent.tools = tools

        # 3) Build a "task" that you want to test
        gen_task = (
            "Use the `FetchMetricsTool` to check available metrics "
            "Select metrics relevant to the user query "
            "Create query with relevant metrics... "
            "Execute query "
            "Analyze the results and gather business insights"
        )

        task = Task(
            description=gen_task,
            expected_output=(
                "Do trend analysis for the volatilities in price "
                "and market caps of all coins on the last 10 months. "
                "Explain what this might mean for a potential investor."
            ),
            agent=bi_agent
        )

        # 4) Create & run the Crew
        crew = Crew(
            agents=[bi_agent],
            tasks=[task],
            verbose=True
        )
        final_result = crew.kickoff()

        # 5) Assertions about final_result
        assert final_result, "We expect some final output from the agent"
        # Example: check if the agent gave a response referencing a dimension or metric
        assert "volatility" in final_result.lower() or "volatilities" in final_result.lower(), \
            "We expect agent to talk about volatility in the final output."

        # If you want to confirm the agent used a certain metric or dimension:
        # Check your mock_subproc calls or parse final_result

        # Example: confirm the agent used 'fetch_metrics' once
        calls = mock_dbt_semantic_layer_server.call_args_list
        used_fetch_metrics = any("dbt ls" in str(call) for call in calls)
        assert used_fetch_metrics, "Agent is supposed to call 'fetch_metrics' (dbt ls) once."

        # Example: confirm the agent built a query with 'mf query'
        used_mf_query = any("mf query" in str(call) for call in calls)
        assert used_mf_query, "Agent should eventually call 'mf query'."

        # Additional checks: 
        # For example, if your 'create_query' requires 'coin_max' metric, 
        # you can parse the final_result or the internal calls for it.
        # ...
