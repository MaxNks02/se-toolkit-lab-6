import subprocess
import json
import pytest

TIMEOUT_SECONDS = 180


def test_framework_tool_usage():
    # Verifies Question 3 uses read_file
    proc = subprocess.run(
        ["uv", "run", "agent.py", "What Python web framework is used?"],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS
    )
    assert proc.returncode == 0, f"Agent crashed: {proc.stderr}"

    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        pytest.fail(f"Invalid JSON output: {proc.stdout}")

    tools_used = [tc["tool"] for tc in data.get("tool_calls", [])]
    assert "read_file" in tools_used, "Agent did not use read_file"
    assert "FastAPI" in data.get("answer", ""), "Agent did not mention FastAPI"


def test_database_count_tool_usage():
    # Verifies Question 5 uses query_api
    proc = subprocess.run(
        ["uv", "run", "agent.py", "How many items are in the database?"],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS
    )
    assert proc.returncode == 0, f"Agent crashed: {proc.stderr}"

    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        pytest.fail(f"Invalid JSON output: {proc.stdout}")

    tools_used = [tc["tool"] for tc in data.get("tool_calls", [])]
    assert "query_api" in tools_used, "Agent did not use query_api"