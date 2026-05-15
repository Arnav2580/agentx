"""
CLI entry point for the Juror system.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import click
import httpx

from .app import run_tui


JUROR_URL = "http://localhost:8000"
JUROR_DIR = Path.home() / ".juror"
PID_FILE = JUROR_DIR / "daemon.pid"
LOG_FILE = JUROR_DIR / "activity.log"
EVENT_FILE = JUROR_DIR / "events.jsonl"
INSTALL_DIR = Path.home() / ".juror-app"


@click.group()
def cli() -> None:
    """AI Hallucination Juror - multi-agent verification for AI outputs."""


@cli.command()
@click.option("--no-tui", is_flag=True, help="Start server only")
def start(no_tui: bool) -> None:
    """Start the Juror backend, with optional TUI."""
    click.echo("Starting AI Hallucination Juror...")

    if no_tui:
        os.execv(sys.executable, [sys.executable, "-m", "server.main"])

    JUROR_DIR.mkdir(parents=True, exist_ok=True)
    server_log = JUROR_DIR / "server.log"
    log_file = server_log.open("w", encoding="utf-8")
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "server.main"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    click.echo(f"Server started (PID: {server_proc.pid}) on {JUROR_URL}")
    time.sleep(2)
    run_tui()


@cli.command()
@click.argument("command", nargs=-1, required=True)
def run(command: tuple[str, ...]) -> None:
    """Run a command, capture its output, and send it to the jury."""
    cmd = list(command)
    click.echo(f"Running: {' '.join(cmd)}")
    click.echo("Juror active - capturing output for verification...\n")

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")

    click.echo("-" * 60)
    click.echo(output)
    click.echo("-" * 60)

    if output.strip():
        click.echo("\nSending to jury for verification...")
        asyncio.run(_verify_and_display(output, source="terminal"))
    else:
        click.echo("No output captured from command.")


@cli.command()
@click.argument("filepath", type=click.Path(exists=True, dir_okay=False))
def verify(filepath: str) -> None:
    """Verify the contents of a file."""
    content = Path(filepath).read_text(encoding="utf-8")
    click.echo(f"Verifying: {filepath}")
    asyncio.run(_verify_and_display(content, source="terminal"))


@cli.command()
def status() -> None:
    """Check if the Juror server is running."""
    try:
        response = httpx.get(f"{JUROR_URL}/health", timeout=3.0)
        response.raise_for_status()
        data = response.json()
    except Exception:
        click.echo("Juror server is NOT running")
        click.echo("Run: juror start")
        return

    click.echo("Juror server is RUNNING")
    click.echo(f"  Version: {data.get('version')}")
    click.echo(f"  Model: {data.get('model')}")
    click.echo(f"  URL: {data.get('server')}")


@cli.command()
def history() -> None:
    """Show recent verdict history."""
    try:
        response = httpx.get(f"{JUROR_URL}/history?limit=10", timeout=3.0)
        response.raise_for_status()
        data = response.json()
    except Exception:
        click.echo("Cannot connect to Juror server. Run: juror start")
        return

    click.echo(f"\nLast {len(data.get('history', []))} verdicts:\n")
    for entry in data.get("history", []):
        final = entry.get("final_verdict", "?")
        icon = "OK" if final == "APPROVED" else "WARN" if final == "FLAGGED" else "BLOCK"
        click.echo(
            f"{icon} [{entry.get('timestamp', '')[:19]}] {final} | "
            f"Domain: {entry.get('domain', '?')} | Fails: {entry.get('fail_count', 0)}/5"
        )


@cli.command()
def install() -> None:
    """Install command interception hooks and start the background daemon."""
    hooks_src = _hooks_source_dir()
    hooks_dst = JUROR_DIR / "hooks"
    hooks_dst.mkdir(parents=True, exist_ok=True)

    click.echo("\nInstalling command interceptor hooks...")
    installed = 0
    for filename in ("intercept.py", "shell_hook.sh", "claude_settings_template.json"):
        src = hooks_src / filename
        dst = hooks_dst / filename
        if not src.exists():
            continue
        shutil.copy2(src, dst)
        try:
            if dst.suffix in {".py", ".sh"}:
                os.chmod(dst, 0o755)
        except Exception:
            pass
        installed += 1
    _print_success(f"Installed {installed} hook asset(s) into {hooks_dst}")

    _configure_claude_hooks(hooks_dst / "claude_settings_template.json")
    _configure_shell_hooks(hooks_dst / "shell_hook.sh")

    click.echo("Starting background daemon...")
    from server.daemon import is_running, read_pid, start_background

    if not is_running():
        start_background(os.getcwd())
        time.sleep(1.0)
    if is_running():
        _print_success("Juror daemon running silently in the background.", f"PID: {read_pid()}", f"Logs: {LOG_FILE}")
    else:
        _print_error("Daemon did not come up cleanly.", f"Check: {LOG_FILE}")


@cli.command("install-service")
def install_service() -> None:
    """Install Juror as an auto-start service."""
    system = platform.system()
    juror_path = shutil.which("juror")

    if not juror_path:
        click.echo("Could not find 'juror' in PATH. Install the package first.")
        return

    click.echo(f"Installing Juror as a system service on {system}...")

    if system == "Darwin":
        _install_macos(juror_path)
    elif system == "Linux":
        _install_linux(juror_path)
    elif system == "Windows":
        _install_windows(juror_path)
    else:
        click.echo(f"Unsupported OS: {system}")


@cli.command()
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
def uninstall(yes: bool) -> None:
    """Remove Juror's installed footprint from this machine."""
    message = (
        "This removes the installed Juror footprint: ~/.juror-app, ~/.juror, hooks, "
        "daemon state, local VS Code extension copies, and service files."
    )
    if not yes and not click.confirm(f"{message}\n\nContinue?", default=False):
        _print_info("Uninstall cancelled.")
        return

    removed: list[str] = []
    notes: list[str] = []

    try:
        from server.daemon import is_running, kill_daemon

        if is_running():
            if kill_daemon():
                removed.append("background daemon")
            else:
                notes.append("daemon may still be running; stop it manually if needed")
    except Exception:
        notes.append("could not fully verify daemon shutdown")

    removed.extend(_remove_service_artifacts())
    removed.extend(_remove_shell_hook_lines())
    removed.extend(_remove_claude_hooks())
    removed.extend(_remove_vscode_extension_dirs())

    for wrapper in (Path.home() / ".local" / "bin" / "juror", Path.home() / ".local" / "bin" / "juror.bat"):
        if _remove_path(wrapper):
            removed.append(str(wrapper))

    if _remove_path(JUROR_DIR):
        removed.append(str(JUROR_DIR))

    current_root = Path(__file__).resolve().parents[1]
    if INSTALL_DIR.exists():
        if current_root == INSTALL_DIR or current_root.is_relative_to(INSTALL_DIR):
            if _schedule_remove_tree(INSTALL_DIR):
                removed.append(f"{INSTALL_DIR} (scheduled for cleanup after exit)")
            else:
                notes.append(f"could not schedule removal of {INSTALL_DIR}")
        elif _remove_path(INSTALL_DIR):
            removed.append(str(INSTALL_DIR))

    _print_success("Juror uninstall complete.")
    if removed:
        click.echo("Removed:")
        for item in removed:
            click.echo(f"  - {item}")
        click.echo()
    if notes:
        click.echo("Notes:")
        for item in notes:
            click.echo(f"  - {item}")
        click.echo()
    click.echo("If you still have a separate dev checkout of the repo, delete that folder manually when you no longer need it.")


