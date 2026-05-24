import json
import subprocess
from pathlib import Path


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    (repo / "demo.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "demo.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    return repo


def test_git_status_reports_modified_file(tmp_path):
    import tools.git_basics_tool as git_tools

    repo = _make_repo(tmp_path)
    (repo / "demo.txt").write_text("hello\nworld\n", encoding="utf-8")

    payload = json.loads(git_tools.git_status(str(repo)))
    assert payload["ok"] is True
    assert payload["repo_root"] == str(repo)
    assert "demo.txt" in payload["output"]


def test_git_diff_returns_patch(tmp_path):
    import tools.git_basics_tool as git_tools

    repo = _make_repo(tmp_path)
    (repo / "demo.txt").write_text("hello\nworld\n", encoding="utf-8")

    payload = json.loads(git_tools.git_diff(str(repo)))
    assert payload["ok"] is True
    assert "diff --git" in payload["output"]
    assert "+world" in payload["output"]


def test_git_log_returns_recent_commits(tmp_path):
    import tools.git_basics_tool as git_tools

    repo = _make_repo(tmp_path)

    payload = json.loads(git_tools.git_log(str(repo), limit=1))
    assert payload["ok"] is True
    assert "init" in payload["output"]


def test_git_tools_error_outside_repo(tmp_path):
    import tools.git_basics_tool as git_tools

    outside = tmp_path / "outside"
    outside.mkdir()

    payload = json.loads(git_tools.git_status(str(outside)))
    assert "error" in payload
    assert "git repository" in payload["error"]
