from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
MAX_LOG_LINES = 5000


@dataclass
class StartPayload:
    max_odds: float
    min_odds: float
    count: int
    stake: float
    execute: bool
    keep_open: bool


class BotProcessManager:
    def __init__(self, script_path: Path) -> None:
        self.script_path = script_path
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._logs: list[str] = []

    def start(self, payload: StartPayload) -> tuple[bool, str]:
        with self._lock:
            if self._is_running_locked():
                return False, "Bot is already running."

            cmd = [
                sys.executable,
                str(self.script_path),
                "--max-odds",
                f"{payload.max_odds}",
                "--min-odds",
                f"{payload.min_odds}",
                "--count",
                str(payload.count),
                "--stake",
                f"{payload.stake}",
            ]
            if payload.execute:
                cmd.append("--execute")
            if payload.keep_open:
                cmd.append("--keep-open")

            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.script_path.parent),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                return False, f"Failed to start bot process: {exc}"

            self._process = process
            self._append_log_locked(f"Starting: {' '.join(cmd)}")
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()
            return True, "Bot started."

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                self._process = None
                return False, "Bot is not running."

            process.terminate()
            self._append_log_locked("Stopping process...")
            return True, "Stop signal sent."

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._is_running_locked(),
                "log_lines": len(self._logs),
            }

    def get_logs(self, from_index: int) -> dict[str, Any]:
        if from_index < 0:
            from_index = 0

        with self._lock:
            total = len(self._logs)
            if from_index > total:
                from_index = total

            return {
                "from_index": from_index,
                "next_index": total,
                "running": self._is_running_locked(),
                "lines": self._logs[from_index:],
            }

    def _read_output(self) -> None:
        process: subprocess.Popen[str] | None
        with self._lock:
            process = self._process

        if process is None:
            return

        if process.stdout is not None:
            for line in process.stdout:
                with self._lock:
                    self._append_log_locked(line.rstrip("\n"))

        return_code = process.wait()
        with self._lock:
            self._append_log_locked(f"Process exited with code {return_code}")
            self._process = None
            self._reader_thread = None

    def _append_log_locked(self, line: str) -> None:
        self._logs.append(line)
        if len(self._logs) > MAX_LOG_LINES:
            overflow = len(self._logs) - MAX_LOG_LINES
            del self._logs[:overflow]

    def _is_running_locked(self) -> bool:
        return self._process is not None and self._process.poll() is None


def parse_start_payload(raw: dict[str, Any]) -> StartPayload:
    try:
        max_odds = float(raw.get("max_odds", 1.35))
        min_odds = float(raw.get("min_odds", 1.01))
        count = int(raw.get("count", 39))
        stake = float(raw.get("stake", 2.0))
        execute = bool(raw.get("execute", False))
        keep_open = bool(raw.get("keep_open", True))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid numeric values in payload.") from exc

    if count <= 0:
        raise ValueError("count must be greater than 0.")
    if stake <= 0:
        raise ValueError("stake must be greater than 0.")
    if min_odds <= 0 or max_odds <= 0:
        raise ValueError("min_odds and max_odds must be greater than 0.")
    if min_odds > max_odds:
        raise ValueError("min_odds must be less than or equal to max_odds.")

    return StartPayload(
        max_odds=max_odds,
        min_odds=min_odds,
        count=count,
        stake=stake,
        execute=execute,
        keep_open=keep_open,
    )


def build_handler(manager: BotProcessManager) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "BetikaBotService/1.0"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True, **manager.health()})
                return

            if parsed.path == "/logs":
                params = parse_qs(parsed.query)
                raw_index = params.get("from", ["0"])[0]
                try:
                    from_index = int(raw_index)
                except ValueError:
                    self._send_json(400, {"ok": False, "error": "Invalid 'from' query value."})
                    return
                self._send_json(200, {"ok": True, **manager.get_logs(from_index)})
                return

            self._send_json(404, {"ok": False, "error": "Not found."})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/start":
                payload = self._read_json_body()
                if payload is None:
                    self._send_json(400, {"ok": False, "error": "Body must be valid JSON."})
                    return

                try:
                    parsed_payload = parse_start_payload(payload)
                except ValueError as exc:
                    self._send_json(400, {"ok": False, "error": str(exc)})
                    return

                ok, message = manager.start(parsed_payload)
                status = 200 if ok else 409
                self._send_json(status, {"ok": ok, "message": message, **manager.health()})
                return

            if parsed.path == "/stop":
                ok, message = manager.stop()
                status = 200 if ok else 409
                self._send_json(status, {"ok": ok, "message": message, **manager.health()})
                return

            self._send_json(404, {"ok": False, "error": "Not found."})

        def log_message(self, format: str, *args: object) -> None:
            # Keep server output clean for CLI logs from betika.py.
            return

        def _read_json_body(self) -> dict[str, Any] | None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            return payload if isinstance(payload, dict) else None

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a small HTTP service that starts/stops betika.py for mobile control."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    script_path = Path(__file__).resolve().with_name("betika.py")
    if not script_path.exists():
        print(f"ERROR: Could not find bot script at {script_path}", file=sys.stderr)
        return 1

    manager = BotProcessManager(script_path)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(manager))
    print(f"Betika service listening on http://{args.host}:{args.port}")
    print("Endpoints: GET /health, GET /logs?from=0, POST /start, POST /stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
