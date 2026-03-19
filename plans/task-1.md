# Task 1 Implementation Plan

## LLM Provider and Model
* **Provider:** Qwen Code API (self-hosted proxy on the university VM).
* **Model:** `qwen3-coder-plus`.
* **Configuration:** Credentials and endpoint URL will be loaded dynamically from `.env.agent.secret`.

## Agent Structure
1. **Input Parsing:** Use `sys.argv` to capture the user's question from the command line.
2. **Environment Loading:** Use `dotenv` to load the `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` variables.
3. **API Communication:** Use the `requests` library (or the `openai` Python SDK) to send a POST request to the OpenAI-compatible chat completions endpoint. 
4. **Output Formatting:** * Extract the assistant's response text.
   * Construct a dictionary: `{"answer": <extracted_text>, "tool_calls": []}`.
   * Print the dictionary as a JSON string to `stdout`.
5. **Error/Debug Handling:** Any status logs or error messages will be explicitly written to `stderr` using `sys.stderr.write()` to ensure the `stdout` remains valid JSON.