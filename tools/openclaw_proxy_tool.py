#!/usr/bin/env python3
"""Thin OpenClaw bridge tools for swarm profiles.

This bypasses Hermes's optional MCP dependency and calls the standalone
openclaw bridge directly in its CLI mode. The result is a tiny, practical
proxy surface (whole-turn delegation + history inspection) without exposing
full Hermes tools inside swarm1.
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_cli.config import load_config
from tools.file_tools import search_tool
from tools.registry import registry, tool_error, tool_result

_REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)
_DEFAULT_NODE = "/Users/aurora/.nvm/versions/node/v22.22.0/bin/node"
_DEFAULT_BRIDGE_SCRIPT = str(_REAL_HOME / ".local/share/hermes-openclaw-bridge/server.mjs")
_DEFAULT_GATEWAY_URL = "ws://127.0.0.1:18789"
_DEFAULT_PROFILE = "swarm1"
_DEFAULT_TIMEOUT_SECONDS = 300
_DEFAULT_GIT_TIMEOUT_SECONDS = 30
_TOOLSET_NAME = "openclaw_proxy"


def _bridge_config() -> Dict[str, Any]:
    try:
        config = load_config() or {}
    except Exception:
        config = {}
    servers = config.get("mcp_servers") or {}
    bridge = servers.get("openclaw_bridge") or {}
    return bridge if isinstance(bridge, dict) else {}


def _bridge_env_defaults() -> Dict[str, str]:
    env = _bridge_config().get("env") or {}
    return env if isinstance(env, dict) else {}


def _resolve_node_command() -> str:
    cfg = _bridge_config()
    command = str(cfg.get("command") or "").strip()
    if command and ((os.path.isabs(command) and os.path.exists(command)) or shutil.which(command)):
        return command
    if os.path.exists(_DEFAULT_NODE):
        return _DEFAULT_NODE
    return shutil.which("node") or "node"


def _resolve_bridge_script() -> str:
    cfg = _bridge_config()
    args = cfg.get("args") or []
    if isinstance(args, list) and args:
        script = str(args[0]).strip()
        if script and os.path.exists(script):
            return script
    return _DEFAULT_BRIDGE_SCRIPT


def _resolve_timeout_seconds(timeout_seconds: Optional[int]) -> int:
    cfg = _bridge_config()
    raw = timeout_seconds or cfg.get("timeout") or _DEFAULT_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = _DEFAULT_TIMEOUT_SECONDS
    return max(5, value)


def _resolve_runtime(
    *,
    profile: Optional[str] = None,
    gateway_url: Optional[str] = None,
    gateway_token: Optional[str] = None,
) -> Dict[str, str]:
    env_defaults = _bridge_env_defaults()
    env = os.environ.copy()
    env["OPENCLAW_GATEWAY_URL"] = (
        gateway_url
        or env_defaults.get("OPENCLAW_GATEWAY_URL")
        or env.get("OPENCLAW_GATEWAY_URL")
        or _DEFAULT_GATEWAY_URL
    )
    env["OPENCLAW_BRIDGE_PROFILE"] = (
        profile
        or env_defaults.get("OPENCLAW_BRIDGE_PROFILE")
        or env.get("OPENCLAW_BRIDGE_PROFILE")
        or _DEFAULT_PROFILE
    )
    token = (
        gateway_token
        or env_defaults.get("OPENCLAW_GATEWAY_TOKEN")
        or env.get("OPENCLAW_GATEWAY_TOKEN")
    )
    if token:
        env["OPENCLAW_GATEWAY_TOKEN"] = token
    return env


def _extract_assistant_text(payload: Dict[str, Any]) -> str:
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""

    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, list):
            chunks: List[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    block_text = block.get("text")
                    if isinstance(block_text, str) and block_text:
                        chunks.append(block_text)
            combined = "\n".join(chunk for chunk in chunks if chunk).strip()
            if combined:
                return combined
    return ""


def _run_bridge(
    bridge_args: List[str],
    *,
    profile: Optional[str] = None,
    gateway_url: Optional[str] = None,
    gateway_token: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    command = [_resolve_node_command(), _resolve_bridge_script(), *bridge_args]
    env = _resolve_runtime(
        profile=profile,
        gateway_url=gateway_url,
        gateway_token=gateway_token,
    )
    timeout = _resolve_timeout_seconds(timeout_seconds)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"OpenClaw bridge dependency missing: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"OpenClaw bridge timed out after {timeout}s") from exc

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if completed.returncode != 0:
        detail = stderr or stdout or f"exit {completed.returncode}"
        raise RuntimeError(f"OpenClaw bridge failed: {detail}")

    if not stdout:
        raise RuntimeError("OpenClaw bridge returned empty stdout")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        snippet = stdout[:400]
        raise RuntimeError(f"OpenClaw bridge returned invalid JSON: {snippet}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("OpenClaw bridge returned a non-object payload")

    if stderr:
        payload.setdefault("stderr", stderr)
    return payload


def openclaw_turn(
    prompt: str,
    *,
    session_key: Optional[str] = None,
    profile: Optional[str] = None,
    gateway_url: Optional[str] = None,
    gateway_token: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return tool_error("prompt is required")

    bridge_args = ["--turn", prompt]
    if session_key:
        bridge_args.extend(["--session", session_key])

    try:
        payload = _run_bridge(
            bridge_args,
            profile=profile,
            gateway_url=gateway_url,
            gateway_token=gateway_token,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return tool_error(str(exc))

    return tool_result({
        "ok": True,
        "assistant_text": _extract_assistant_text(payload),
        "session_key": payload.get("sessionKey") or session_key,
        "run_id": payload.get("runId"),
        "wait": payload.get("wait"),
        "message_count": len(payload.get("messages") or []),
        "raw": payload,
    })


def openclaw_history(
    *,
    session_key: Optional[str] = None,
    profile: Optional[str] = None,
    gateway_url: Optional[str] = None,
    gateway_token: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    limit: int = 20,
) -> str:
    try:
        limit = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        limit = 20

    bridge_args = ["--history"]
    if session_key:
        bridge_args.extend(["--session", session_key])

    try:
        payload = _run_bridge(
            bridge_args,
            profile=profile,
            gateway_url=gateway_url,
            gateway_token=gateway_token,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return tool_error(str(exc))

    messages = payload.get("messages")
    if isinstance(messages, list):
        payload["messages"] = messages[-limit:]

    return tool_result({
        "ok": True,
        "assistant_text": _extract_assistant_text(payload),
        "session_key": payload.get("sessionKey") or session_key,
        "message_count": len(payload.get("messages") or []),
        "raw": payload,
    })


def openclaw_search_files(
    pattern: str,
    *,
    path: str = ".",
    target: str = "content",
    file_glob: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    output_mode: str = "content",
    context: int = 0,
    profile: Optional[str] = None,
) -> str:
    pattern = (pattern or "").strip()
    if not pattern:
        return tool_error("pattern is required")

    task_id = f"openclaw_proxy:{profile or _DEFAULT_PROFILE}"
    return search_tool(
        pattern=pattern,
        target=target,
        path=path,
        file_glob=file_glob,
        limit=limit,
        offset=offset,
        output_mode=output_mode,
        context=context,
        task_id=task_id,
    )


def openclaw_git_status(
    path: str = ".",
    *,
    timeout_seconds: Optional[int] = None,
) -> str:
    repo_path = str(Path(path).expanduser())
    timeout = _DEFAULT_GIT_TIMEOUT_SECONDS
    if timeout_seconds is not None:
        try:
            timeout = max(5, int(timeout_seconds))
        except (TypeError, ValueError):
            timeout = _DEFAULT_GIT_TIMEOUT_SECONDS

    try:
        completed = subprocess.run(
            ["/usr/bin/git", "-C", repo_path, "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return tool_error(f"git not available: {exc}")
    except subprocess.TimeoutExpired:
        return tool_error(f"git status timed out after {timeout}s")

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0:
        return tool_error(stderr or stdout or f"git status failed with exit {completed.returncode}")

    lines = [line for line in stdout.splitlines() if line]
    return tool_result({
        "ok": True,
        "path": repo_path,
        "branch": lines[0] if lines else "",
        "entries": lines[1:],
        "entry_count": max(0, len(lines) - 1),
        "stdout": stdout,
    })


def check_openclaw_proxy_requirements() -> bool:
    node = _resolve_node_command()
    script = _resolve_bridge_script()
    node_exists = os.path.isabs(node) and os.path.exists(node)
    if not node_exists:
        node_exists = shutil.which(node) is not None
    return node_exists and os.path.exists(script)


OPENCLAW_TURN_SCHEMA = {
    "name": "openclaw_turn",
    "description": (
        "Delegate a whole turn into the thin OpenClaw proxy. Use this when swarm1 "
        "should think/respond through the OpenClaw-backed session instead of using Hermes tools directly."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The exact turn to send into OpenClaw.",
            },
            "session_key": {
                "type": "string",
                "description": "Optional session key override. Omit to use the profile default bridge session.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Optional timeout override in seconds.",
            },
        },
        "required": ["prompt"],
    },
}

OPENCLAW_HISTORY_SCHEMA = {
    "name": "openclaw_history",
    "description": (
        "Inspect the recent message history for the current thin OpenClaw proxy session. "
        "Useful for steering, checking worker state, or confirming what OpenClaw last said."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_key": {
                "type": "string",
                "description": "Optional session key override. Omit to use the profile default bridge session.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of recent messages to return (default 20, max 200).",
                "default": 20,
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Optional timeout override in seconds.",
            },
        },
        "required": [],
    },
}

OPENCLAW_SEARCH_FILES_SCHEMA = {
    "name": "openclaw_search_files",
    "description": (
        "Search local files from the thin OpenClaw proxy surface without exposing the full Hermes file toolset. "
        "Use for filename discovery or regex search when swarm1 needs a tiny workspace lookup capability."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern for content search, or glob pattern for file search.",
            },
            "target": {
                "type": "string",
                "enum": ["content", "files"],
                "description": "Search inside file contents or find files by name.",
                "default": "content",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in.",
                "default": ".",
            },
            "file_glob": {
                "type": "string",
                "description": "Optional file filter for content search, like '*.py'.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "default": 20,
            },
            "offset": {
                "type": "integer",
                "description": "Skip the first N results.",
                "default": 0,
            },
            "output_mode": {
                "type": "string",
                "enum": ["content", "files_only", "count"],
                "description": "Output format for content searches.",
                "default": "content",
            },
            "context": {
                "type": "integer",
                "description": "Context lines around content matches.",
                "default": 0,
            },
        },
        "required": ["pattern"],
    },
}

OPENCLAW_GIT_STATUS_SCHEMA = {
    "name": "openclaw_git_status",
    "description": (
        "Read-only git status from the thin OpenClaw proxy surface. "
        "Use this for a tiny repo-state check without exposing the full terminal toolset."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository path to inspect.",
                "default": ".",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Optional timeout override in seconds.",
                "default": 30,
            },
        },
        "required": [],
    },
}


registry.register(
    name="openclaw_turn",
    toolset=_TOOLSET_NAME,
    schema=OPENCLAW_TURN_SCHEMA,
    handler=lambda args, **kw: openclaw_turn(
        prompt=args.get("prompt", ""),
        session_key=args.get("session_key"),
        timeout_seconds=args.get("timeout_seconds"),
    ),
    check_fn=check_openclaw_proxy_requirements,
    emoji="🧵",
)

registry.register(
    name="openclaw_history",
    toolset=_TOOLSET_NAME,
    schema=OPENCLAW_HISTORY_SCHEMA,
    handler=lambda args, **kw: openclaw_history(
        session_key=args.get("session_key"),
        limit=args.get("limit", 20),
        timeout_seconds=args.get("timeout_seconds"),
    ),
    check_fn=check_openclaw_proxy_requirements,
    emoji="🪶",
)

registry.register(
    name="openclaw_search_files",
    toolset=_TOOLSET_NAME,
    schema=OPENCLAW_SEARCH_FILES_SCHEMA,
    handler=lambda args, **kw: openclaw_search_files(
        pattern=args.get("pattern", ""),
        target=args.get("target", "content"),
        path=args.get("path", "."),
        file_glob=args.get("file_glob"),
        limit=args.get("limit", 20),
        offset=args.get("offset", 0),
        output_mode=args.get("output_mode", "content"),
        context=args.get("context", 0),
    ),
    check_fn=check_openclaw_proxy_requirements,
    emoji="🗂️",
)

registry.register(
    name="openclaw_git_status",
    toolset=_TOOLSET_NAME,
    schema=OPENCLAW_GIT_STATUS_SCHEMA,
    handler=lambda args, **kw: openclaw_git_status(
        path=args.get("path", "."),
        timeout_seconds=args.get("timeout_seconds"),
    ),
    check_fn=check_openclaw_proxy_requirements,
    emoji="🌿",
)
