import subprocess
import json
import pytest


def test_agent_basic_plumbing():
    """
    Test that agent.py correctly parses input, calls the LLM,
    and outputs the exact required JSON format to stdout.
    """
    question = "What is the capital of France?"

    # Run the agent as a subprocess using uv
    try:
        result = subprocess.run(
            ["uv", "run", "agent.py", question],
            capture_output=True,
            text=True,
            timeout=65  # 60s for the agent + 5s for uv startup overhead
        )
    except subprocess.TimeoutExpired:
        pytest.fail("The agent took longer than 60 seconds to respond.")

    # 1. Check exit code is 0 (Success)
    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}. stderr: {result.stderr}"

    # 2. Check that stdout contains valid JSON
    stdout_text = result.stdout.strip()
    assert stdout_text, "Stdout is empty. Expected a JSON string."

    try:
        parsed_output = json.loads(stdout_text.splitlines()[-1])  # Safely grab the last line in case of uv warnings
    except json.JSONDecodeError as e:
        pytest.fail(f"Stdout does not contain valid JSON. Error: {e}\nRaw stdout was: {stdout_text}")

    # 3. Check for the exact required keys
    assert "answer" in parsed_output, "The 'answer' key is missing from the JSON output."
    assert "tool_calls" in parsed_output, "The 'tool_calls' key is missing from the JSON output."

    # 4. Validate the values
    assert isinstance(parsed_output["answer"], str), "'answer' must be a string."
    assert len(parsed_output["answer"]) > 0, "The 'answer' string is empty."
    assert parsed_output["tool_calls"] == [], "For Task 1, 'tool_calls' must be exactly an empty list."