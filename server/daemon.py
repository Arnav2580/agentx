"""
Juror background daemon.

Runs silently in the background, watches sensitive files, records security
activity, and exposes a tiny local event endpoint for UI polling.
"""

from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional


JUROR_DIR = Path.home() / ".juror"
PID_FILE = JUROR_DIR / "daemon.pid"
LOG_FILE = JUROR_DIR / "activity.log"
EVENT_FILE = JUROR_DIR / "events.jsonl"


def _log(message: str, level: str = "INFO") -> None:
    JUROR_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] [{level}] {message}\n")


def _write_event(event: dict) -> None:
    JUROR_DIR.mkdir(parents=True, exist_ok=True)
    payload = dict(event)
    payload["timestamp"] = datetime.now().isoformat()
    with EVENT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def notify(title: str, body: str, urgency: str = "normal") -> None:
    try:
        system = platform.system()
        if system == "Darwin":
            safe_title = title.replace('"', '\\"')
            safe_body = body.replace('"', '\\"')
            os.system(f'osascript -e \'display notification "{safe_body}" with title "{safe_title}"\'')
        elif system == "Linux":
            urgency_flag = {"low": "low", "normal": "normal", "high": "critical"}.get(urgency, "normal")
            safe_title = title.replace('"', "'")
            safe_body = body.replace('"', "'")
            os.system(f'notify-send -u {urgency_flag} "{safe_title}" "{safe_body}" 2>/dev/null')
        elif system == "Windows":
            try:
                from win10toast import ToastNotifier

                toaster = ToastNotifier()
                toaster.show_toast(title, body, duration=6, threaded=True)
            except Exception:
                safe_title = title.replace("'", "''").replace('"', "'")
                safe_body = body[:120].replace("'", "''").replace('"', "'").replace("\n", " ")
                script = (
                    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
                    "$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                    "$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template);"
                    f'$xml.GetElementsByTagName("text")[0].AppendChild($xml.CreateTextNode(\'{safe_title}\')) | Out-Null;'
                    f'$xml.GetElementsByTagName("text")[1].AppendChild($xml.CreateTextNode(\'{safe_body}\')) | Out-Null;'
                    "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);"
                    '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Juror").Show($toast);'
                )
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
    except Exception as exc:
        _log(f"Notification failed: {exc}", "WARN")


def write_pid() -> None:
    JUROR_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def read_pid() -> Optional[int]:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def is_running() -> bool:
    pid = read_pid()
    if not pid:
        return False
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            output = (result.stdout or "").strip()
            return bool(output) and "No tasks are running" not in output and "INFO:" not in output
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def kill_daemon() -> bool:
    pid = read_pid()
    if not pid:
        return False

    if platform.system() == "Windows":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            time.sleep(0.5)
            PID_FILE.unlink(missing_ok=True)
            return True
        except Exception as exc:
            _log(f"Failed to stop daemon: {exc}", "ERROR")
            return False

    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        PID_FILE.unlink(missing_ok=True)
        return True
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return True
    except Exception as exc:
        _log(f"Failed to stop daemon: {exc}", "ERROR")
        return False


def start_file_watcher(watch_dirs: list[str]) -> None:
    suspicious_files = {
        ".env",
        ".npmrc",
        ".pypirc",
        "requirements.txt",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "Pipfile",
        "Pipfile.lock",
        "setup.py",
        "pyproject.toml",
        ".gitconfig",
        "authorized_keys",
        "known_hosts",
        "id_rsa",
        "id_ed25519",
        "credentials",
    }
    file_mtimes: dict[str, float] = {}

    def scan() -> None:
        for watch_dir in watch_dirs:
            if not os.path.exists(watch_dir):
                continue
            for root, dirs, files in os.walk(watch_dir):
                dirs[:] = [
                    directory
                    for directory in dirs
                    if directory not in {".git", "node_modules", "__pycache__", ".venv", "venv", ".cache", "dist", "build", ".tox"}
                ]
                for filename in files:
                    if filename not in suspicious_files and not filename.endswith((".pem", ".key", ".p12", ".pfx", ".env")):
                        continue
                    path = os.path.join(root, filename)
                    try:
                        modified = os.path.getmtime(path)
                    except OSError:
                        continue
                    previous = file_mtimes.get(path)
                    if previous is not None and modified != previous:
                        _log(f"MODIFIED sensitive file: {path}")
                        _write_event({"type": "file_modified", "path": path, "severity": "warn"})
                        if ".env" in filename or filename in {"id_rsa", "id_ed25519", "credentials"}:
                            notify("Juror warning", f"Sensitive file changed: {filename}", urgency="high")
                    file_mtimes[path] = modified
        _log("Manual file scan completed")

    return scan


