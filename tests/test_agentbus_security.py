from __future__ import annotations

import json
import os
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from codexiachat.agentbus.config import AgentConfig, ProjectConfig, ServerConfig, WorkerConfig
from codexiachat.agentbus.errors import AuthError, ConflictError, ValidationError
from codexiachat.agentbus.models import validate_task_payload
from codexiachat.agentbus.security import PathPolicy, redact
from codexiachat.agentbus.server import AgentBusService, make_http_server
from codexiachat.agentbus.worker import AgentBusWorker


def test_task_rejects_runtime_control_fields(tmp_path: Path) -> None:
    task = _task(tmp_path)
    task["env"] = {"GITHUB_TOKEN": "x"}
    with pytest.raises(ValidationError, match="runtime fields"):
        validate_task_payload(task, known_agents={"windows-infra", "mac-ui"}, known_projects={"codexiachat"})


def test_path_policy_rejects_escape_and_ads(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)
    with pytest.raises(ValidationError):
        policy.resolve_allowed("../outside.txt", field="path")
    with pytest.raises(ValidationError):
        policy.resolve_allowed("~/outside.txt", field="path")
    with pytest.raises(ValidationError):
        policy.resolve_allowed("docs/file.txt:ads", field="path")


def test_redact_removes_secret_like_values() -> None:
    seeded = "sk-" + "1" * 24
    assert seeded not in redact(f"token={seeded}")
    assert "hunter2" not in redact("password=hunter2")


def test_server_auth_and_replay_protection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path, monkeypatch)
    task = _task(tmp_path)
    with pytest.raises(AuthError):
        service.create_task("mac-ui", task)
    created = service.create_task("windows-infra", task)
    assert created["status"] == "pending"
    with pytest.raises(ConflictError):
        service.create_task("windows-infra", {**task, "id": "task_other"})


def test_server_rejects_duplicate_agent_tokens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_repo(tmp_path)
    monkeypatch.setenv("AGENTBUS_WINDOWS_INFRA_TOKEN", "same-token")
    monkeypatch.setenv("AGENTBUS_MAC_UI_TOKEN", "same-token")
    with pytest.raises(AuthError, match="unique"):
        AgentBusService(_server_config(tmp_path, 0))


def test_server_rejects_missing_context_refs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path, monkeypatch)
    task = _task(tmp_path)
    task["context_refs"] = ["docs/missing.md"]
    with pytest.raises(ValidationError, match="missing"):
        service.create_task("windows-infra", task)


def test_worker_runs_static_profile_and_redacts_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    port = _free_port()
    service = _service(tmp_path, monkeypatch, port=port)
    service.create_task("windows-infra", _task(tmp_path))
    httpd, thread = _server_thread(tmp_path, monkeypatch, port=port)
    try:
        seeded = "sk-" + "1" * 24
        monkeypatch.setenv("SHOULD_NOT_LEAK", seeded)
        worker = AgentBusWorker(_worker_config(tmp_path, port=port, script=_writer_script(tmp_path)))
        assert worker.run_once() == "completed"
        stdout = (tmp_path / ".agentbus" / "logs" / "task_20260528_001.stdout.log").read_text(encoding="utf-8")
        assert seeded not in stdout
        assert (tmp_path / "docs" / "ui" / "result.md").read_text(encoding="utf-8") == "done\n"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_worker_marks_unexpected_writes_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    port = _free_port()
    service = _service(tmp_path, monkeypatch, port=port)
    service.create_task("windows-infra", _task(tmp_path))
    httpd, thread = _server_thread(tmp_path, monkeypatch, port=port)
    try:
        worker = AgentBusWorker(_worker_config(tmp_path, port=port, script=_writer_script(tmp_path, extra_write=True)))
        assert worker.run_once() == "failed"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_worker_blocks_on_active_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    port = _free_port()
    service = _service(tmp_path, monkeypatch, port=port)
    task = _task(tmp_path)
    service.create_task("windows-infra", task)
    service.create_lock("windows-infra", {
        "id": "lock_docs_ui",
        "project": "codexiachat",
        "resource": "docs/ui",
        "reason": "test lock",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    })
    httpd, thread = _server_thread(tmp_path, monkeypatch, port=port)
    try:
        worker = AgentBusWorker(_worker_config(tmp_path, port=port, script=_writer_script(tmp_path)))
        assert worker.run_once() == "blocked"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def _service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, port: int = 18765) -> AgentBusService:
    _prepare_repo(tmp_path)
    monkeypatch.setenv("AGENTBUS_WINDOWS_INFRA_TOKEN", "windows-token")
    monkeypatch.setenv("AGENTBUS_MAC_UI_TOKEN", "mac-token")
    return AgentBusService(_server_config(tmp_path, port))


