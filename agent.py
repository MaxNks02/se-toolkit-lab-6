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
            return f.read()[:10000]  # Cap at 10k to prevent context window overflow
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

            # Inject a system note to help the LLM count items without math hallucination
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

    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a directory. Use to explore project structure.",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read source code or documentation. Use to inspect code or read wiki pages.",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Make an HTTP request to the live backend API. Use to count items, check endpoints, or trigger errors.",
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

    # The aggressive System Prompt designed to stop "chatty" LLMs
    system_prompt = (
        "You are an autonomous System Debugging Agent. You MUST use tools to find answers. NEVER guess.\n"
        "STRICT BEHAVIORAL RULES:\n"
        "1. NO CHATTING: Never output conversational text, inner monologue, or explanations. Do not say 'I will now look at...'\n"
        "2. To explore, you MUST trigger a tool call via the JSON schema.\n"
        "3. If a file doesn't contain the answer, use list_files to look for other files.\n"
        "STRATEGIES:\n"
        "- WIKI: 'list_files' on 'wiki', then 'read_file'.\n"
        "- ROUTERS/FRAMEWORK: 'list_files' on 'backend/app/routers', then 'read_file'. Note the framework used in main files.\n"
        "- API COUNT: 'query_api' on '/items/'.\n"
        "- BUG HUNTING (500 Errors): 'query_api' the endpoint with parameters (like '?lab=lab-01' or '?lab=lab-99') until it crashes. Then 'read_file' the router source code to find the exact Python exception (e.g., TypeError, ZeroDivisionError).\n"
        "- ARCHITECTURE: 'read_file' on 'docker-compose.yml' and 'backend/Dockerfile'.\n"
        "- PIPELINE: 'read_file' on 'backend/app/routers/pipeline.py' to see how duplicates are avoided.\n"
        "FINAL OUTPUT FORMAT:\n"
        "When you are finished, output ONLY a JSON object exactly like this:\n"
        "{\"answer\": \"detailed final answer\", \"source\": \"file path or endpoint\"}"
    )

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    executed_tool_calls = []
    final_json = None

    for loop_num in range(15):
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

        # Debug logging to stderr (won't break the eval script JSON parsing)
        print(f"\n[DEBUG] Loop {loop_num + 1}:", file=sys.stderr)
        if content:
            print(f"[DEBUG] Content: {content[:150]}...", file=sys.stderr)

        if msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except:
                    args = {}

                print(f"[DEBUG] Tool Call: {name} {args}", file=sys.stderr)

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
            # Bulletproof JSON extraction: searches for the exact object structure even if wrapped in chat text
            try:
                start_idx = content.find('{"answer"')
                if start_idx == -1:
                    start_idx = content.find('{"answer":')

                if start_idx != -1:
                    end_idx = content.rfind('}')
                    if end_idx > start_idx:
                        final_json = json.loads(content[start_idx:end_idx + 1])
                        break

                # Fallback purely to JSON parse
                final_json = json.loads(content)
                break
            except json.JSONDecodeError:
                pass

            # Nudge the LLM aggressively if it breaks rules
            messages.append(msg)
            messages.append({
                "role": "user",
                "content": "SYSTEM ERROR: You output plain text without calling a tool or providing the final JSON. DO NOT explain your thoughts. EITHER call a tool using the JSON schema OR output the final {\"answer\": \"...\", \"source\": \"...\"} object."
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

    # Final output must be printed to stdout cleanly
    print(json.dumps(final_json))


if __name__ == "__main__":
    main()