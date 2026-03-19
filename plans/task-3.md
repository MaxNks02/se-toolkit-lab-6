# Task 3 Implementation Plan: The System Agent

## 1. Tool Definition: `query_api`
I will implement a new tool called `query_api` to allow the agent to interact with the live backend. 
* **Functionality**: The tool will send HTTP requests to the deployed API to fetch system facts and live data.
* **Parameters**: 
    * `method`: The HTTP verb (GET, POST, etc.).
    * `path`: The specific endpoint relative to the base URL.
    * `body`: An optional JSON string for request data.
* **Implementation**: I will use Python's `urllib.request` library to handle the calls without adding new external dependencies.

## 2. Authentication and Environment Handling
The agent must be fully configurable via environment variables to pass the autochecker.
* **API Keys**: `LLM_API_KEY` will be loaded from `.env.agent.secret`, while `LMS_API_KEY` will be loaded from `.env.docker.secret`.
* **Base URL**: The agent will use `AGENT_API_BASE_URL`, defaulting to `http://localhost:42002` if the variable is not provided.
* **Headers**: Every API call will include the `X-API-Key` header populated by `LMS_API_KEY`.

## 3. Agentic Logic and System Prompt
The system prompt will be updated to transform the agent from a documentation reader into a system troubleshooter.
* **Tool Selection**: The LLM will be instructed to use `read_file` for static code/wiki questions and `query_api` for any question regarding the "current" state or "live" data.
* **Chaining Tools**: For bug diagnosis (questions 6 and 7 in the benchmark), the agent will be prompted to first call `query_api` to identify an error (like a 500 status code) and then use `read_file` on the source code to find the root cause.

## 4. Benchmark and Iteration Strategy
I will use the `run_eval.py` script to test the agent against the 10 required questions.
* **Initial Score**: 0/10 (Starting baseline).
* **First Failures**: I anticipate initial issues with the LLM providing incorrect paths (e.g., missing leading slashes) or failing to provide the `LMS_API_KEY` correctly.
* **Refinement**: I will analyze the "feedback hint" provided by the evaluation script for every failing question and refine the tool descriptions in the JSON schema to clarify parameter requirements.