def _server_config(tmp_path: Path, port: int) -> ServerConfig:
    return ServerConfig(
        bind_host="127.0.0.1",
        port=port,
        data_dir=tmp_path / ".agentbus" / "server",
        agents={
            "windows-infra": AgentConfig(
                id="windows-infra",
                token_env="AGENTBUS_WINDOWS_INFRA_TOKEN",
                allowed_projects=("codexiachat",),
                can_submit_tasks=True,
            ),
            "mac-ui": AgentConfig(
                id="mac-ui",
                token_env="AGENTBUS_MAC_UI_TOKEN",
                allowed_projects=("codexiachat",),
            ),
        },
        projects={
            "codexiachat": ProjectConfig(
                id="codexiachat",
                repo_path=tmp_path,
                coordination_roots=(tmp_path / ".agentbus",),
                artifact_root=tmp_path / ".agentbus" / "artifacts",
            )
        },
    )


def _worker_config(tmp_path: Path, port: int, script: Path) -> WorkerConfig:
    return WorkerConfig(
        agent=AgentConfig(
            id="mac-ui",
            token_env="AGENTBUS_MAC_UI_TOKEN",
            allowed_projects=("codexiachat",),
            command_profile=(sys.executable, str(script), "{task_id}", "{result_file}"),
            timeout_seconds=30,
        ),
        project=ProjectConfig(
            id="codexiachat",
            repo_path=tmp_path,
            coordination_roots=(tmp_path / ".agentbus",),
            artifact_root=tmp_path / ".agentbus" / "artifacts",
        ),
        server_url=f"http://127.0.0.1:{port}",
    )


def _server_thread(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, port: int):
    monkeypatch.setenv("AGENTBUS_WINDOWS_INFRA_TOKEN", "windows-token")
    monkeypatch.setenv("AGENTBUS_MAC_UI_TOKEN", "mac-token")
    httpd = make_http_server(_server_config(tmp_path, port))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _prepare_repo(tmp_path: Path) -> None:
    (tmp_path / "docs" / "ui").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "current_state.md").write_text("state\n", encoding="utf-8")
    (tmp_path / ".agentbus" / "artifacts").mkdir(parents=True, exist_ok=True)


def _task(tmp_path: Path) -> dict:
    now = datetime.now(UTC)
    return {
        "id": "task_20260528_001",
        "version": "1.0",
        "project": "codexiachat",
        "kind": "REQUEST",
        "from": "windows-infra",
        "to": "mac-ui",
        "priority": "normal",
        "summary": "Write UI result",
        "why": "Exercise worker execution",
        "known_context": ["Use the expected output only."],
        "context_refs": ["docs/current_state.md"],
        "allowed_files": ["docs/ui", ".agentbus/outbox"],
        "forbidden_scope": ["Do not write outside docs/ui."],
        "expected_outputs": ["docs/ui/result.md", ".agentbus/outbox/task_20260528_001.result.json"],
        "reply_to": "windows-infra",
        "ack_required": True,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "nonce": "nonce_20260528_001",
    }


def _writer_script(tmp_path: Path, extra_write: bool = False) -> Path:
    script = tmp_path / "writer.py"
    extra = "(Path('unexpected.txt')).write_text('bad\\n', encoding='utf-8')" if extra_write else ""
    script.write_text(
        f"""
import json
import os
import sys
from pathlib import Path

task_id = sys.argv[1]
result_file = Path(sys.argv[2])
Path('docs/ui/result.md').write_text('done\\n', encoding='utf-8')
{extra}
print(os.environ.get('SHOULD_NOT_LEAK', 'not-present'))
result_file.write_text(json.dumps({{
    'task_id': task_id,
    'status': 'completed',
    'worker_id': 'mac-ui',
    'summary': 'completed',
    'changed_files': ['docs/ui/result.md'],
    'artifact_refs': [],
    'tests_run': ['writer.py'],
    'warnings': [],
    'errors': [],
}}, sort_keys=True), encoding='utf-8')
""",
        encoding="utf-8",
    )
    return script
