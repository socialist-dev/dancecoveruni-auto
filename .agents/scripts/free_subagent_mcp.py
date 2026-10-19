#!/usr/bin/env python3
"""
free_subagent_mcp.py - Free Multi-Model Subagent Bridge with Auto-Fallback Engine
Implements a lightweight Model Context Protocol (MCP) server over standard I/O for Antigravity 2.0.
Features:
- Supports Google AI Studio Free Tier models (Gemini 3.5 Flash Lite [500 RPD], Gemma 4 31B [14.4K RPD], Gemini 3.8 Flash)
- Supports NVIDIA NIM Open Source models (Qwen 3.8 Coder, Llama 3.3 70B, DeepSeek-R1)
- Multi-tier Auto-Fallback Engine: Automatically retries and falls back on HTTP 429 (Rate Limit / Quota Exceeded)
Zero external dependencies (uses standard library urllib).
"""

import sys
import json
import os
import time
import urllib.request
import urllib.error

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Fallback sequence for Google AI Studio models based on quota priority
GEMINI_FALLBACK_CHAIN = [
    "gemini-3.8-flash",       # High intelligence (5 RPM / 20 RPD)
    "gemini-3.5-flash-lite",  # High speed, generous quota (15 RPM / 500 RPD)
    "gemini-3.1-flash-lite",  # Secondary generous quota (15 RPM / 500 RPD)
    "gemma-4-31b",            # Massive quota workhorse (30 RPM / 14,400 RPD)
    "gemma-4-26b"             # Ultra fallback (30 RPM / 14,400 RPD)
]

# Fallback sequence for NVIDIA NIM models
NVIDIA_FALLBACK_CHAIN = [
    "qwen/qwen3.8-coder-32b-instruct",
    "qwen/qwen2.5-coder-32b-instruct",
    "meta/llama-3.3-70b-instruct",
    "deepseek-ai/deepseek-r1"
]

def call_nvidia_nim_raw(prompt: str, model: str, system_instruction: str = "You are a specialized code subagent.") -> tuple:
    if not NVIDIA_API_KEY:
        return False, "[CONFIG ERROR] NVIDIA_API_KEY is not set."
    
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4096
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {NVIDIA_API_KEY}"
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return True, res_data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        is_rate_limit = (e.code == 429 or "rate" in error_body.lower() or "quota" in error_body.lower())
        return False, f"[HTTP {e.code}] RateLimit={is_rate_limit} Body={error_body}"
    except Exception as e:
        return False, f"[CONNECTION ERROR] {str(e)}"

def call_gemini_raw(prompt: str, model: str, system_instruction: str = "You are a helpful coding assistant.") -> tuple:
    if not GEMINI_API_KEY:
        return False, "[CONFIG ERROR] GEMINI_API_KEY is not set."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"System Context: {system_instruction}\n\nTask: {prompt}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096
        }
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                return True, candidates[0]["content"]["parts"][0]["text"]
            return False, "[EMPTY] No response candidate returned."
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        is_rate_limit = (e.code == 429 or "rate" in error_body.lower() or "quota" in error_body.lower())
        return False, f"[HTTP {e.code}] RateLimit={is_rate_limit} Body={error_body}"
    except Exception as e:
        return False, f"[CONNECTION ERROR] {str(e)}"

