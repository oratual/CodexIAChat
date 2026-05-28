from __future__ import annotations

import argparse
import json
import sys

from .config import load_server_config, load_worker_config
from .server import AgentBusService, run_server
from .worker import AgentBusWorker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codexiachat-agentbus")
    sub = parser.add_subparsers(dest="command", required=True)

    server = sub.add_parser("server")
    server.add_argument("--config", required=True)

    validate_server = sub.add_parser("validate-server-config")
    validate_server.add_argument("--config", required=True)

    validate_worker = sub.add_parser("validate-worker-config")
    validate_worker.add_argument("--config", required=True)

    submit = sub.add_parser("submit-task")
    submit.add_argument("--config", required=True)
    submit.add_argument("--actor", required=True)
    submit.add_argument("--task", required=True)

    worker = sub.add_parser("worker-run-once")
    worker.add_argument("--config", required=True)

    args = parser.parse_args(argv)

    if args.command == "server":
        run_server(load_server_config(args.config))
        return 0
    if args.command == "validate-server-config":
        load_server_config(args.config)
        print("ok")
        return 0
    if args.command == "validate-worker-config":
        load_worker_config(args.config)
        print("ok")
        return 0
    if args.command == "submit-task":
        config = load_server_config(args.config)
        with open(args.task, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        service = AgentBusService(config)
        print(json.dumps(service.create_task(args.actor, payload), ensure_ascii=False, indent=2))
        return 0
    if args.command == "worker-run-once":
        print(AgentBusWorker(load_worker_config(args.config)).run_once())
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