@cli.command()
def logs() -> None:
    """Print the server log path."""
    log_path = JUROR_DIR / "server.log"
    if log_path.exists():
        click.echo(str(log_path))
    else:
        click.echo("No server log found yet.")


@cli.group()
def daemon() -> None:
    """Background daemon commands."""


@daemon.command("start")
@click.option("--workspace", default=None, help="Workspace directory to watch")
def daemon_start(workspace: str | None) -> None:
    """Start Juror as a silent background daemon."""
    from server.daemon import is_running, read_pid, start_background

    if is_running():
        _print_info("Daemon already running.", "Use 'juror daemon status' to inspect it.")
        return

    workspace = workspace or os.getcwd()
    start_background(workspace)
    time.sleep(1.0)

    if is_running():
        _print_success(
            "Juror daemon started silently.",
            f"PID: {read_pid()}",
            f"Watching: {workspace}",
            f"Logs: {LOG_FILE}",
            "Stop with: juror stop",
        )
    else:
        _print_error("Daemon failed to start.", f"Check logs: {LOG_FILE}")


@daemon.command("status")
def daemon_status() -> None:
    """Check daemon status."""
    from server.daemon import is_running, read_pid

    if is_running():
        _print_success(f"Juror daemon is RUNNING (PID {read_pid()})")
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
            recent = [line for line in lines[-5:] if line.strip()]
            if recent:
                click.echo("Recent activity:")
                for line in recent:
                    _colorize_log_line(f"  {line}")
                click.echo()
        return

    _print_info("Juror daemon is not running.", "Start it with: juror daemon start")


