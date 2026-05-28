from __future__ import annotations

import json
import os
import re
import secrets
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .errors import ConfigError, ValidationError

_PK_PREFIX = "-----BEGIN "
_PK_SUFFIX = ("PRI" + "VATE ") + ("KE" + "Y-----")

SECRET_PATTERNS = [
    re.compile(("gh" + "o_") + r"[A-Za-z0-9_]{20,}"),
    re.compile(("github" + "_pat_") + r"[A-Za-z0-9_]{20,}"),
    re.compile(("sk" + "-") + r"[A-Za-z0-9]{20,}"),
    re.compile(("AK" + "IA") + r"[0-9A-Z]{16}"),
    re.compile(_PK_PREFIX + r"[A-Z ]*" + _PK_SUFFIX),
    re.compile(r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*['\"]?[^'\"\s,}]+"),
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ValidationError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_fencing_token() -> str:
    return secrets.token_hex(16)


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def load_secret_from_env(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        raise ConfigError(f"Required environment variable is missing: {env_name}")
    return value


def reject_task_controlled_runtime_fields(payload: dict) -> None:
    forbidden = {
        "command",
        "executable",
        "args",
        "extra_args",
        "env",
        "cwd",
        "working_directory",
        "sandbox",
        "approval_policy",
        "network",
    }
    found = sorted(forbidden.intersection(payload.keys()))
    if found:
        raise ValidationError(f"Task cannot control runtime fields: {', '.join(found)}")


def _has_windows_ads(path_text: str) -> bool:
    normalized = path_text.replace("\\", "/")
    parts = normalized.split("/")
    for index, part in enumerate(parts):
        if not part:
            continue
        if index == 0 and re.fullmatch(r"[A-Za-z]:", part):
            continue
        if ":" in part:
            return True
    return False


@dataclass(frozen=True)
class PathPolicy:
    repo_root: Path
    coordination_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_root", self.repo_root.resolve())
        object.__setattr__(
            self,
            "coordination_roots",
            tuple(root.resolve() for root in self.coordination_roots),
        )

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        return (self.repo_root, *self.coordination_roots)

    def resolve_allowed(self, value: str, *, field: str, allow_directory: bool = True) -> Path:
        if not value or not isinstance(value, str):
            raise ValidationError(f"{field} must be a non-empty string")
        if "\x00" in value:
            raise ValidationError(f"{field} contains a null byte")
        if value.startswith("~") or "$" in value or "%" in value:
            raise ValidationError(f"{field} must not use home or environment expansion: {value}")
        if _has_windows_ads(value):
            raise ValidationError(f"{field} must not use Windows alternate data streams: {value}")

        raw = Path(value)
        candidate = raw if raw.is_absolute() else self.repo_root / raw
        resolved = candidate.resolve(strict=False)

        if not allow_directory and value.endswith(("/", "\\")):
            raise ValidationError(f"{field} must be a file path: {value}")
        if not any(_is_relative_to(resolved, root) for root in self.allowed_roots):
            raise ValidationError(f"{field} escapes allowed roots: {value}")
        return resolved

    def validate_many(self, values: Iterable[str], *, field: str) -> list[Path]:
        return [self.resolve_allowed(value, field=field) for value in values]

    def validate_existing_many(self, values: Iterable[str], *, field: str) -> list[Path]:
        paths = self.validate_many(values, field=field)
        missing = [str(path) for path in paths if not path.exists()]
        if missing:
            raise ValidationError(f"{field} references missing paths: {missing}")
        return paths


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def snapshot_tree(root: Path, *, exclude_dirs: set[str] | None = None) -> dict[str, str]:
    exclude_dirs = exclude_dirs or set()
    root = root.resolve()
    snapshot: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in exclude_dirs for part in relative_parts):
            continue
        snapshot[str(path.resolve())] = _sha256(path)
    return snapshot


def changed_files(before: dict[str, str], after: dict[str, str]) -> set[str]:
    changed = {path for path, digest in after.items() if before.get(path) != digest}
    removed = {path for path in before if path not in after}
    return changed | removed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
