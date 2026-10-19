#!/usr/bin/env python3
"""
security_gate.py - PreToolUse Security Gate for Antigravity 2.0
Interprets stdin JSON payload from Antigravity lifecycle hooks,
validates commands against dangerous patterns, prevent malicious execution,
data exfiltration, and unauthorized file system destruction.
"""

import sys
import json
import re

# Blacklist regex patterns for high-risk terminal commands
DANGEROUS_PATTERNS = [
    (r"\brm\s+(-[rfRF]{1,4}\s+)?(/|[a-zA-Z]:\\|~|\.\.)", "Destructive recursive deletion of critical system or parent paths"),
    (r"\bformat\s+[a-zA-Z]:", "Disk format command detected"),
    (r"\bdd\s+if=.*of=/dev/", "Raw disk write command detected"),
    (r"\b(curl|wget)\b.*\|\s*(sh|bash|powershell|cmd|zsh)\b", "Remote pipe execution (curl | bash) detected"),
    (r"\bgit\s+push\b.*(--force|-f)\b", "Force push to git remote can cause code loss"),
    (r"\bgit\s+reset\s+--hard\b", "Hard git reset can permanently discard uncommitted work"),
    (r"\b(mkfs|diskpart|fdisk)\b", "Low-level filesystem modification detected"),
    (r"\b(shutdown|reboot)\b", "System shutdown/reboot command"),
    (r"\b(chmod|icacls)\s+(-R\s+)?777\b", "Insecure global permission granting detected"),
    (r"(cat|type|view)\s+.*(\.env|id_rsa|id_ed25519|secrets?\.(json|ya?ml))", "Attempted direct reading of sensitive credentials"),
]

# Sensitive external network exfiltration indicators
EXFILTRATION_PATTERNS = [
    (r"(curl|wget|nc|ncat|socat)\b.*(@|\$|\.env)", "Possible credential exfiltration in network command"),
]

def analyze_command(command_str: str) -> dict:
    if not command_str:
        return {"decision": "allow"}

    # 1. Check for hard-blocked destructive patterns
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command_str, re.IGNORECASE):
            return {
                "decision": "deny",
                "reason": f"[SECURITY GATE HARD BLOCKED] {reason}: `{command_str}`"
            }

    # 2. Check for suspicious network commands -> escalate to user confirmation
    for pattern, reason in EXFILTRATION_PATTERNS:
        if re.search(pattern, command_str, re.IGNORECASE):
            return {
                "decision": "force_ask",
                "reason": f"[SECURITY GATE WARNING] {reason}. Vui lòng xác nhận trước khi cho phép AI chạy lệnh: `{command_str}`"
            }

    # 3. Safe command
    return {
        "decision": "allow",
        "reason": "Command verified safe by local security gate."
    }

def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "allow"}))
            return

        payload = json.loads(raw_input)
        
        # Tool call arguments
        tool_args = payload.get("toolArgs", {})
        command_line = tool_args.get("CommandLine") or tool_args.get("command") or ""

        result = analyze_command(command_line)
        print(json.dumps(result))
    except Exception as e:
        # In case of validation script failure, fail safely by asking the user
        print(json.dumps({
            "decision": "ask",
            "reason": f"Security gate script encounter error: {str(e)}. Yêu cầu xác nhận từ người dùng."
        }))

if __name__ == "__main__":
    main()