@daemon.command("logs")
@click.option("--lines", "-n", default=30, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def daemon_logs(lines: int, follow: bool) -> None:
    """View daemon activity log."""
    if not LOG_FILE.exists():
        _print_info("No daemon log yet.", "Start the daemon first: juror daemon start")
        return

    if follow:
        click.echo(f"Following {LOG_FILE} (Ctrl+C to stop)\n")
        _tail_follow(LOG_FILE)
        return

    content = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    for line in content[-lines:]:
        _colorize_log_line(line)


@cli.command("stop")
def stop() -> None:
    """Stop the Juror background daemon."""
    from server.daemon import is_running, kill_daemon

    if not is_running():
        _print_info("Daemon is not running.")
        return

    if kill_daemon():
        _print_success("Juror daemon stopped.")
    else:
        _print_error("Could not stop daemon.", f"Try manually clearing: {PID_FILE}")


@cli.command("wakeup")
@click.option("--workspace", default=None, help="Workspace directory to watch")
def wakeup(workspace: str | None) -> None:
    """Restart the Juror daemon."""
    from server.daemon import is_running, kill_daemon, read_pid, start_background

    if is_running():
        click.echo("Stopping existing daemon...")
        kill_daemon()
        time.sleep(0.5)

    start_background(workspace or os.getcwd())
    time.sleep(1.0)

    if read_pid():
        _print_success(f"Juror daemon restarted (PID {read_pid()})")
    else:
        _print_error("Failed to restart daemon.", f"Check logs: {LOG_FILE}")


@cli.command("check")
@click.argument("command")
@click.option("--source", default="manual", help="Source agent name")
def check_cmd(command: str, source: str) -> None:
    """Manually check a command for risks before running it."""
    asyncio.run(_check_and_print(command, source))


def _hooks_source_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "server" / "hooks"


def _remove_path(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True
    except Exception:
        return False


def _schedule_remove_tree(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        if platform.system() == "Windows":
            safe_path = str(path).replace("'", "''")
            command = (
                f"Start-Sleep -Seconds 2; "
                f"Remove-Item -LiteralPath '{safe_path}' -Recurse -Force -ErrorAction SilentlyContinue"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                ["/bin/sh", "-c", f"sleep 2; rm -rf {json.dumps(str(path))}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        return True
    except Exception:
        return False


def _configure_claude_hooks(template_path: Path) -> None:
    if not template_path.exists():
        return

    claude_config = Path.home() / ".claude" / "settings.json"
    claude_config.parent.mkdir(parents=True, exist_ok=True)
    template = json.loads(template_path.read_text(encoding="utf-8"))

    if claude_config.exists():
        try:
            existing = json.loads(claude_config.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    else:
        existing = {}

    existing.setdefault("hooks", {})
    for hook_name, template_entries in template.get("hooks", {}).items():
        existing["hooks"].setdefault(hook_name, [])
        current_entries = existing["hooks"][hook_name]
        for entry in template_entries:
            if entry not in current_entries:
                current_entries.append(entry)

    claude_config.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    _print_success("Claude Code hook template installed.", f"Config: {claude_config}")


def _remove_claude_hooks() -> list[str]:
    claude_config = Path.home() / ".claude" / "settings.json"
    if not claude_config.exists():
        return []

    try:
        data = json.loads(claude_config.read_text(encoding="utf-8"))
    except Exception:
        return []

    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return []

    removed = False
    for phase in ("PreToolUse", "PostToolUse"):
        entries = hooks.get(phase)
        if not isinstance(entries, list):
            continue
        filtered_entries = []
        for entry in entries:
            entry_hooks = entry.get("hooks", []) if isinstance(entry, dict) else []
            kept_hooks = []
            for hook in entry_hooks:
                command = hook.get("command", "") if isinstance(hook, dict) else ""
                if "intercept.py" in command or "activity.log" in command:
                    removed = True
                    continue
                kept_hooks.append(hook)
            if kept_hooks:
                new_entry = dict(entry)
                new_entry["hooks"] = kept_hooks
                filtered_entries.append(new_entry)
            else:
                removed = True
        if filtered_entries:
            hooks[phase] = filtered_entries
        elif phase in hooks:
            hooks.pop(phase, None)

    if not hooks:
        data.pop("hooks", None)

    if removed:
        claude_config.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return [str(claude_config)]
    return []


def _configure_shell_hooks(shell_hook_path: Path) -> None:
    shell_line = "\n# Juror universal shell hook\nsource ~/.juror/hooks/shell_hook.sh\n"
    updated_files: list[str] = []

    if platform.system() == "Windows":
        _print_info("Shell RC auto-configuration skipped on Windows.", f"Hook available at: {shell_hook_path}")
        return

    for rc_file in [Path.home() / ".bashrc", Path.home() / ".zshrc"]:
        if not rc_file.exists():
            continue
        content = rc_file.read_text(encoding="utf-8")
        if "shell_hook.sh" in content:
            continue
        with rc_file.open("a", encoding="utf-8") as handle:
            handle.write(shell_line)
        updated_files.append(rc_file.name)

    if updated_files:
        _print_success("Shell hook added.", "Updated: " + ", ".join(updated_files))
    else:
        _print_info("Shell hook was already present or no rc files were found.", f"Hook available at: {shell_hook_path}")


def _remove_shell_hook_lines() -> list[str]:
    if platform.system() == "Windows":
        return []

    removed_from: list[str] = []
    patterns = {"# Juror universal shell hook", "source ~/.juror/hooks/shell_hook.sh"}
    for rc_file in (Path.home() / ".bashrc", Path.home() / ".zshrc"):
        if not rc_file.exists():
            continue
        lines = rc_file.read_text(encoding="utf-8").splitlines()
        filtered = [line for line in lines if not any(pattern in line for pattern in patterns)]
        if filtered != lines:
            rc_file.write_text("\n".join(filtered).rstrip() + "\n", encoding="utf-8")
            removed_from.append(str(rc_file))
    return removed_from


def _install_macos(juror_path: str) -> None:
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.juror.mcp</string>
  <key>ProgramArguments</key>
  <array>
    <string>{juror_path}</string>
    <string>start</string>
    <string>--no-tui</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{Path.home() / '.juror' / 'juror.log'}</string>
  <key>StandardErrorPath</key>
  <string>{Path.home() / '.juror' / 'juror-error.log'}</string>
</dict>
</plist>"""

    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.juror.mcp.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(plist_content, encoding="utf-8")
    subprocess.run(["launchctl", "load", str(plist_path)], check=False)
    click.echo(f"Service installed at {plist_path}")


def _install_linux(juror_path: str) -> None:
    service_content = f"""[Unit]
Description=AI Hallucination Juror MCP Server
After=network.target

[Service]
Type=simple
ExecStart={juror_path} start --no-tui
Restart=always
RestartSec=3
StandardOutput=append:{Path.home() / '.juror' / 'juror.log'}
StandardError=append:{Path.home() / '.juror' / 'juror-error.log'}

[Install]
WantedBy=default.target
"""

    service_path = Path.home() / ".config" / "systemd" / "user" / "juror.service"
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(service_content, encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "juror"], check=False)
    subprocess.run(["systemctl", "--user", "start", "juror"], check=False)
    click.echo(f"systemd service installed at {service_path}")


def _install_windows(juror_path: str) -> None:
    script_path = Path(__file__).resolve().parents[1] / "persistence" / "windows" / "install-service.ps1"
    if not script_path.exists():
        click.echo(f"Windows installer script not found: {script_path}")
        return
    subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-JurorPath",
            juror_path,
        ],
        check=False,
    )
    click.echo("Task Scheduler installer executed.")


def _remove_service_artifacts() -> list[str]:
    removed: list[str] = []
    system = platform.system()

    if system == "Darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.juror.mcp.plist"
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
            if _remove_path(plist_path):
                removed.append(str(plist_path))
    elif system == "Linux":
        service_path = Path.home() / ".config" / "systemd" / "user" / "juror.service"
        if service_path.exists():
            subprocess.run(["systemctl", "--user", "stop", "juror"], check=False)
            subprocess.run(["systemctl", "--user", "disable", "juror"], check=False)
            if _remove_path(service_path):
                removed.append(str(service_path))
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    elif system == "Windows":
        subprocess.run(["schtasks", "/Delete", "/TN", "AIHallucinationJuror", "/F"], check=False, capture_output=True)
        removed.append("Windows task AIHallucinationJuror (if present)")

    return removed


def _remove_vscode_extension_dirs() -> list[str]:
    removed: list[str] = []
    base_dirs = [Path.home() / ".vscode" / "extensions", Path.home() / ".vscode-insiders" / "extensions"]
    if platform.system() == "Windows":
        appdata = os.environ.get("USERPROFILE")
        if appdata:
            base_dirs.extend(
                [
                    Path(appdata) / ".vscode" / "extensions",
                    Path(appdata) / ".vscode-insiders" / "extensions",
                ]
            )

    seen: set[Path] = set()
    for base_dir in base_dirs:
        if base_dir in seen or not base_dir.exists():
            continue
        seen.add(base_dir)
        for candidate in base_dir.glob("*ai-hallucination-juror*"):
            if _remove_path(candidate):
                removed.append(str(candidate))
    return removed


async def _verify_and_display(content: str, source: str = "terminal") -> None:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{JUROR_URL}/verify", json={"content": content, "source": source})
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        click.echo(f"Juror server error: {exc}")
        click.echo("Is the server running? Run: juror start --no-tui")
        return

    final = data.get("final_verdict", "?")
    fail_count = int(data.get("fail_count", 0))
    confidence = float(data.get("overall_confidence", 0))

    click.echo(f"\n{'-' * 60}")
    click.echo(f"JURY VERDICT: {final}")
    click.echo(f"Confidence: {confidence:.0%} | Agents Failed: {fail_count}/5")
    click.echo(f"{'-' * 60}")

    for agent in data.get("agent_results", []):
        click.echo(f"  - Agent {agent['agent_id']} ({agent['agent_name']}): {agent['verdict']}")
        for issue in agent.get("issues", []):
            click.echo(f"    * {issue}")

    if data.get("issues_summary"):
        click.echo("\nIssues found:")
        for issue in data["issues_summary"][:5]:
            click.echo(f"  * {issue}")

    if final == "BLOCKED" and data.get("correction"):
        click.echo("\nCorrected output (Agent 6):")
        click.echo("-" * 40)
        click.echo(data["correction"])


async def _check_and_print(command: str, source: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{JUROR_URL}/check-command",
                json={"command": command, "source": source},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        click.echo(f"Error: {exc}\nIs the server running? juror start")
        return

    verdict = data.get("verdict", "?")
    reasons = data.get("reasons", [])
    suggestion = data.get("suggestion", "")
    packages = data.get("packages_checked", [])

    colors = {"SAFE": (122, 184, 122), "WARN": (200, 160, 64), "BLOCK": (200, 96, 96)}
    icons = {"SAFE": "OK", "WARN": "WARN", "BLOCK": "BLOCK"}
    color = colors.get(verdict, (168, 144, 112))
    click.echo()
    click.echo(click.style(f"{icons.get(verdict, '?')} JUROR: {verdict}", fg=color, bold=True))
    click.echo(f"Command: {command}")

    if reasons:
        click.echo("\nReasons:")
        for reason in reasons:
            click.echo(f"  - {reason}")

    if packages:
        click.echo("\nPackages:")
        for package in packages:
            if not package.get("exists"):
                click.echo(click.style(f"  X {package['package']}: does not exist on {package['ecosystem']}", fg=(200, 96, 96)))
            elif package.get("cve_count", 0) > 0:
                click.echo(click.style(f"  ! {package['package']}: {package['cve_count']} CVEs", fg=(200, 160, 64)))
            else:
                click.echo(click.style(f"  OK {package['package']}: looks legitimate", fg=(122, 184, 122)))

    if suggestion:
        click.echo(f"\nSafer alternative:\n  {suggestion}")
    click.echo()


def _colorize_log_line(line: str) -> None:
    if "[ERROR]" in line or "BLOCK" in line:
        click.echo(click.style(line, fg=(200, 96, 96)))
    elif "[WARN]" in line or "WARN" in line:
        click.echo(click.style(line, fg=(200, 160, 64)))
    elif "SAFE" in line:
        click.echo(click.style(line, fg=(122, 184, 122)))
    elif "[INFO]" in line:
        click.echo(click.style(line, fg=(168, 144, 112)))
    else:
        click.echo(click.style(line, fg=(107, 80, 64)))


def _tail_follow(filepath: Path) -> None:
    with filepath.open("r", encoding="utf-8") as handle:
        handle.seek(0, 2)
        try:
            while True:
                line = handle.readline()
                if line:
                    _colorize_log_line(line.rstrip())
                else:
                    time.sleep(0.3)
        except KeyboardInterrupt:
            pass


def _print_success(*lines: Any) -> None:
    for index, line in enumerate(lines):
        prefix = "OK " if index == 0 else "   "
        color = (122, 184, 122) if index == 0 else (168, 144, 112)
        click.echo(click.style(f"{prefix}{line}", fg=color))
    click.echo()


def _print_info(*lines: Any) -> None:
    for line in lines:
        click.echo(click.style(f"INFO {line}", fg=(168, 144, 112)))
    click.echo()


def _print_error(*lines: Any) -> None:
    for line in lines:
        click.echo(click.style(f"ERR {line}", fg=(200, 96, 96)))
    click.echo()


if __name__ == "__main__":
    cli()
