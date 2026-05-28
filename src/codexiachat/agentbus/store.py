from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConflictError, ValidationError
from .security import new_fencing_token, utc_now


@dataclass
class JsonStore:
    data_dir: Path

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for name, initial in {
            "tasks.json": {},
            "results.json": {},
            "nonces.json": {},
            "locks.json": {},
        }.items():
            path = self.data_dir / name
            if not path.exists():
                self._write_json(path, initial)

    def create_task(self, task: dict[str, Any]) -> dict[str, Any]:
        tasks = self._read_json("tasks.json")
        nonces = self._read_json("nonces.json")
        if task["id"] in tasks:
            raise ConflictError("Duplicate task id")
        nonce_key = f"{task['from']}:{task['nonce']}"
        if nonce_key in nonces:
            raise ConflictError("Duplicate task nonce")
        record = {
            "payload": task,
            "status": "pending",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        tasks[task["id"]] = record
        nonces[nonce_key] = task["id"]
        self._write_json(self.data_dir / "tasks.json", tasks)
        self._write_json(self.data_dir / "nonces.json", nonces)
        self.append_event(task["id"], "created", {"to": task["to"], "from": task["from"]})
        return record

    def next_task_for(self, agent_id: str) -> dict[str, Any] | None:
        tasks = self._read_json("tasks.json")
        candidates = [
            record for record in tasks.values()
            if record["status"] == "pending" and record["payload"]["to"] == agent_id
        ]
        candidates.sort(key=lambda record: record["created_at"])
        return candidates[0] if candidates else None

    def get_task(self, task_id: str) -> dict[str, Any]:
        tasks = self._read_json("tasks.json")
        if task_id not in tasks:
            raise ValidationError("Unknown task")
        return tasks[task_id]

    def update_task_status(self, task_id: str, status: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        tasks = self._read_json("tasks.json")
        if task_id not in tasks:
            raise ValidationError("Unknown task")
        tasks[task_id]["status"] = status
        tasks[task_id]["updated_at"] = utc_now().isoformat()
        self._write_json(self.data_dir / "tasks.json", tasks)
        self.append_event(task_id, event_type, payload or {})

    def save_result(self, task_id: str, result: dict[str, Any]) -> None:
        results = self._read_json("results.json")
        results[task_id] = {
            "payload": result,
            "created_at": utc_now().isoformat(),
        }
        self._write_json(self.data_dir / "results.json", results)
        self.update_task_status(task_id, result["status"], "result", {"status": result["status"]})

    def create_lock(self, lock: dict[str, Any]) -> dict[str, Any]:
        locks = self._read_json("locks.json")
        if lock["id"] in locks:
            raise ConflictError("Duplicate lock id")
        lock = {**lock, "fencing_token": new_fencing_token(), "released_at": None}
        locks[lock["id"]] = lock
        self._write_json(self.data_dir / "locks.json", locks)
        return lock

    def active_locks(self) -> list[dict[str, Any]]:
        now = utc_now().isoformat()
        locks = self._read_json("locks.json")
        return [
            lock for lock in locks.values()
            if lock.get("released_at") is None and lock["expires_at"] > now
        ]

    def append_event(self, task_id: str, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "task_id": task_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": utc_now().isoformat(),
        }
        with (self.data_dir / "task_events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _read_json(self, name: str) -> dict[str, Any]:
        with (self.data_dir / name).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        tmp.replace(path)