def start_package_monitor() -> None:
    npm_dir = Path.home() / ".npm"
    pip_dir = Path.home() / ".cache" / "pip"
    known_packages: set[tuple[str, str]] = set()

    def scan() -> None:
        nonlocal known_packages
        current: set[tuple[str, str]] = set()

        if npm_dir.exists():
            try:
                for entry in npm_dir.iterdir():
                    if entry.is_dir():
                        current.add(("npm", entry.name))
            except Exception:
                pass

        if pip_dir.exists():
            try:
                for entry in pip_dir.iterdir():
                    if entry.is_dir():
                        current.add(("PyPI", entry.name))
            except Exception:
                pass

        new_packages = current - known_packages
        if known_packages and new_packages:
            for ecosystem, package in sorted(new_packages):
                _log(f"NEW package detected: {package} ({ecosystem})")
                _write_event({"type": "new_package", "package": package, "ecosystem": ecosystem, "severity": "info"})

        known_packages = current
        _log("Manual package scan completed")

    return scan


def start_event_server(port: int = 8001, trigger_scan=None) -> None:
    class EventHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/events":
                try:
                    if EVENT_FILE.exists():
                        lines = EVENT_FILE.read_text(encoding="utf-8").strip().splitlines()
                        events = [json.loads(line) for line in lines[-50:] if line.strip()]
                    else:
                        events = []
                except Exception:
                    events = []
                body = json.dumps({"events": events}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == "/status":
                body = json.dumps({"running": True, "pid": os.getpid()}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/scan":
                if hasattr(self.server, "trigger_scan"):
                    self.server.trigger_scan()
                body = json.dumps({"status": "scan_completed"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
                
            self.send_response(404)
            self.end_headers()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

    def serve() -> None:
        try:
            server = HTTPServer(("127.0.0.1", port), EventHandler)
            setattr(server, "trigger_scan", trigger_scan)
            server.serve_forever()
        except OSError:
            _log(f"Event server port {port} unavailable", "WARN")

    threading.Thread(target=serve, daemon=True).start()
    _log(f"Event server started on 127.0.0.1:{port} with manual scan endpoint")


def run_daemon(workspace: Optional[str] = None) -> None:
    write_pid()
    _log("Juror daemon started")
    notify("Juror active", "AI command interceptor running in the background", urgency="low")

    watch_dirs: list[str] = []
    if workspace and os.path.exists(workspace):
        watch_dirs.append(workspace)

    for candidate in [
        os.path.expanduser("~/projects"),
        os.path.expanduser("~/dev"),
        os.path.expanduser("~/code"),
        os.getcwd(),
    ]:
        if os.path.exists(candidate) and candidate not in watch_dirs:
            watch_dirs.append(candidate)

    for candidate in [str(Path.home() / ".npm"), str(Path.home() / ".cache" / "pip")]:
        if os.path.exists(candidate) and candidate not in watch_dirs:
            watch_dirs.append(candidate)

    scan_files = start_file_watcher(watch_dirs)
    scan_packages = start_package_monitor()
    
    def trigger_scan():
        scan_files()
        scan_packages()

    start_event_server(8001, trigger_scan=trigger_scan)
    _log(f"Watching {len(watch_dirs)} directories manually")

    def handle_signal(*_args) -> None:
        _log("Daemon stopped by signal")
        PID_FILE.unlink(missing_ok=True)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while True:
        time.sleep(10)
        try:
            import urllib.request

            urllib.request.urlopen(
                f"http://localhost:{os.environ.get('SERVER_PORT', 8000)}/health",
                timeout=3,
            )
        except Exception:
            _log("Main server not responding", "WARN")


def start_background(workspace: Optional[str] = None) -> int:
    JUROR_DIR.mkdir(parents=True, exist_ok=True)
    system = platform.system()

    if system == "Windows":
        env = os.environ.copy()
        if workspace:
            env["JUROR_DAEMON_WORKSPACE"] = workspace
        with LOG_FILE.open("a", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--daemon-worker"],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                stdout=log_handle,
                stderr=log_handle,
                env=env,
            )
        PID_FILE.write_text(str(process.pid), encoding="utf-8")
        return process.pid

    pid = os.fork()
    if pid > 0:
        return pid

    os.setsid()

    pid2 = os.fork()
    if pid2 > 0:
        raise SystemExit(0)

    sys.stdout.flush()
    sys.stderr.flush()
    with open("/dev/null", "r", encoding="utf-8") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with LOG_FILE.open("a", encoding="utf-8") as log_handle:
        os.dup2(log_handle.fileno(), sys.stdout.fileno())
        os.dup2(log_handle.fileno(), sys.stderr.fileno())
        run_daemon(workspace)
    raise SystemExit(0)


if __name__ == "__main__":
    if "--daemon-worker" in sys.argv:
        JUROR_DIR.mkdir(parents=True, exist_ok=True)
        run_daemon(os.environ.get("JUROR_DAEMON_WORKSPACE"))
