# Agent Documentation

## Overview
This repository contains a Python-based Command Line Interface (CLI) agent built for Lab 6. In its current implementation (Task 1), it functions as a direct Question-and-Answer tool that connects to a Large Language Model (LLM) to provide answers to user prompts.

## How the Agent Works
The agent operates through a straightforward pipeline without an agentic loop or external tool use (which will be introduced in later tasks):
1. **Input Parsing:** The agent accepts a single question as a command-line argument.
2. **Environment Loading:** It securely loads the API credentials and endpoint configuration from a local `.env.agent.secret` file.
3. **API Request:** It constructs a standard OpenAI-compatible JSON payload and sends a `POST` request to the configured LLM endpoint.
4. **Execution & Timeout:** The agent waits for the LLM's response, enforcing a strict 60-second timeout limit to prevent hanging.
5. **Output Formatting:** The agent extracts the assistant's text and formats it into a strict JSON structure. 
6. **Stream Separation:** To ensure the output is machine-readable, the valid JSON is printed exclusively to `stdout`, while all errors, debug information, or environment logs are routed to `stderr`.

## LLM Provider Configuration
This agent is configured to use the **Qwen Code API**, self-hosted on a remote university virtual machine via an OpenAI-compatible proxy.

* **Provider:** Qwen Code API
* **Model:** `qwen3-coder-plus`
* **Network:** Hosted on VM IP `10.93.25.214` at port `42005`.

## Usage Instructions

 


To execute the agent, use the `uv` package manager from the root of the project repository:

```bash
uv run agent.py "What does REST stand for?"