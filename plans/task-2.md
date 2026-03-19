# Task 2 Implementation Plan

## Tool Schemas
We will define two tools as JSON schemas in the API payload to allow the LLM to call them:
1. **`list_files(path)`**: Takes a relative directory path as a string and returns a newline-separated list of contents.
2. **`read_file(path)`**: Takes a relative file path as a string and returns the file's text content (or an error if not found).

## Agentic Loop Design
We will replace the single API call with a `while` loop capped at a maximum of 10 iterations to prevent infinite looping.
1. Append the user's question and a system prompt to the message history.
2. Send the message history and tool schemas to the LLM.
3. If the LLM returns `tool_calls`:
   - Parse the tool name and arguments.
   - Execute the corresponding local Python function (`list_files` or `read_file`).
   - Append the tool's output to the message history as a "tool" role message.
   - Continue the loop.
4. If the LLM returns a text message without tool calls:
   - This is the final answer. 
   - Parse the final text to extract the `answer` and the `source` citation.
   - Print the final JSON (`answer`, `source`, `tool_calls`) to stdout and break the loop.

## Security & Path Handling
To ensure the agent cannot read files outside the project directory (preventing directory traversal attacks like `../`), we will:
- Resolve the absolute path of the requested file/directory using `os.path.abspath`.
- Resolve the absolute path of the project root.
- Verify that the requested absolute path strictly starts with the project root absolute path before executing the tool read/list operations.