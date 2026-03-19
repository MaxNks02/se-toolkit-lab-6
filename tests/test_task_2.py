import subprocess
import json
import pytest

# The agentic loop requires multiple API calls, so we give it a generous timeout
TIMEOUT_SECONDS = 180


def run_and_parse_agent(question: str) -> dict:
    """Helper function to run the agent, capture output, and safely parse the JSON."""
    try:
        result = subprocess.run(
            ["uv", "run", "agent.py", question],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"Agent timed out after {TIMEOUT_SECONDS} seconds while answering: '{question}'")

    # Ensure the script didn't crash
    assert result.returncode == 0, f"Agent crashed with exit code {result.returncode}.\nStderr: {result.stderr}"

    stdout_text = result.stdout.strip()
    assert stdout_text, "Agent returned an empty stdout. Expected a JSON string."

    # Parse only the last line in case `uv` prints setup warnings to stdout
    try:
        last_line = stdout_text.splitlines()[-1]
        return json.loads(last_line)
    except (json.JSONDecodeError, IndexError) as e:
        pytest.fail(f"Failed to parse agent output as JSON.\nError: {e}\nRaw stdout was: {stdout_text}")


def test_agent_resolves_merge_conflict():
    """
    Test 1: Asks about merge conflicts.
    Expects 'read_file' in tool_calls and 'wiki/git-workflow.md' in the source.
    """
    output = run_and_parse_agent("How do you resolve a merge conflict?")

    # 1. Verify all required keys are present
    assert "answer" in output, "Missing 'answer' field in JSON output."
    assert "source" in output, "Missing 'source' field in JSON output."
    assert "tool_calls" in output, "Missing 'tool_calls' field in JSON output."

    # 2. Verify the agent used the correct tool
    tools_used = [tc.get("tool") for tc in output.get("tool_calls", [])]
    assert "read_file" in tools_used, f"Expected 'read_file' to be in tool_calls. Tools actually used: {tools_used}"

    # 3. Verify the agent correctly identified the source file
    source = output.get("source", "")
    assert source is not None, "The 'source' field should not be null."
    assert "wiki/git-workflow.md" in source, f"Expected source to contain 'wiki/git-workflow.md', but got: '{source}'"


def test_agent_lists_wiki_files():
    """
    Test 2: Asks what files are in the wiki.
    Expects 'list_files' in tool_calls.
    """
    output = run_and_parse_agent("What files are in the wiki?")

    # 1. Verify all required keys are present
    assert "answer" in output, "Missing 'answer' field in JSON output."
    assert "source" in output, "Missing 'source' field in JSON output."
    assert "tool_calls" in output, "Missing 'tool_calls' field in JSON output."

    # 2. Verify the agent used the correct tool to look up the directory