import subprocess
import json

def test_framework_tool_usage():
    # Verifies Question 3 uses read_file
    proc = subprocess.run(["uv", "run", "agent.py", "What Python web framework is used?"], capture_output=True, text=True)
    data = json.loads(proc.stdout)
    tools_used = [tc["tool"] for tc in data.get("tool_calls", [])]
    assert "read_file" in tools_used
    assert "FastAPI" in data["answer"]

def test_database_count_tool_usage():
    # Verifies Question 5 uses query_api
    proc = subprocess.run(["uv", "run", "agent.py", "How many items are in the database?"], capture_output=True, text=True)
    data = json.loads(proc.stdout)
    tools_used = [tc["tool"] for tc in data.get("tool_calls", [])]
    assert "query_api" in tools_used