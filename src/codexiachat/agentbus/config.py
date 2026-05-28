from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError
from .security import load_secret_from_env


@dataclass(frozen=True)
class AgentConfig:
    id: str
    token_env: str
    allowed_projects: tuple[str, ...]
    repo_path: Path | None = None
    command_profile: tuple[str, ...] = ()
    timeout_seconds: int = 3600
    can_submit_tasks: bool = False

    def token(self) -> str:
        return load_secret_from_env(self.token_env)


@dataclass(frozen=True)
class ProjectConfig:
    id: str
    repo_path: Path
    coordination_roots: tuple[Path, ...] = ()
    artifact_root: Path | None = None


@dataclass(frozen=True)
class ServerConfig:
    bind_host: str
    port: int
    data_dir: Path
    agents: dict[str, AgentConfig]
    projects: dict[str, ProjectConfig]
    max_message_bytes: int = 262_144


@dataclass(frozen=True)
class WorkerConfig:
    agent: AgentConfig
    project: ProjectConfig
    server_url: str
    poll_interval_seconds: float = 5.0
    redact_logs: bool = True
    extra_env_allowlist: tuple[str, ...] = field(default_factory=tuple)


def load_server_config(path: str | Path) -> ServerConfig:
    raw = _read_yaml(path)
    server = raw.get("server") or {}
    agents = _parse_agents(raw.get("agents") or [])
    projects = _parse_projects(raw.get("projects") or [])
    bind_host = str(server.get("bind_host", "127.0.0.1"))
    if bind_host == "0.0.0.0":
        raise ConfigError("Refusing bind_host 0.0.0.0 without an explicit downstream security decision")
    return ServerConfig(
        bind_host=bind_host,
        port=int(server.get("port", 8765)),
        data_dir=Path(server.get("data_dir", ".agentbus/server")),
        agents=agents,
        projects=projects,
        max_message_bytes=int(server.get("max_message_bytes", 262_144)),
    )


def load_worker_config(path: str | Path) -> WorkerConfig:
    raw = _read_yaml(path)
    server = raw.get("server") or {}
    worker = raw.get("worker") or {}
    agents = _parse_agents(raw.get("agents") or [])
    projects = _parse_projects(raw.get("projects") or [])
    agent_id = worker.get("agent_id")
    project_id = worker.get("project_id")
    if agent_id not in agents:
        raise ConfigError(f"Unknown worker agent_id: {agent_id}")
    if project_id not in projects:
        raise ConfigError(f"Unknown worker project_id: {project_id}")
    agent = agents[agent_id]
    if project_id not in agent.allowed_projects:
        raise ConfigError(f"Agent {agent_id} is not allowed to handle project {project_id}")
    if not agent.command_profile:
        raise ConfigError(f"Agent {agent_id} needs a static command_profile")
    return WorkerConfig(
        agent=agent,
        project=projects[project_id],
        server_url=str(server.get("url", "http://127.0.0.1:8765")).rstrip("/"),
        poll_interval_seconds=float(worker.get("poll_interval_seconds", 5.0)),
        redact_logs=bool(worker.get("redact_logs", True)),
        extra_env_allowlist=tuple(worker.get("extra_env_allowlist") or ()),
    )


def _read_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")
    return data


def _parse_agents(items: list[dict[str, Any]]) -> dict[str, AgentConfig]:
    agents: dict[str, AgentConfig] = {}
    for item in items:
        agent_id = str(item.get("id", "")).strip()
        if not agent_id:
            raise ConfigError("Agent id is required")
        agents[agent_id] = AgentConfig(
            id=agent_id,
            token_env=str(item.get("token_env", "")).strip(),
            allowed_projects=tuple(item.get("allowed_projects") or ()),
            repo_path=Path(item["repo_path"]) if item.get("repo_path") else None,
            command_profile=tuple(str(part) for part in item.get("command_profile") or ()),
            timeout_seconds=int(item.get("timeout_seconds", 3600)),
            can_submit_tasks=bool(item.get("can_submit_tasks", False)),
        )
        if not agents[agent_id].token_env:
            raise ConfigError(f"Agent {agent_id} must use token_env")
    return agents


def _parse_projects(items: list[dict[str, Any]]) -> dict[str, ProjectConfig]:
    projects: dict[str, ProjectConfig] = {}
    for item in items:
        project_id = str(item.get("id", "")).strip()
        if not project_id:
            raise ConfigError("Project id is required")
        projects[project_id] = ProjectConfig(
            id=project_id,
            repo_path=Path(item["repo_path"]),
            coordination_roots=tuple(Path(path) for path in item.get("coordination_roots") or ()),
            artifact_root=Path(item["artifact_root"]) if item.get("artifact_root") else None,
        )
    return projects
