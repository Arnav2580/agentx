#!/usr/bin/env python3
"""
Juror universal hook interceptor.

Reads hook JSON from stdin, checks shell commands against the Juror server,
and returns exit code 2 to block dangerous commands in compatible AI agents.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


JUROR_URL = os.environ.get("JUROR_URL", "http://localhost:8000")
LOG_FILE = Path.home() / ".juror" / "activity.log"


def log(line: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")
    except Exception:
        pass


def check_command(command: str, source: str) -> dict | None:
    try:
        payload = json.dumps({"command": command, "source": source}).encode("utf-8")
        request = urllib.request.Request(
            f"{JUROR_URL}/check-command",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError:
        log(f"WARN server_offline cmd={command[:80]}")
        return None
    except Exception as exc:
        log(f"ERROR hook_failed: {exc}")
        return None


def notify_desktop(title: str, message: str) -> None:
    try:
        system = platform.system()
        safe_title = title.replace('"', "'")
        safe_message = message[:100].replace('"', "'").replace("\n", " ")
        if system == "Darwin":
            os.system(f'osascript -e \'display notification "{safe_message}" with title "{safe_title}"\'')
        elif system == "Linux":
            os.system(f'notify-send "{safe_title}" "{safe_message}" 2>/dev/null')
        elif system == "Windows":
            toast_title = safe_title.replace("'", "''")
            toast_message = safe_message.replace("'", "''")
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
                "$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                "$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template);"
                f"$xml.GetElementsByTagName(\"text\")[0].AppendChild($xml.CreateTextNode('{toast_title}')) | Out-Null;"
                f"$xml.GetElementsByTagName(\"text\")[1].AppendChild($xml.CreateTextNode('{toast_message}')) | Out-Null;"
                "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);"
                '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Juror").Show($toast);'
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except Exception:
        pass


def detect_source() -> str:
    source = os.environ.get("JUROR_SOURCE", "unknown")
    if source and source != "unknown":
        return source
    launcher = os.environ.get("_", "")
    lowered = launcher.lower()
    if "claude" in lowered:
        return "claude_code"
    if "codex" in lowered:
        return "codex"
    if "copilot" in lowered:
        return "copilot"
    return "ai_agent"


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        raise SystemExit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    if tool_name not in {
        "Bash",
        "bash",
        "Shell",
        "terminal",
        "run_terminal_cmd",
        "execute_command",
        "run_command",
        "execute_bash",
    }:
        raise SystemExit(0)

    command = (
        tool_input.get("command")
        or tool_input.get("cmd")
        or tool_input.get("bash_command")
        or tool_input.get("shell_command")
        or ""
    ).strip()
    if not command:
        raise SystemExit(0)

    source = detect_source()
    log(f"CHECK source={source} cmd={command[:120]}")
    result = check_command(command, source)
    if result is None:
        raise SystemExit(0)

    verdict = result.get("verdict", "SAFE")
    reasons = result.get("reasons", [])
    suggestion = result.get("suggestion", "")
    confidence = result.get("confidence", 0.8)

    if verdict == "SAFE":
        log(f"SAFE source={source} cmd={command[:80]}")
        raise SystemExit(0)

    lines = [
        f"Juror {verdict} ({int(confidence * 100)}%)",
        f"Command: {command[:100]}",
        "",
        "Reasons:",
    ]
    for reason in reasons[:4]:
        lines.append(f"  - {reason}")
    if suggestion:
        lines.extend(["", f"Safer alternative: {suggestion}"])
    message = "\n".join(lines)

    log(f"{verdict} source={source} reasons={len(reasons)} cmd={command[:80]}")
    notify_desktop(f"Juror {verdict}: AI command intercepted", reasons[0] if reasons else command[:60])

    if verdict == "BLOCK":
        print(message, file=sys.stderr)
        raise SystemExit(2)

    print(message)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
