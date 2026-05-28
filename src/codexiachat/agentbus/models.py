from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .security import parse_datetime, reject_task_controlled_runtime_fields, utc_now

ALLOWED_KINDS = {"REQUEST", "REPLY", "HANDOFF", "BLOCKED", "ARTIFACT_READY", "ERROR", "SUMMARY"}
ALLOWED_PRIORITIES = {"low", "normal", "high"}
TERMINAL_STATUSES = {"completed", "blocked", "failed"}


@dataclass(frozen=True)
class TaskEnvelope:
    payload: dict[str, Any]

    @property
    def id(self) -> str:
        return self.payload["id"]

    @property
    def project(self) -> str:
        return self.payload["project"]

    @property
    def from_agent(self) -> str:
        return self.payload["from"]

    @property
    def to_agent(self) -> str:
        return self.payload["to"]


def validate_task_payload(payload: dict[str, Any], *, known_agents: set[str], known_projects: set[str]) -> TaskEnvelope:
    if not isinstance(payload, dict):
        raise ValidationError("Task payload must be an object")
    reject_task_controlled_runtime_fields(payload)
    required = [
        "id",
        "version",
        "project",
        "kind",
        "from",
        "to",
        "priority",
        "summary",
        "why",
        "known_context",
        "context_refs",
        "allowed_files",
        "forbidden_scope",
        "expected_outputs",
        "reply_to",
        "ack_required",
        "created_at",
        "expires_at",
        "nonce",
    ]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValidationError(f"Task missing fields: {', '.join(missing)}")
    if payload["version"] != "1.0":
        raise ValidationError("Unsupported task version")
    if payload["kind"] not in ALLOWED_KINDS:
        raise ValidationError("Unsupported task kind")
    if payload["priority"] not in ALLOWED_PRIORITIES:
        raise ValidationError("Unsupported task priority")
    if payload["from"] not in known_agents:
        raise ValidationError("Unknown source agent")
    if payload["to"] not in known_agents:
        raise ValidationError("Unknown target agent")
    if payload["project"] not in known_projects:
        raise ValidationError("Unknown project")
    if not payload["id"].startswith("task_"):
        raise ValidationError("Task id must start with task_")
    for list_field in ["known_context", "context_refs", "allowed_files", "forbidden_scope", "expected_outputs"]:
        if not isinstance(payload[list_field], list):
            raise ValidationError(f"{list_field} must be a list")
    created_at = parse_datetime(payload["created_at"], "created_at")
    expires_at = parse_datetime(payload["expires_at"], "expires_at")
    if expires_at <= created_at:
        raise ValidationError("expires_at must be after created_at")
    if expires_at <= utc_now():
        raise ValidationError("Task is expired")
    if not isinstance(payload["nonce"], str) or len(payload["nonce"]) < 16:
        raise ValidationError("nonce must be at least 16 characters")
    return TaskEnvelope(payload=payload)


def validate_result_payload(payload: dict[str, Any], *, task: TaskEnvelope, worker_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("Result payload must be an object")
    required = ["task_id", "status", "worker_id", "summary", "changed_files", "artifact_refs", "tests_run", "warnings", "errors"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValidationError(f"Result missing fields: {', '.join(missing)}")
    if payload["task_id"] != task.id:
        raise ValidationError("Result task_id does not match task")
    if payload["worker_id"] != worker_id:
        raise ValidationError("Result worker_id does not match worker")
    if payload["status"] not in TERMINAL_STATUSES:
        raise ValidationError("Unsupported result status")
    for list_field in ["changed_files", "artifact_refs", "tests_run", "warnings", "errors"]:
        if not isinstance(payload[list_field], list):
            raise ValidationError(f"{list_field} must be a list")
    return payload
