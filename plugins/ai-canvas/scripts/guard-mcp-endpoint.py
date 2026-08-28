#!/usr/bin/env python3
"""PreToolUse guard: AI-Canvas sites are driven only through their MCP tools.

Denies Bash commands and file writes that talk to an ai-canvas MCP endpoint
(.../wp-json/ai-canvas/mcp) directly over HTTP. This is the failure mode where
an agent, finding the MCP tools unavailable mid-session, rebuilds the
connection out of curl and stored credentials instead of asking the user to
reconnect (/mcp) or restart the session.

Allowed on purpose:
- the setup skill's unauthenticated status probe (curl to the endpoint with no
  auth, headers, body, or method override)
- `claude mcp ...` registration and management commands
- Markdown/text files, which legitimately quote these commands as docs

The guard fails open: any unexpected input is allowed through rather than
blocking unrelated work.
"""

import json
import re
import sys

ENDPOINT = re.compile(r"wp-json/ai-canvas/mcp|rest_route=/?ai-canvas/mcp", re.I)

# Anything that turns a mention of the endpoint into an authenticated or
# protocol-level request: auth flags, custom headers, request bodies, method
# overrides, MCP protocol strings, or an HTTP library standing in for curl.
BASH_INDICATORS = re.compile(
    r"(^|\s)-(u|H|d|X)\s"
    r"|--(user|header|data|data-raw|data-binary|data-urlencode|json|request|basic|anyauth|oauth2-bearer)\b"
    r"|authorization"
    r"|jsonrpc|tools/call"
    r"|urllib|requests\.|http\.client|fetch\(|axios|net/http|curl_init",
    re.I,
)

# For file content (helper scripts): the endpoint plus anything that makes or
# authenticates an HTTP request to it.
CONTENT_INDICATORS = re.compile(
    r"authorization|jsonrpc|tools/call"
    r"|--user\b|(^|\s)-u\s|basic\s+[A-Za-z0-9+/=]{8,}"
    r"|curl|wget|urllib|requests\.|http\.client|fetch\(|axios|net/http|curl_init",
    re.I | re.M,
)

DOC_EXTENSIONS = (".md", ".markdown", ".mdx", ".txt")

REASON = (
    "AI-Canvas sites are driven only through their MCP tools "
    "(mcp__<server>__ai-canvas-*), never by calling the /wp-json/ai-canvas/mcp "
    "endpoint directly over HTTP. If those tools are missing from this session, "
    "the server was registered or changed after the session started — MCP "
    "servers load at session start. Ask the user to run /mcp to reconnect, or "
    "to restart the session, then continue through the MCP tools. Do not retry "
    "this over HTTP with curl, helper scripts, or libraries, and do not extract "
    "stored credentials from the MCP config."
)


def deny() -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON,
                },
                "systemMessage": "ai-canvas guard: direct HTTP access to an AI-Canvas MCP endpoint was blocked; use the MCP tools (reconnect via /mcp or a session restart if they are missing).",
            }
        )
    )
    sys.exit(0)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input") or {}
    except Exception:
        sys.exit(0)

    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        if not ENDPOINT.search(command):
            sys.exit(0)
        if "claude mcp" in command:
            sys.exit(0)
        if BASH_INDICATORS.search(command):
            deny()
        sys.exit(0)

    if tool_name in ("Write", "Edit"):
        file_path = str(tool_input.get("file_path", ""))
        if file_path.lower().endswith(DOC_EXTENSIONS):
            sys.exit(0)
        content = str(tool_input.get("content") or tool_input.get("new_string") or "")
        if ENDPOINT.search(content) and CONTENT_INDICATORS.search(content):
            deny()
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
