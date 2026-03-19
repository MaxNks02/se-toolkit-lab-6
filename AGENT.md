# Agent Architecture: The System Agent Evolution

## 1. Overview and Evolution
Originally designed as a specialized tool for navigating project documentation, the agent has evolved into a **System Agent**. This transition allows the agent to move beyond static wiki files and interact directly with the "source of truth"—the live, running backend system. By bridging the gap between documentation and real-time state, the agent can provide accurate answers regarding system facts and data-dependent queries.

## 2. The `query_api` Tool and Authentication
The core addition for Task 3 is the `query_api` tool. 
* **Functionality**: This tool enables the agent to perform authenticated HTTP requests to the backend API to retrieve live data, such as item counts or status codes. 
* **Authentication**: Security is strictly maintained using the `LMS_API_KEY` loaded from the `.env.docker.secret` file. 
* **Headers**: Every request includes an Authorization: Bearer header to authenticate with the backend, ensuring that only authorized agent actions are performed.
* **Base URL**: The agent dynamically resolves the target environment using the `AGENT_API_BASE_URL` variable, which defaults to `http://localhost:42002` but is easily configurable for VM deployments.

## 3. Tool Selection and Decision Logic
The agent utilizes a refined system prompt to manage its expanded toolkit effectively. 
* **Heuristics**: The LLM is instructed to use `read_file` or `list_files` for procedural questions found in the wiki or for static source code analysis, such as identifying the web framework. 
* **Live Queries**: For questions involving "how many," current status codes, or live system facts, the LLM is prompted to prioritize the `query_api` tool.
* **Diagnostic Chaining**: For troubleshooting, the agent employs multi-step reasoning. It first calls `query_api` to identify a live error (such as a `ZeroDivisionError`) and then uses `read_file` on the source code to find the exact buggy line and explain the cause.

## 4. Benchmark Lessons and Iteration
Benchmarking the agent using `run_eval.py` provided several key insights into agentic stability. 
* **Defensive Parsing**: We implemented logic to handle `null` content responses from the LLM during tool calls, a common issue when the model prioritizes function arguments over text content. 
* **Context Windows**: Large file reads were truncated to 4,000–10,000 characters to prevent the LLM from losing focus or triggering provider-side "Operation not allowed" errors.
* **Tool Misuse**: Early failures showed the LLM sometimes attempted to use documentation tools for live data. Refining the tool descriptions in the JSON schemas was necessary to clarify the "source of truth" for the model.

> **Final Evaluation Score**: 10/10