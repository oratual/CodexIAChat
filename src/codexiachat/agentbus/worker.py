from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import WorkerConfig
from .errors import ValidationError
from .models import validate_result_payload, validate_task_payload
from .security import PathPolicy, changed_files, redact, snapshot_tree, utc_now


class AgentBusWorker:
    def __init__(self, config: WorkerConfig):
        self.config = config
        config.agent.token()
        roots = list(config.project.coordination_roots)
        if config.project.artifact_root:
            roots.append(config.project.artifact_root)
        self.path_policy = PathPolicy(config.project.repo_path, tuple(roots))

    def run_once(self) -> str:
        record = self._request("GET", "/tasks/next")
        if record.get("task") is None and "payload" not in record:
            return "idle"
        payload = record["payload"]
        task = validate_task_payload(
            payload,
            known_agents={self.config.agent.id, payload["from"], payload["to"]},
            known_projects={self.config.project.id},
        )
        if task.to_agent != self.config.agent.id:
            raise ValidationError("Worker received task addressed to another agent")
        self.path_policy.validate_many(payload["context_refs"], field="context_refs")
        self.path_policy.validate_many(payload["allowed_files"], field="allowed_files")
        self.path_policy.validate_many(payload["expected_outputs"], field="expected_outputs")
        blocked = self._blocked_by_lock(payload)
        if blocked:
            result = self._blocked_result(task.id, blocked)
            self._request("POST", f"/tasks/{task.id}/result", result)
            return "blocked"
        self._request("POST", f"/tasks/{task.id}/running", {})
        task_file = self._materialize_task_pack(payload)
        before = snapshot_tree(self.config.project.repo_path, exclude_dirs={".agentbus", ".git", "__pycache__"})
        completed = self._run_command(task.id, task_file)
        after = snapshot_tree(self.config.project.repo_path, exclude_dirs={".agentbus", ".git", "__pycache__"})
        actual_changed = changed_files(before, after)
        result_path = self.config.project.repo_path / ".agentbus" / "outbox" / f"{task.id}.result.json"
        if not result_path.exists():
            if completed.returncode == 0:
                raise ValidationError(f"Command completed without required result file: {result_path}")
            result = self._failure_result(task.id, completed)
        else:
            with result_path.open("r", encoding="utf-8") as handle:
                result = json.load(handle)
            validate_result_payload(result, task=task, worker_id=self.config.agent.id)
        unexpected = self._unexpected_actual_changes(payload, actual_changed)
        if unexpected:
            result = {
                "task_id": task.id,
                "status": "failed",
                "worker_id": self.config.agent.id,
                "summary": "Command changed files outside expected outputs",
                "changed_files": [],
                "artifact_refs": [],
                "tests_run": [],
                "warnings": [],
                "errors": [f"Unexpected changes: {unexpected}"],
                "completed_at": utc_now().isoformat(),
            }
        self._request("POST", f"/tasks/{task.id}/result", result)
        return str(result["status"])

    def _materialize_task_pack(self, payload: dict[str, Any]) -> Path:
        task_dir = self.config.project.repo_path / ".agentbus" / "inbox" / payload["id"]
        task_dir.mkdir(parents=True, exist_ok=True)
        task_file = task_dir / "task.md"
        allowed_file = task_dir / "allowed_files.txt"
        context_file = task_dir / "context.md"
        task_file.write_text(_render_task_markdown(payload), encoding="utf-8")
        allowed_file.write_text("\n".join(payload["allowed_files"]) + "\n", encoding="utf-8")
        context_file.write_text("\n".join(payload["known_context"]) + "\n", encoding="utf-8")
        return task_file

    def _run_command(self, task_id: str, task_file: Path) -> subprocess.CompletedProcess[str]:
        outbox = self.config.project.repo_path / ".agentbus" / "outbox"
        logs = self.config.project.repo_path / ".agentbus" / "logs"
        outbox.mkdir(parents=True, exist_ok=True)
        logs.mkdir(parents=True, exist_ok=True)
        format_values = {
            "task_id": task_id,
            "task_file": str(task_file),
            "result_file": str(outbox / f"{task_id}.result.json"),
        }
        command = [part.format(**format_values) for part in self.config.agent.command_profile]
        env = {"PATH": os.environ.get("PATH", "")}
        for name in self.config.extra_env_allowlist:
            if name in os.environ:
                env[name] = os.environ[name]
        completed = subprocess.run(
            command,
            cwd=self.config.project.repo_path,
            env=env,
            text=True,
            capture_output=True,
            timeout=self.config.agent.timeout_seconds,
            check=False,
        )
        stdout = redact(completed.stdout) if self.config.redact_logs else completed.stdout
        stderr = redact(completed.stderr) if self.config.redact_logs else completed.stderr
        (logs / f"{task_id}.stdout.log").write_text(stdout, encoding="utf-8")
        (logs / f"{task_id}.stderr.log").write_text(stderr, encoding="utf-8")
        return completed

    def _failure_result(self, task_id: str, completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "status": "failed",
            "worker_id": self.config.agent.id,
            "summary": f"Command exited with code {completed.returncode}",
            "changed_files": [],
            "artifact_refs": [],
            "tests_run": [],
            "warnings": [],
            "errors": [redact(completed.stderr[-4000:])],
            "completed_at": utc_now().isoformat(),
        }

    def _blocked_result(self, task_id: str, reason: str) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "status": "blocked",
            "worker_id": self.config.agent.id,
            "summary": reason,
            "changed_files": [],
            "artifact_refs": [],
            "tests_run": [],
            "warnings": [reason],
            "errors": [],
            "completed_at": utc_now().isoformat(),
        }

    def _blocked_by_lock(self, payload: dict[str, Any]) -> str | None:
        locks = self._request("GET", "/locks").get("locks", [])
        if not locks:
            return None
        expected = [self.path_policy.resolve_allowed(path, field="expected_outputs") for path in payload["expected_outputs"]]
        for lock in locks:
            if lock.get("owner_agent") == self.config.agent.id:
                continue
            resource = self.path_policy.resolve_allowed(lock["resource"], field="lock.resource")
            for output in expected:
                if _overlaps(resource, output):
                    return f"Blocked by lock {lock['id']} on {lock['resource']}"
        return None

    def _unexpected_actual_changes(self, payload: dict[str, Any], actual_changed: set[str]) -> list[str]:
        expected = {
            str(self.path_policy.resolve_allowed(path, field="expected_outputs"))
            for path in payload["expected_outputs"]
            if not path.replace("\\", "/").startswith(".agentbus/")
        }
        return sorted(path for path in actual_changed if path not in expected)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.config.server_url + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.config.agent.token()}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise ValidationError(f"Server returned {exc.code}: {detail}") from exc


def _overlaps(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _render_task_markdown(payload: dict[str, Any]) -> str:
    return "\n".join([
        f"# AgentBus Task: {payload['id']}",
        "",
        "## Task",
        payload["summary"],
        "",
        "## Why",
        payload["why"],
        "",
        "## Known Context",
        *[f"- {item}" for item in payload["known_context"]],
        "",
        "## Context References",
        *[f"- {item}" for item in payload["context_refs"]],
        "",
        "## Allowed Files",
        *[f"- {item}" for item in payload["allowed_files"]],
        "",
        "## Forbidden Scope",
        *[f"- {item}" for item in payload["forbidden_scope"]],
        "",
        "## Expected Outputs",
        *[f"- {item}" for item in payload["expected_outputs"]],
        "",
        "Write the required result JSON and do not inspect unrelated AgentBus tasks.",
        "",
    ])
