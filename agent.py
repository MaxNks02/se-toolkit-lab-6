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
            return f.read()[:15000]  # Cap read size to prevent context overflow
    except Exception as e:
        return f"Error: {e}"

def query_api(method, path, body=None, include_auth=True):
    """Authenticated call to the backend using LMS_API_KEY."""
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip('/')
    api_key = os.getenv("LMS_API_KEY", "")
    url = f"{base_url}/{path.lstrip('/')}"

    headers = {"Content-Type": "application/json"}
    if include_auth and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = json.dumps(body).encode('utf-8') if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=15) as response:
            body_str = response.read().decode('utf-8')
            if len(body_str) > 15000:
                body_str = body_str[:15000] + "... [TRUNCATED]"
            return json.dumps({"status_code": response.getcode(), "body": body_str})
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
                        "path": {"type": "string", "description": "API path, e.g., '/items/' or '/analytics/completion-rate?lab=lab-99'"},
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
        "You are an expert System Debugging Agent. You MUST use tools to find answers. NEVER guess or answer from memory.\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. WIKI: If asked about the wiki, first use 'list_files' on 'wiki', then 'read_file' on the markdown file.\n"
        "2. ROUTERS: If asked about backend router modules, use 'list_files' on 'backend/app/routers', then 'read_file'.\n"
        "3. API QUERIES: To query an endpoint with parameters (like '?lab=lab-99'), include the exact query string in the 'path' argument of 'query_api' (e.g., '/analytics/completion-rate?lab=lab-99').\n"
        "4. BUG HUNTING: If an API query returns an error (like a 500 status code), you MUST use 'read_file' to read the corresponding router source code (e.g., 'backend/app/routers/analytics.py') to find the exact Python exception (like ZeroDivisionError or TypeError) and the buggy line of code.\n"
        "5. API AUTH: To test endpoints without authentication, use 'query_api' with 'include_auth': false.\n"
        "6. OUTPUT FORMAT: When you have the final answer, output ONLY a valid JSON object. "
        "Format: {\"answer\": \"your detailed answer\", \"source\": \"file path or endpoint\"}. NO markdown blocks."
    )

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    executed_tool_calls = []
    final_json = None

    for _ in range(15):
        payload = {"model": model, "messages": messages, "tools": tools}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            req = urllib.request.Request(f"{api_base.rstrip('/')}/chat/completions",
                                         data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=90) as response:
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
            try:
                final_json = json.loads(content)
                break
            except json.JSONDecodeError:
                cleaned = content.strip("` \n").removeprefix("json").strip()
                try:
                    final_json = json.loads(cleaned)
                    break
                except json.JSONDecodeError:
                    start = content.find('{')
                    end = content.rfind('}')
                    if start != -1 and end > start:
                        try:
                            final_json = json.loads(content[start:end + 1])
                            break
                        except json.JSONDecodeError:
                            pass

            # The "Nudge": If it fails to parse as JSON, force it to use tools or output JSON properly
            messages.append(msg)
            messages.append({
                "role": "user",
                "content": "SYSTEM ERROR: You provided conversational text. You MUST either call a tool (like 'query_api' or 'read_file') to investigate further, or output the final answer as a strict JSON object: {\"answer\": \"...\", \"source\": \"...\"}."
            })

    if not final_json:
        # Save whatever text the LLM managed to generate if it failed formatting after 15 loops
        last_attempt = content if content else "Exceeded maximum iterations without a conclusive answer."
        final_json = {"answer": last_attempt, "source": None}

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