import sys
import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv


def is_safe_path(base_dir, target_path):
    """Ensure the target path is within the base directory to prevent directory traversal."""
    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(target_path)
    return abs_target.startswith(abs_base)


def list_files(base_dir, path):
    """Tool to list files in a directory."""
    target = os.path.join(base_dir, path)
    if not is_safe_path(base_dir, target):
        return "Error: Access denied. Cannot read outside the project directory."
    if not os.path.exists(target):
        return "Error: Path does not exist."
    if not os.path.isdir(target):
        return "Error: Path is not a directory."
    try:
        return "\n".join(os.listdir(target))
    except Exception as e:
        return f"Error: {e}"


def read_file(base_dir, path):
    """Tool to read the contents of a file."""
    target = os.path.join(base_dir, path)
    if not is_safe_path(base_dir, target):
        return "Error: Access denied. Cannot read outside the project directory."
    if not os.path.exists(target):
        return "Error: File does not exist."
    if not os.path.isfile(target):
        return "Error: Path is not a file."
    try:
        with open(target, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}"


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Error: Please provide a question as a command-line argument.\n")
        sys.exit(1)

    question = sys.argv[1]
    project_root = os.getcwd()

    # Load configuration
    load_dotenv('.env.agent.secret')
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not all([api_key, api_base, model]):
        sys.stderr.write("Error: Missing LLM configuration in .env.agent.secret\n")
        sys.exit(1)

    # Define the tool schemas in OpenAI format
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given relative path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string",
                                 "description": "Relative directory path from project root (e.g., 'wiki' or '.')."}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string",
                                 "description": "Relative file path from project root (e.g., 'wiki/git-workflow.md')."}
                    },
                    "required": ["path"]
                }
            }
        }
    ]

    # System prompt heavily instructs the LLM on behavior and final output format
    system_prompt = (
        "You are a strict documentation agent. You MUST NOT answer questions from your own knowledge. "
        "You MUST answer by exploring the project directory using tools. "
        "First, use 'list_files' with the path 'wiki' to discover files. "
        "Second, use 'read_file' on the specific file (e.g., 'wiki/git-workflow.md') to read its contents. "
        "Once you find the answer in the text, your final response MUST be a valid JSON object with exactly two keys: "
        "'answer' (a concise answer based ONLY on the file content) and "
        "'source' (the EXACT file path you read from, plus the section anchor, e.g., 'wiki/git-workflow.md#resolving-merge-conflicts'). "
        "CRITICAL: Do not hallucinate or guess file names. The 'source' field MUST exactly match the file path you passed to 'read_file'. "
        "Output ONLY the raw JSON object. Do not use markdown blocks like ```json."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    executed_tool_calls = []
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Agentic Loop: Run for a maximum of 10 iterations
    loop_count = 0
    while loop_count < 10:
        loop_count += 1

        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto"
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                response_data = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            sys.stderr.write(f"Error calling LLM API: {e}\n")
            sys.exit(1)

        choice = response_data["choices"][0]
        message = choice["message"]

        # Check if the LLM wants to call a tool
        if message.get("tool_calls"):
            # Append the assistant's tool_call request to the history
            messages.append(message)

            for tc in message["tool_calls"]:
                tc_id = tc["id"]
                func_name = tc["function"]["name"]
                args_str = tc["function"]["arguments"]

                try:
                    args = json.loads(args_str)
                except:
                    args = {}

                result_str = ""
                # Execute the matched function locally
                if func_name == "list_files":
                    result_str = list_files(project_root, args.get("path", ""))
                elif func_name == "read_file":
                    result_str = read_file(project_root, args.get("path", ""))
                else:
                    result_str = f"Error: Unknown tool {func_name}"

                # Append the tool's result to the message history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": func_name,
                    "content": result_str
                })

                # Store for final JSON output
                executed_tool_calls.append({
                    "tool": func_name,
                    "args": args,
                    "result": result_str
                })
        else:
            # No tool calls means the LLM has provided the final answer
            final_content = message.get("content", "").strip()

            # Clean up markdown formatting if the LLM hallucinated it
            if final_content.startswith("```json"):
                final_content = final_content.strip("`").replace("json\n", "", 1)
            elif final_content.startswith("```"):
                final_content = final_content.strip("`")

            # Parse the LLM's JSON to extract answer and source
            try:
                parsed_final = json.loads(final_content)
                ans = parsed_final.get("answer", final_content)
                src = parsed_final.get("source", "unknown")
            except json.JSONDecodeError:
                ans = final_content
                src = "unknown"

            # Construct the exact output expected by the autochecker
            final_output = {
                "answer": ans,
                "source": src,
                "tool_calls": executed_tool_calls
            }

            print(json.dumps(final_output))
            sys.exit(0)

    # If the loop maxes out at 10 without a final answer
    sys.stderr.write("Error: Exceeded maximum of 10 tool calls.\n")
    final_output = {
        "answer": "Error: Exceeded max iterations.",
        "source": "",
        "tool_calls": executed_tool_calls
    }
    print(json.dumps(final_output))
    sys.exit(0)


if __name__ == "__main__":
    main()