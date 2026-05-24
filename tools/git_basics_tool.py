#!/usr/bin/env python3
"""Minimal native git tools for small, stable swarm profiles."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple

from tools.registry import registry, tool_error, tool_result

_TOOLSET_NAME = "git_basics"
_DEFAULT_TIMEOUT_SECONDS = 15
_MAX_OUTPUT_CHARS = 12000


def _has_git() -> bool:
    return shutil.which("git") is not None


def _resolve_path(path: str | None) -> Path:
    raw = (path or ".").strip() or "."
    return Path(raw).expanduser().resolve()


def _repo_root(path: Path) -> Path:
    current = path if path.is_dir() else path.parent
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            raise ValueError(f"Not inside a git repository: {path}")
        current = current.parent


def _truncate(text: str) -> Tuple[str, bool]:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text, False
    return text[:_MAX_OUTPUT_CHARS] + "\n... [truncated]", True


def _run_git(repo_root: Path, args: List[str], timeout_seconds: int | None = None) -> dict:
    timeout = timeout_seconds or _DEFAULT_TIMEOUT_SECONDS
    command = ["git", "-C", str(repo_root), *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "GIT_PAGER": "cat"},
        )
    except FileNotFoundError:
        return {"ok": False, "error": "git is not installed", "command": command}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"git command timed out after {timeout}s", "command": command}

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    combined = stdout if stdout else stderr
    truncated_output, truncated = _truncate(combined)
    return {
        "ok": completed.returncode == 0,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "output": truncated_output,
        "truncated": truncated,
    }


def git_status(path: str = ".", timeout_seconds: int | None = None) -> str:
    try:
        repo_root = _repo_root(_resolve_path(path))
    except ValueError as exc:
        return tool_error(str(exc))

    result = _run_git(repo_root, ["status", "--short", "--branch"], timeout_seconds)
    if not result["ok"]:
        return tool_error(result.get("error") or result.get("stderr") or result.get("output") or "git status failed")
    return tool_result({
        "ok": True,
        "repo_root": str(repo_root),
        "command": result["command"],
        "output": result["output"],
        "truncated": result["truncated"],
    })


def git_diff(path: str = ".", staged: bool = False, ref: str = "", timeout_seconds: int | None = None) -> str:
    try:
        repo_root = _repo_root(_resolve_path(path))
    except ValueError as exc:
        return tool_error(str(exc))

    args = ["diff", "--no-ext-diff", "--submodule=short"]
    if staged:
        args.append("--cached")
    if ref.strip():
        args.append(ref.strip())
    result = _run_git(repo_root, args, timeout_seconds)
    if not result["ok"]:
        return tool_error(result.get("error") or result.get("stderr") or result.get("output") or "git diff failed")
    return tool_result({
        "ok": True,
        "repo_root": str(repo_root),
        "command": result["command"],
        "output": result["output"],
        "truncated": result["truncated"],
    })


def git_log(path: str = ".", limit: int = 10, timeout_seconds: int | None = None) -> str:
    try:
        repo_root = _repo_root(_resolve_path(path))
    except ValueError as exc:
        return tool_error(str(exc))

    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 10

    result = _run_git(repo_root, ["log", f"-n{limit}", "--oneline", "--decorate"], timeout_seconds)
    if not result["ok"]:
        return tool_error(result.get("error") or result.get("stderr") or result.get("output") or "git log failed")
    return tool_result({
        "ok": True,
        "repo_root": str(repo_root),
        "command": result["command"],
        "output": result["output"],
        "truncated": result["truncated"],
    })


registry.register(
    name="git_status",
    toolset=_TOOLSET_NAME,
    schema={
        "name": "git_status",
        "description": "Show concise git status for the repository containing the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File or directory inside the target git repository."},
                "timeout_seconds": {"type": "integer", "description": "Optional timeout in seconds (default 15)."},
            },
        },
    },
    handler=lambda args, **_: git_status(
        path=args.get("path", "."),
        timeout_seconds=args.get("timeout_seconds"),
    ),
    check_fn=_has_git,
    emoji="🌿",
)

registry.register(
    name="git_diff",
    toolset=_TOOLSET_NAME,
    schema={
        "name": "git_diff",
        "description": "Show concise git diff for the repository containing the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File or directory inside the target git repository."},
                "staged": {"type": "boolean", "description": "When true, show staged changes instead of unstaged."},
                "ref": {"type": "string", "description": "Optional git ref/revspec to diff against."},
                "timeout_seconds": {"type": "integer", "description": "Optional timeout in seconds (default 15)."},
            },
        },
    },
    handler=lambda args, **_: git_diff(
        path=args.get("path", "."),
        staged=bool(args.get("staged", False)),
        ref=args.get("ref", ""),
        timeout_seconds=args.get("timeout_seconds"),
    ),
    check_fn=_has_git,
    emoji="🧾",
)

registry.register(
    name="git_log",
    toolset=_TOOLSET_NAME,
    schema={
        "name": "git_log",
        "description": "Show recent git commits for the repository containing the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File or directory inside the target git repository."},
                "limit": {"type": "integer", "description": "Maximum number of commits to show (1-50, default 10)."},
                "timeout_seconds": {"type": "integer", "description": "Optional timeout in seconds (default 15)."},
            },
        },
    },
    handler=lambda args, **_: git_log(
        path=args.get("path", "."),
        limit=args.get("limit", 10),
        timeout_seconds=args.get("timeout_seconds"),
    ),
    check_fn=_has_git,
    emoji="🕰️",
)
