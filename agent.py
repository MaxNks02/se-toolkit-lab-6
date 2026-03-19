import sys
import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv


# --- Tool Logic ---

def is_safe_path(base_dir, target_path):
    """Prevents directory traversal."""
    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(os.path.join(base_dir, target_path))
    return abs_target.startswith(abs_base)


def list_files(base_dir, path):
    """Lists files in the project structure."""
    if not is_safe_path(base_dir, path): return "Error: Access denied."
    target = os.path.join(base_dir, path)
    if not os.path.exists(target): return f"Error: Directory '{path}' not found."
    try:
        return "\n".join(os.listdir(target))
    except Exception as e:
        return f"Error: {e}"


def read_file(base_dir, path):
    """Reads file content."""
    if not is_safe_path(base_dir, path): return "Error: Access denied."
    target = os.path.join(base_dir, path)
    if not os.path.exists(target): return f"Error: File '{path}' not found."
    try:
        with open(target, 'r', encoding='utf-8') as f:
            return f.read()[:15000]  # Increased slightly for larger backend files
    except Exception as e:
        return f"Error: {e}"


def query_api(method, path, body=None, include_auth=True):
    """Authenticated call to the backend using LMS_API_KEY."""
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip('/')
    api_key = os.getenv("LMS_API_KEY", "")
    url = f"{base_url}/{path.lstrip('/')}"

    headers = {"Content-Type": "application/json"}
    # The lab uses Bearer token authentication, not X-API-Key
    if include_auth and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = json.dumps(body).encode('utf-8') if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.dumps({"status_code": response.getcode(), "body": response.read().decode('utf-8')})
    except urllib.error.HTTPError as e:
        return json.dumps({"status_code": e.code, "body": e.read().decode('utf-8')})
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- Main Agent Loop ---

def main():
    if len(sys.argv) < 2: sys.exit(1)
    question = sys.argv[1]
    project_root = os.getcwd()

    load_dotenv('.env.agent.secret')
    load_dotenv('.env.docker.secret')

    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a directory. Use this to explore the project structure (e.g., 'backend/app/routers', 'wiki').",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a source code or documentation file.",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Make an HTTP request to the live backend API. Use to check live data, status codes, or trigger errors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                        "path": {"type": "string", "description": "API path, e.g., '/items/'"},
                        "body": {"type": "object", "description": "Optional JSON body"},
                        "include_auth": {"type": "boolean",
                                         "description": "Set to false to test endpoints without authentication"}
                    },
                    "required": ["method", "path"]
                }
            }
        }
    ]

    system_prompt = (
        "You are an expert System Debugging and Documentation Agent. You MUST use tools to find answers. NEVER answer from your own memory.\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. WIKI/DOCUMENTATION: If asked about the project wiki (like SSH, VMs, or branches), you MUST first use 'list_files' on the 'wiki' folder, then use 'read_file' to read the specific markdown file before answering.\n"
        "2. BACKEND/ROUTERS: If asked about router modules or framework, use 'list_files' on 'backend/app/routers' or 'backend', then 'read_file' to read the source code.\n"
        "3. API ERRORS: If an API query returns a 500 error, use 'read_file' to read the backend source code to find the exact buggy line.\n"
        "4. API AUTH: To test endpoints without authentication, use 'query_api' with 'include_auth': false.\n"
        "5. OUTPUT FORMAT: When you have the final answer, output ONLY a valid JSON object. "
        "Format: {\"answer\": \"your detailed answer\", \"source\": \"file path or endpoint\"}. NO markdown blocks."
    )

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    executed_tool_calls = []
    final_json = None

    for _ in range(10):
        payload = {"model": model, "messages": messages, "tools": tools}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            req = urllib.request.Request(f"{api_base.rstrip('/')}/chat/completions",
                                         data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(json.dumps({"answer": f"API Error: {e}", "source": None, "tool_calls": executed_tool_calls}))
            return

        msg = res_data["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        msg["content"] = content

        if msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except:
                    args = {}

                if name == "list_files":
                    res = list_files(project_root, args.get("path", ""))
                elif name == "read_file":
                    res = read_file(project_root, args.get("path", ""))
                elif name == "query_api":
                    res = query_api(args.get("method", "GET"), args.get("path", ""), args.get("body"),
                                    args.get("include_auth", True))
                else:
                    res = f"Error: Unknown tool {name}"

                messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": str(res)})
                executed_tool_calls.append({"tool": name, "args": args, "result": res})
        else:
            # Check if LLM output is the final JSON
            start, end = content.find("{"), content.rfind("}")
            if start != -1 and end != -1:
                try:
                    final_json = json.loads(content[start:end + 1])
                    break
                except json.JSONDecodeError:
                    pass

            # The "Nudge": If no JSON and no tools, tell the LLM to get back on track
            messages.append(msg)
            messages.append({
                "role": "user",
                "content": "SYSTEM DIRECTIVE: You provided text instead of a tool call or the final JSON. If you need to explore, CALL A TOOL. If you are finished, OUTPUT ONLY THE STRICT JSON format {\"answer\": \"...\", \"source\": \"...\"}."
            })

    # Cleanup format
    if not final_json:
        final_json = {"answer": "Exceeded maximum iterations without a conclusive answer.", "source": None}

    if isinstance(final_json.get("answer"), list):
        final_json["answer"] = "\n".join(str(i) for i in final_json["answer"])

    if not final_json.get("source"):
        for tc in reversed(executed_tool_calls):
            if tc["tool"] in ["read_file", "query_api"]:
                final_json["source"] = tc["args"].get("path")
                break

    final_json["tool_calls"] = executed_tool_calls
    print(json.dumps(final_json))


if __name__ == "__main__":
    main()