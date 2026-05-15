"""
CLI entry point for the Juror system.
"""

import asyncio
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import click
import httpx

from .app import run_tui


JUROR_URL = "http://localhost:8000"


@click.group()
def cli():
    """AI Hallucination Juror - multi-agent verification for AI outputs."""


@cli.command()
@click.option("--no-tui", is_flag=True, help="Start server only")
def start(no_tui: bool) -> None:
    """Start the Juror backend, with optional TUI."""
    click.echo("Starting AI Hallucination Juror...")

    if no_tui:
        os.execv(sys.executable, [sys.executable, "-m", "server.main"])

    log_dir = Path.home() / ".juror"
    log_dir.mkdir(parents=True, exist_ok=True)
    server_log = log_dir / "server.log"
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
def logs() -> None:
    """Print the server log path."""
    log_path = Path.home() / ".juror" / "server.log"
    if log_path.exists():
        click.echo(str(log_path))
    else:
        click.echo("No server log found yet.")


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


if __name__ == "__main__":
    cli()