def execute_with_auto_fallback(prompt: str, preferred_provider: str = "gemini", preferred_model: str = "") -> str:
    """
    Executes prompt with graceful multi-tier fallback:
    1. Try preferred model with 1 backoff retry.
    2. Fallback to high-quota models within the same provider (e.g. Gemini 3.5 Flash Lite -> Gemma 4 31B [14.4k RPD]).
    3. Cross-provider fallback (Gemini -> Nvidia or Nvidia -> Gemini).
    """
    fallback_logs = []
    
    # Tier 1 & 2: Same-provider chain
    if preferred_provider == "gemini":
        model_queue = [preferred_model] if preferred_model else []
        model_queue.extend([m for m in GEMINI_FALLBACK_CHAIN if m not in model_queue])
        
        for m in model_queue:
            success, result = call_gemini_raw(prompt, model=m)
            if success:
                if fallback_logs:
                    return f"[NOTE: Executed via Fallback Model '{m}' due to previous limits: {'; '.join(fallback_logs)}]\n\n" + result
                return result
            else:
                fallback_logs.append(f"Gemini({m}): {result[:80]}")
                time.sleep(1) # brief cooling delay
        
        # Cross-provider fallback to NVIDIA NIM
        if NVIDIA_API_KEY:
            fallback_logs.append("Attempting Cross-Provider Fallback to NVIDIA NIM...")
            for nm in NVIDIA_FALLBACK_CHAIN:
                success, result = call_nvidia_nim_raw(prompt, model=nm)
                if success:
                    return f"[NOTE: Cross-Provider Fallback to NVIDIA NIM '{nm}' successful]\n\n" + result
                fallback_logs.append(f"NVIDIA({nm}): {result[:80]}")
                
    else: # preferred_provider == "nvidia"
        model_queue = [preferred_model] if preferred_model else []
        model_queue.extend([m for m in NVIDIA_FALLBACK_CHAIN if m not in model_queue])
        
        for m in model_queue:
            success, result = call_nvidia_nim_raw(prompt, model=m)
            if success:
                if fallback_logs:
                    return f"[NOTE: Executed via Fallback Model '{m}' due to previous limits]\n\n" + result
                return result
            else:
                fallback_logs.append(f"NVIDIA({m}): {result[:80]}")
                time.sleep(1)
                
        # Cross-provider fallback to Gemini
        if GEMINI_API_KEY:
            fallback_logs.append("Attempting Cross-Provider Fallback to Gemini 3.5 Flash Lite...")
            for gm in GEMINI_FALLBACK_CHAIN:
                success, result = call_gemini_raw(prompt, model=gm)
                if success:
                    return f"[NOTE: Cross-Provider Fallback to Gemini '{gm}' successful]\n\n" + result
                fallback_logs.append(f"Gemini({gm}): {result[:80]}")

    return "[ALL FREE SUBAGENT TIERS EXHAUSTED / FAILED]\nLogs:\n" + "\n".join(fallback_logs)

# JSON-RPC 2.0 / MCP Protocol Handler
def handle_rpc_request(req):
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "free-subagents-resilient-bridge",
                    "version": "2.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "ask_free_subagent",
                        "description": "Delegates tasks to FREE external models (Gemini 3.5 Flash Lite [500 RPD], Gemma 4 31B [14.4k RPD], Qwen 3.8 Coder, Llama 3.3) with built-in AUTO-FALLBACK to bypass rate limits (429).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task_description": {
                                    "type": "string",
                                    "description": "Detailed task or prompt for the subagent to perform"
                                },
                                "provider": {
                                    "type": "string",
                                    "enum": ["gemini", "nvidia"],
                                    "default": "gemini",
                                    "description": "Preferred provider: 'gemini' (AI Studio) or 'nvidia' (NVIDIA NIM)"
                                },
                                "model_name": {
                                    "type": "string",
                                    "description": "Specific model name (optional, auto-fallback will route if omitted or rate-limited)"
                                }
                            },
                            "required": ["task_description"]
                        }
                    }
                ]
            }
        }
        
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "ask_free_subagent":
            task = args.get("task_description", "")
            provider = args.get("provider", "gemini").lower()
            model_name = args.get("model_name", "")
            
            output_text = execute_with_auto_fallback(task, preferred_provider=provider, preferred_model=model_name)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": output_text}]
                }
            }
            
    return {"jsonrpc": "2.0", "id": req_id, "result": {}}

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_rpc_request(req)
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)}
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
