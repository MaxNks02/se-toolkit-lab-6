import sys
import json
import os
import urllib.request
import urllib.error
from dotenv import load_dotenv


def main():
    # 1. Parse input: Get the question from the first command-line argument
    if len(sys.argv) < 2:
        sys.stderr.write("Error: Please provide a question as a command-line argument.\n")
        sys.exit(1)

    question = sys.argv[1]

    # 2. Load configuration from .env.agent.secret
    load_dotenv('.env.agent.secret')
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not all([api_key, api_base, model]):
        sys.stderr.write("Error: Missing LLM configuration in .env.agent.secret\n")
        sys.exit(1)

    # 3. Construct the API request payload
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}]
    }

    # 4. Execute the request and format the output
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        # Enforce the 60-second timeout rule
        with urllib.request.urlopen(req, timeout=60) as response:
            response_body = response.read().decode('utf-8')
            response_data = json.loads(response_body)

            # Extract the actual text answer from the LLM response
            answer_content = response_data["choices"][0]["message"]["content"]

            # Build the strict JSON output
            output = {
                "answer": answer_content,
                "tool_calls": []
            }

            # Print ONLY valid JSON to stdout
            print(json.dumps(output))
            sys.exit(0)

    except Exception as e:
        # Send any crashes or debug information strictly to stderr
        sys.stderr.write(f"Error calling LLM API: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()