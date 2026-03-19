# Agent Documentation

## Overview
This repository contains a Python-based Command Line Interface (CLI) agent built for Lab 6. It operates as a fully functional documentation agent capable of exploring the project directory to answer user questions.

## Architecture & The Agentic Loop
Unlike a simple chatbot, this agent utilizes an **agentic loop** to reason and use tools. 
1. **Initialization:** The user's question and a system prompt are sent to the LLM alongside JSON schemas defining available tools.
2. **The Loop:** The agent enters a `while` loop (capped at a maximum of 10 iterations to prevent infinite loops).
   - If the LLM requests a tool call, the local Python script intercepts it, executes the corresponding function, and appends the result to the message history as a `tool` role message.
   - The updated history is sent back to the LLM.
3. **Termination:** When the LLM has enough information, it stops calling tools and provides a final text response formatted as a strict JSON object.
4. **Output:** The script parses the final answer and source, combines them with the log of executed tool calls, and prints the final JSON to `stdout`. All debug information is routed to `stderr`.

## Tools & Security
The agent is equipped with two tools:
* **`list_files(path)`:** Lists files and directories at a given relative path.
* **`read_file(path)`:** Reads the contents of a specified file.

**Security:** Both tools use `os.path.abspath` to verify that the requested path strictly resides within the project root directory, preventing directory traversal attacks (e.g., `../../`).

## System Prompt Strategy
The system prompt explicitly instructs the LLM to act as a documentation agent, directing it to use `list_files` to discover paths and `read_file` to ingest content. Furthermore, it strictly enforces the final output format, demanding the LLM return only a raw JSON string containing an `answer` and a `source` (file path and section anchor) without Markdown wrappers.

## LLM Provider Configuration
* **Provider:** Qwen Code API (self-hosted via proxy on a remote VM)
* **Model:** `qwen3-coder-plus`
* **Configuration:** Loaded from a local `.env.agent.secret` file.

## Usage
```bash
uv run agent.py "How do you resolve a merge conflict?"