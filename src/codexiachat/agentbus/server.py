from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .config import ServerConfig
from .errors import AgentBusError, AuthError, ConflictError, ValidationError
from .models import validate_result_payload, validate_task_payload
from .security import PathPolicy
from .store import JsonStore


class AgentBusService:
    def __init__(self, config: ServerConfig):
        self.config = config
        seen_tokens: set[str] = set()
        for agent in config.agents.values():
            token = agent.token()
            if token in seen_tokens:
                raise AuthError("Agent bearer tokens must be unique")
            seen_tokens.add(token)
        self.store = JsonStore(config.data_dir)

    def authenticate(self, headers: dict[str, str]) -> str:
        auth = headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            raise AuthError("Missing bearer token")
        token = auth.removeprefix("Bearer ").strip()
        for agent in self.config.agents.values():
            if token == agent.token():
                return agent.id
        raise AuthError("Invalid bearer token")

    def create_task(self, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
        envelope = validate_task_payload(
            payload,
            known_agents=set(self.config.agents.keys()),
            known_projects=set(self.config.projects.keys()),
        )
        actor_config = self.config.agents[actor]
        if not actor_config.can_submit_tasks and envelope.from_agent != actor:
            raise AuthError("Actor cannot submit tasks for another agent")
        if envelope.project not in actor_config.allowed_projects:
            raise AuthError("Actor cannot submit tasks for this project")
        if envelope.project not in self.config.agents[envelope.to_agent].allowed_projects:
            raise AuthError("Target agent cannot receive this project")
        policy = self._path_policy(envelope.project)
        policy.validate_existing_many(payload["context_refs"], field="context_refs")
        policy.validate_many(payload["allowed_files"], field="allowed_files")
        policy.validate_many(payload["expected_outputs"], field="expected_outputs")
        return self.store.create_task(payload)

    def next_task(self, actor: str) -> dict[str, Any] | None:
        return self.store.next_task_for(actor)

    def get_task(self, actor: str, task_id: str) -> dict[str, Any]:
        record = self.store.get_task(task_id)
        payload = record["payload"]
        if actor not in {payload["from"], payload["to"]} and not self.config.agents[actor].can_submit_tasks:
            raise AuthError("Actor cannot read this task")
        return record

    def ack_task(self, actor: str, task_id: str, status: str) -> dict[str, str]:
        record = self.store.get_task(task_id)
        if record["payload"]["to"] != actor:
            raise AuthError("Only target worker can ack this task")
        if status not in {"acknowledged", "running"}:
            raise ValidationError("Invalid ack status")
        self.store.update_task_status(task_id, status, status)
        return {"ok": "true"}

    def submit_result(self, actor: str, task_id: str, payload: dict[str, Any]) -> dict[str, str]:
        record = self.store.get_task(task_id)
        task = validate_task_payload(
            record["payload"],
            known_agents=set(self.config.agents.keys()),
            known_projects=set(self.config.projects.keys()),
        )
        if task.to_agent != actor:
            raise AuthError("Only target worker can submit result")
        result = validate_result_payload(payload, task=task, worker_id=actor)
        policy = self._path_policy(task.project)
        policy.validate_many(result["changed_files"], field="changed_files")
        policy.validate_many(result["artifact_refs"], field="artifact_refs")
        expected = {str(policy.resolve_allowed(path, field="expected_outputs")) for path in task.payload["expected_outputs"]}
        changed = {str(policy.resolve_allowed(path, field="changed_files")) for path in result["changed_files"]}
        unexpected = sorted(path for path in changed if path not in expected and ".agentbus" not in path)
        if unexpected:
            raise ValidationError(f"Result changed files outside expected outputs: {unexpected}")
        self.store.save_result(task_id, result)
        return {"ok": "true"}

    def create_lock(self, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
        for field in ["id", "project", "resource", "reason", "expires_at"]:
            if field not in payload:
                raise ValidationError(f"Lock missing field: {field}")
        if payload["project"] not in self.config.projects:
            raise ValidationError("Unknown project")
        if payload["project"] not in self.config.agents[actor].allowed_projects:
            raise AuthError("Actor cannot lock this project")
        policy = self._path_policy(payload["project"])
        policy.resolve_allowed(payload["resource"], field="resource")
        return self.store.create_lock({**payload, "owner_agent": actor})

    def active_locks(self, actor: str) -> list[dict[str, Any]]:
        allowed_projects = set(self.config.agents[actor].allowed_projects)
        return [lock for lock in self.store.active_locks() if lock["project"] in allowed_projects]

    def _path_policy(self, project_id: str) -> PathPolicy:
        project = self.config.projects[project_id]
        roots = list(project.coordination_roots)
        if project.artifact_root:
            roots.append(project.artifact_root)
        return PathPolicy(project.repo_path, tuple(roots))


def make_http_server(config: ServerConfig) -> ThreadingHTTPServer:
    service = AgentBusService(config)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle(self, method: str) -> None:
            try:
                response = self._dispatch(method)
                self._send_json(200, response)
            except AuthError as exc:
                self._send_json(401, {"error": str(exc)})
            except ConflictError as exc:
                self._send_json(409, {"error": str(exc)})
            except ValidationError as exc:
                self._send_json(400, {"error": str(exc)})
            except AgentBusError as exc:
                self._send_json(500, {"error": str(exc)})

        def _dispatch(self, method: str) -> Any:
            path = urlparse(self.path).path
            if method == "GET" and path == "/health":
                return {"ok": True}
            actor = service.authenticate({key.lower(): value for key, value in self.headers.items()})
            if method == "GET" and path == "/tasks/next":
                return service.next_task(actor) or {"task": None}
            if method == "GET" and path == "/locks":
                return {"locks": service.active_locks(actor)}
            if method == "POST" and path == "/tasks":
                return service.create_task(actor, self._read_json())
            if method == "POST" and path == "/locks":
                return service.create_lock(actor, self._read_json())
            parts = [part for part in path.split("/") if part]
            if len(parts) == 2 and parts[0] == "tasks" and method == "GET":
                return service.get_task(actor, parts[1])
            if len(parts) == 3 and parts[0] == "tasks" and method == "POST":
                if parts[2] in {"ack", "running"}:
                    return service.ack_task(actor, parts[1], "running" if parts[2] == "running" else "acknowledged")
                if parts[2] == "result":
                    return service.submit_result(actor, parts[1], self._read_json())
            raise ValidationError("Route not found")

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            if length > service.config.max_message_bytes:
                raise ValidationError("Request body too large")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValidationError("Invalid JSON body") from exc
            if not isinstance(payload, dict):
                raise ValidationError("JSON body must be an object")
            return payload

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((config.bind_host, config.port), Handler)


def run_server(config: ServerConfig) -> None:
    make_http_server(config).serve_forever()
