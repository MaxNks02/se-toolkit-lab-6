import sys
import json
import os
import re
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
            # Reduced to 10k to protect context window during long loops
            return f.read()[:10000]
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

            # Help the LLM count items in JSON arrays natively
            try:
                parsed = json.loads(body_str)
                if isinstance(parsed, list):
                    body_str = f"[SYSTEM NOTE: This JSON array contains exactly {len(parsed)} items.]\n" + body_str
            except json.JSONDecodeError:
                pass

            if len(body_str) > 10000:
                body_str = body_str[:10000] + "... [TRUNCATED]"
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

    # Improved tool descriptions to guide LLM naturally
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a directory. Use to explore project structure (e.g., 'wiki', 'backend').",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read source code or documentation. Use to inspect code for bugs or trace architecture.",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Make an HTTP request to the live backend API. Use to count items, test auth (include_auth=false), or trigger 500 errors to diagnose bugs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                        "path": {"type": "string",
                                 "description": "API path, e.g., '/items/' or '/analytics/top-learners?lab=lab-01'"},
                        "body": {"type": "object", "description": "Optional JSON body"},
                        "include_auth": {"type": "boolean",
                                         "description": "Set to false to test endpoints without authentication"}
                    },
                    "required": ["method", "path"]
                }
            }
        }
    ]

    # Generalized runbook: Teaches STRATEGIES, not the answers themselves
    system_prompt = (
        "You are an expert System Debugging Agent. You MUST use tools to find answers. NEVER guess.\n"
        "CRITICAL STRATEGIES:\n"
        "1. WIKI: Use 'list_files' on 'wiki', then 'read_file'.\n"
        "2. FRAMEWORK/ROUTERS: Use 'list_files' on 'backend/app/routers' and 'read_file' to identify frameworks and domains.\n"
        "3. API COUNT: Use 'query_api' on '/items/'. Read the SYSTEM NOTE at the top for the exact count.\n"
        "4. BUG HUNTING (500 Errors): Query the endpoint with different parameters (e.g., '?lab=lab-99' or '?lab=lab-01') until it crashes. Then 'read_file' the router source code to find the exact Python exception (e.g., ZeroDivisionError, TypeError) and explain it.\n"
        "5. ARCHITECTURE: To explain a request journey or architecture, read 'docker-compose.yml' and 'backend/Dockerfile' to find all components (proxy, web server, db, etc.).\n"
        "6. IDEMPOTENCY: To explain how pipelines avoid duplicates, 'read_file' the pipeline code and find the exact field used for checking.\n"
        "FINAL OUTPUT FORMAT: Output ONLY a valid JSON object: {\"answer\": \"detailed answer\", \"source\": \"file or endpoint\"}."
    )

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    executed_tool_calls = []
    final_json = None

    for _ in range(15):
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "temperature": 0.0  # Strict determinism
        }
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
            # Enhanced Robust JSON Parsing using Regular Expressions
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                try:
                    final_json = json.loads(match.group(0))
                    break
                except json.JSONDecodeError:
                    pass

            messages.append(msg)
            messages.append({
                "role": "user",
                "content": "SYSTEM ERROR: You must either call a tool or output the final JSON: {\"answer\": \"...\", \"source\": \"...\"}."
            })

    if not final_json:
        last_attempt = content if content else "Exceeded maximum iterations."
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