import json
from types import SimpleNamespace
from unittest.mock import patch



def _completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_openclaw_turn_uses_profile_bridge_defaults_and_extracts_text():
    import tools.openclaw_proxy_tool as bridge

    payload = {
        "sessionKey": "hermes-bridge-swarm1",
        "runId": "run-123",
        "text": "",
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "ping"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": ""},
                    {"type": "text", "text": "pong"},
                ],
            },
        ],
        "wait": {"status": "ok"},
    }

    config = {
        "mcp_servers": {
            "openclaw_bridge": {
                "command": "/custom/node",
                "args": ["/custom/server.mjs"],
                "env": {
                    "OPENCLAW_GATEWAY_URL": "ws://test-gateway:18789",
                    "OPENCLAW_BRIDGE_PROFILE": "swarm1",
                },
            }
        }
    }

    real_exists = bridge.os.path.exists

    def fake_exists(path):
        return path in {"/custom/node", "/custom/server.mjs"} or real_exists(path)

    with patch.object(bridge, "load_config", return_value=config), \
         patch.object(bridge.os.path, "exists", side_effect=fake_exists), \
         patch.object(bridge.shutil, "which", return_value="/custom/node"), \
         patch.object(bridge.subprocess, "run", return_value=_completed(json.dumps(payload))) as mock_run:
        result = json.loads(bridge.openclaw_turn("ping"))

    assert result["ok"] is True
    assert result["assistant_text"] == "pong"
    assert result["session_key"] == "hermes-bridge-swarm1"

    command = mock_run.call_args.args[0]
    env = mock_run.call_args.kwargs["env"]
    assert command == ["/custom/node", "/custom/server.mjs", "--turn", "ping"]
    assert env["OPENCLAW_GATEWAY_URL"] == "ws://test-gateway:18789"
    assert env["OPENCLAW_BRIDGE_PROFILE"] == "swarm1"


def test_openclaw_history_trims_messages_to_limit():
    import tools.openclaw_proxy_tool as bridge

    payload = {
        "sessionKey": "hermes-bridge-swarm1",
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "one"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "two"}]},
            {"role": "user", "content": [{"type": "text", "text": "three"}]},
        ],
    }

    with patch.object(bridge.subprocess, "run", return_value=_completed(json.dumps(payload))):
        result = json.loads(bridge.openclaw_history(limit=2))

    assert result["ok"] is True
    assert result["message_count"] == 2
    assert result["raw"]["messages"][0]["content"][0]["text"] == "two"
    assert result["raw"]["messages"][1]["content"][0]["text"] == "three"


def test_openclaw_turn_returns_tool_error_on_bridge_failure():
    import tools.openclaw_proxy_tool as bridge

    with patch.object(
        bridge.subprocess,
        "run",
        return_value=_completed("", returncode=1, stderr="bridge exploded"),
    ):
        result = json.loads(bridge.openclaw_turn("ping"))

    assert "error" in result
    assert "bridge exploded" in result["error"]


def test_openclaw_search_files_uses_masked_task_id_and_forwards_args():
    import tools.openclaw_proxy_tool as bridge

    expected = {"total_count": 1, "files": ["tools/openclaw_proxy_tool.py"]}

    with patch.object(bridge, "search_tool", return_value=json.dumps(expected)) as mock_search:
        result = json.loads(
            bridge.openclaw_search_files(
                "openclaw_proxy",
                target="files",
                path="tools",
                limit=5,
                offset=2,
                profile="swarm1",
            )
        )

    assert result == expected
    mock_search.assert_called_once_with(
        pattern="openclaw_proxy",
        target="files",
        path="tools",
        file_glob=None,
        limit=5,
        offset=2,
        output_mode="content",
        context=0,
        task_id="openclaw_proxy:swarm1",
    )


def test_openclaw_search_files_requires_pattern():
    import tools.openclaw_proxy_tool as bridge

    result = json.loads(bridge.openclaw_search_files("   "))

    assert result["error"] == "pattern is required"


def test_openclaw_git_status_returns_branch_and_entries():
    import tools.openclaw_proxy_tool as bridge

    stdout = "## main\n M tools/openclaw_proxy_tool.py\n?? tests/tools/test_openclaw_proxy_tool.py\n"

    with patch.object(bridge.subprocess, "run", return_value=_completed(stdout)):
        result = json.loads(bridge.openclaw_git_status("/tmp/repo"))

    assert result["ok"] is True
    assert result["path"] == "/tmp/repo"
    assert result["branch"] == "## main"
    assert result["entry_count"] == 2
    assert result["entries"] == [
        " M tools/openclaw_proxy_tool.py",
        "?? tests/tools/test_openclaw_proxy_tool.py",
    ]


def test_openclaw_git_status_returns_tool_error_on_failure():
    import tools.openclaw_proxy_tool as bridge

    with patch.object(
        bridge.subprocess,
        "run",
        return_value=_completed("", returncode=128, stderr="fatal: not a git repository"),
    ):
        result = json.loads(bridge.openclaw_git_status("/tmp/nope"))

    assert result["error"] == "fatal: not a git repository"


def test_openclaw_proxy_registers_dynamic_toolset():
    from toolsets import resolve_toolset, validate_toolset
    import tools.openclaw_proxy_tool  # noqa: F401

    assert validate_toolset("openclaw_proxy") is True
    assert resolve_toolset("openclaw_proxy") == [
        "openclaw_git_status",
        "openclaw_history",
        "openclaw_search_files",
        "openclaw_turn",
    ]
