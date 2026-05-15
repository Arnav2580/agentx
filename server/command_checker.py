"""
Universal command checker for AI agent tool interception.

The checker layers:
1. Fast regex-based pattern analysis
2. Package threat intel from OSV.dev, npm, and PyPI
3. Gemini reasoning for suspicious or ambiguous commands
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from .grok_client import call_grok, grok_available, parse_agent_json


@dataclass
class ThreatIntel:
    package: str
    ecosystem: str
    vulnerabilities: list[dict] = field(default_factory=list)
    cve_count: int = 0
    weekly_downloads: Optional[int] = None
    age_days: Optional[int] = None
    exists: bool = True
    suspicious_age: bool = False
    suspicious_downloads: bool = False


@dataclass
class CommandRisk:
    verdict: str
    confidence: float
    reasons: list[str]
    suggestion: str
    category: str
    packages_checked: list[ThreatIntel] = field(default_factory=list)
    raw_command: str = ""


PACKAGE_PATTERNS = [
    (r"\bnpm\s+(?:install|i|add)\s+(.+?)(?:\s+--|$)", "npm"),
    (r"\byarn\s+(?:add|install)\s+(.+?)(?:\s+--|$)", "npm"),
    (r"\bpnpm\s+(?:add|install)\s+(.+?)(?:\s+--|$)", "npm"),
    (r"\bnpx\s+(?!create-)(\S+)", "npm"),
    (r"\bpip(?:3)?\s+install\s+(.+?)(?:\s+--|$)", "PyPI"),
    (r"\bpoetry\s+add\s+(.+?)(?:\s+--|$)", "PyPI"),
    (r"\bcargo\s+(?:add|install)\s+(\S+)", "crates.io"),
    (r"\bgem\s+install\s+(\S+)", "RubyGems"),
    (r"\bgo\s+get\s+(\S+)", "Go"),
    (r"\bcomposer\s+require\s+(\S+)", "Packagist"),
]

DESTRUCTIVE_PATTERNS = [
    (r"\brm\s+-[rRfF]{1,4}\s+(?:/|~|\$HOME|\.\.?)(?:\s|$)", "rm -rf on root, home, or current directory"),
    (r"\brm\s+-rf\s+\*", "rm -rf on wildcard deletes everything in scope"),
    (r"\bdd\s+if=/dev/zero\s+of=", "disk wipe command"),
    (r"\bmkfs\.", "filesystem format erases disk contents"),
    (r"\b(?:DROP|TRUNCATE)\s+TABLE\b", "SQL table destruction"),
    (r"\bDROP\s+DATABASE\b", "SQL database destruction"),
    (r"\bshred\s+-", "secure deletion prevents recovery"),
    (r"\bgit\s+(?:push\s+.*--force|push\s+-f\b)", "force push rewrites remote history"),
    (r"\bgit\s+reset\s+--hard\b", "hard git reset discards local changes"),
    (r"\bchmod\s+(?:777|a\+rwx)\b", "world-writable permissions are dangerous"),
    (r">\s*/etc/", "writes directly into system configuration"),
    (r"\brmdir\s+/[sS]\s*/[qQ]\b", "Windows recursive directory deletion"),
    (r"\bdel\s+/[fF]\s+/[sS]\b", "Windows force recursive delete"),
    (r"\bformat\s+[a-zA-Z]:\b", "Windows disk format"),
    (r"\brd\s+/s\s+/q\b", "Windows recursive directory removal"),
]

NETWORK_SUSPICIOUS = [
    (r"\bcurl\b.*\|\s*(?:bash|sh|python|node|ruby|perl)\b", "piping a remote script directly into a shell"),
    (r"\bwget\b.*\|\s*(?:bash|sh|python|node)\b", "piping a remote download directly into a shell"),
    (r"\b(?:curl|wget)\b.*(?:pastebin\.com|hastebin\.com|paste\.ee|rentry\.co)", "downloading code from a paste site"),
    (r"\bnc\s+-[lLe]\b", "netcat listener can expose a backdoor"),
    (r"\bnc\b.*\s+-e\s+", "netcat command execution pattern"),
    (r"\bpython[23]?\s+-c\s+.*(?:socket|requests|urllib).*(?:exec|eval)", "inline Python downloads then executes code"),
    (r"/dev/tcp/", "TCP shell redirection pattern"),
]

PRIVILEGE_PATTERNS = [
    (r"\bsudo\s+su\b", "escalating to a root shell"),
    (r"\bsudo\s+-s\b", "opening a root shell"),
    (r"\bchmod\s+[+u]*s\s", "setting SUID bit"),
    (r"\bvisudo\b", "editing sudoers"),
    (r"\becho\s+.*>>\s*/etc/sudoers\b", "writing to sudoers file"),
    (r"\busermod\s+.*-aG\s+sudo\b", "adding a user to the sudo group"),
]

SECRET_EXPOSURE = [
    (r"\bcat\s+(?:\.env|\.env\.\w+|secrets\.ya?ml|credentials)\b", "reading a secrets file"),
    (r"\becho\s+\$(?:AWS_|GOOGLE_|GITHUB_|ANTHROPIC_|OPENAI_|API_KEY|SECRET|TOKEN|PASSWORD)\w*", "printing a secret environment variable"),
    (r"\bprintenv\s+(?:AWS_|GOOGLE_|ANTHROPIC_|API_KEY|SECRET|TOKEN)", "printing sensitive environment variables"),
    (r"\bgit\s+add\s+(?:\.env|secrets|credentials|\.pem|\.key)\b", "staging secrets for commit"),
    (r"\benv\s*\|.*grep\s+-i\s+(?:key|secret|token|password)", "searching environment output for secrets"),
    (r"\bhistory\b", "reading shell history can expose secrets"),
]

CODE_EXECUTION = [
    (r"\beval\s*\(", "eval executes arbitrary code"),
    (r"\bexec\s*\(.*__import__", "dynamic import through exec"),
    (r"\bpython[23]?\s+-c\s+[\"'](?:import\s+base64|__import__)", "obfuscated inline Python execution"),
    (r"\bnode\s+-e\s+[\"'].*require.*http", "inline Node script that reaches the network"),
    (r"\bbash\s+-c\s+\$\(", "command substitution inside bash -c"),
]

COMMAND_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["SAFE", "WARN", "BLOCK"]},
        "confidence": {"type": "number"},
        "primary_reason": {"type": "string"},
        "all_reasons": {"type": "array", "items": {"type": "string"}},
        "suggestion": {"type": "string"},
        "risk_category": {
            "type": "string",
            "enum": [
                "package_install",
                "destructive",
                "network",
                "privilege",
                "secret",
                "execution",
                "safe",
                "unknown",
            ],
        },
    },
    "required": [
        "verdict",
        "confidence",
        "primary_reason",
        "all_reasons",
        "suggestion",
        "risk_category",
    ],
}

COMMAND_ANALYSIS_PROMPT = """You are a security agent analyzing a terminal command before execution by an AI coding assistant.

Command: {command}
Source AI agent: {source}
Pattern findings: {patterns}
Package threat intel: {intel}

Analyze this command for security risks. Consider:
1. Does the command have a hidden side effect beyond the stated task?
2. Is there a safer alternative that achieves the same goal?
3. What is the worst-case outcome on a production machine?
4. Does the combination of actions suggest malicious or careless intent?
5. Are any package names typosquatting a known library?

Respond in this exact JSON shape:
{{
  "verdict": "SAFE" or "WARN" or "BLOCK",
  "confidence": 0.0,
  "primary_reason": "one sentence",
  "all_reasons": ["reason 1", "reason 2"],
  "suggestion": "specific safer alternative",
  "risk_category": "package_install|destructive|network|privilege|secret|execution|safe|unknown"
}}
"""


def _normalize_package_name(package: str, ecosystem: str) -> str:
    package = package.strip().strip("\"'")
    if ecosystem == "npm":
        if package.startswith("@") and package.count("@") > 1:
            return package.rsplit("@", 1)[0]
        if not package.startswith("@") and "@" in package:
            return package.split("@", 1)[0]
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if separator in package:
            package = package.split(separator, 1)[0]
            break
    return package.strip()


def parse_packages(command: str) -> list[tuple[str, str]]:
    packages: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for pattern, ecosystem in PACKAGE_PATTERNS:
        for match in re.findall(pattern, command, re.IGNORECASE):
            parts = str(match).strip().split()
            for part in parts:
                if part.startswith("-"):
                    continue
                normalized = _normalize_package_name(part, ecosystem)
                if len(normalized) < 2:
                    continue
                item = (normalized, ecosystem)
                if item not in seen:
                    packages.append(item)
                    seen.add(item)

    return packages[:10]


def quick_pattern_check(command: str) -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    all_checks = [
        ("destructive", DESTRUCTIVE_PATTERNS, "BLOCK"),
        ("network", NETWORK_SUSPICIOUS, "WARN"),
        ("privilege", PRIVILEGE_PATTERNS, "WARN"),
        ("secret", SECRET_EXPOSURE, "WARN"),
        ("execution", CODE_EXECUTION, "WARN"),
    ]
    for category, patterns, severity in all_checks:
        for pattern, description in patterns:
            if re.search(pattern, command, re.IGNORECASE):
                findings.append((category, description, severity))
    return findings


async def check_npm_package(package: str) -> ThreatIntel:
    intel = ThreatIntel(package=package, ecosystem="npm")

    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            response = await client.get(f"https://registry.npmjs.org/{package}")
            if response.status_code == 404:
                intel.exists = False
                return intel

            data = response.json()
            created = data.get("time", {}).get("created")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    intel.age_days = (datetime.now(timezone.utc) - created_dt).days
                    intel.suspicious_age = (intel.age_days or 0) < 30
                except Exception:
                    pass

            try:
                downloads = await client.get(f"https://api.npmjs.org/downloads/point/last-week/{package}")
                if downloads.status_code == 200:
                    intel.weekly_downloads = int(downloads.json().get("downloads", 0))
                    intel.suspicious_downloads = intel.weekly_downloads < 100
            except Exception:
                pass
        except Exception:
            pass

        try:
            osv = await client.post(
                "https://api.osv.dev/v1/query",
                json={"package": {"name": package, "ecosystem": "npm"}},
                timeout=6.0,
            )
            if osv.status_code == 200:
                vulns = osv.json().get("vulns", [])
                intel.vulnerabilities = vulns[:5]
                intel.cve_count = len(vulns)
        except Exception:
            pass

    return intel


async def check_pypi_package(package: str) -> ThreatIntel:
    intel = ThreatIntel(package=package, ecosystem="PyPI")

    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            response = await client.get(f"https://pypi.org/pypi/{package}/json")
            if response.status_code == 404:
                intel.exists = False
                return intel

            data = response.json()
            releases = data.get("releases", {})
            upload_times: list[datetime] = []
            for version_files in releases.values():
                for package_file in version_files:
                    raw_time = package_file.get("upload_time_iso_8601") or package_file.get("upload_time")
                    if not raw_time:
                        continue
                    try:
                        upload_times.append(datetime.fromisoformat(raw_time.replace("Z", "+00:00")))
                    except Exception:
                        continue

            if upload_times:
                earliest = min(upload_times)
                intel.age_days = (datetime.now(timezone.utc) - earliest.astimezone(timezone.utc)).days
                intel.suspicious_age = (intel.age_days or 0) < 30
        except Exception:
            pass

        try:
            osv = await client.post(
                "https://api.osv.dev/v1/query",
                json={"package": {"name": package, "ecosystem": "PyPI"}},
                timeout=6.0,
            )
            if osv.status_code == 200:
                vulns = osv.json().get("vulns", [])
                intel.vulnerabilities = vulns[:5]
                intel.cve_count = len(vulns)
        except Exception:
            pass

    return intel


async def _check_other_package(package: str, ecosystem: str) -> ThreatIntel:
    intel = ThreatIntel(package=package, ecosystem=ecosystem)
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(
                "https://api.osv.dev/v1/query",
                json={"package": {"name": package, "ecosystem": ecosystem}},
            )
            if response.status_code == 200:
                vulns = response.json().get("vulns", [])
                intel.vulnerabilities = vulns[:5]
                intel.cve_count = len(vulns)
    except Exception:
        pass
    return intel


async def check_packages(packages: list[tuple[str, str]]) -> list[ThreatIntel]:
    tasks = []
    for package, ecosystem in packages:
        if ecosystem == "npm":
            tasks.append(check_npm_package(package))
        elif ecosystem == "PyPI":
            tasks.append(check_pypi_package(package))
        else:
            tasks.append(_check_other_package(package, ecosystem))

    if not tasks:
        return []

    return list(await asyncio.gather(*tasks))


def _default_suggestion(command: str, category: str, packages: list[ThreatIntel]) -> str:
    if any(not package.exists for package in packages):
        missing = next(package.package for package in packages if not package.exists)
        return f"Verify the package name for '{missing}' against the official registry before installing it."
    if category == "destructive":
        return "Replace destructive operations with a dry run, a targeted path, or a git-backed rollback plan first."
    if category == "network":
        return "Download the script to a file, inspect it locally, then run only the reviewed commands you need."
    if category == "privilege":
        return "Use the least-privileged command possible and explain why elevated access is required before proceeding."
    if category == "secret":
        return "Inspect secrets through your secret manager or masked tooling instead of printing or staging them."
    if category == "execution":
        return "Move the inline code into a reviewed file and execute that file after inspection."
    if packages:
        package_list = ", ".join(package.package for package in packages[:3])
        return f"Install only verified packages after checking their registry pages: {package_list}."
    return f"Review the command manually before running it: {command[:120]}"


def _fallback_ai_result(
    command: str,
    patterns: list[tuple[str, str, str]],
    intel: list[ThreatIntel],
) -> dict:
    reasons = [description for _, description, _ in patterns[:4]]
    verdict = "SAFE"
    category = "safe"

    if any(severity == "BLOCK" for _, _, severity in patterns):
        verdict = "BLOCK"
        category = next((cat for cat, _, severity in patterns if severity == "BLOCK"), "destructive")
    elif patterns or intel:
        verdict = "WARN"
        category = patterns[0][0] if patterns else "package_install"

    for package in intel:
        if not package.exists:
            verdict = "BLOCK"
            category = "package_install"
            reasons.insert(0, f"Package '{package.package}' does not exist on {package.ecosystem}.")
        elif package.cve_count > 0:
            if verdict == "SAFE":
                verdict = "WARN"
            category = "package_install"
            reasons.append(f"Package '{package.package}' has {package.cve_count} known vulnerabilities.")

    return {
        "verdict": verdict,
        "confidence": 0.72 if verdict != "SAFE" else 0.96,
        "primary_reason": reasons[0] if reasons else "No obvious risk signals detected.",
        "all_reasons": reasons or ["No obvious risk signals detected."],
        "suggestion": _default_suggestion(command, category, intel),
        "risk_category": category,
    }


def _should_skip_ai(
    patterns: list[tuple[str, str, str]],
    intel: list[ThreatIntel],
) -> bool:
    if any(severity == "BLOCK" for _, _, severity in patterns):
        return True
    if any(not package.exists for package in intel):
        return True
    if any(package.cve_count > 20 for package in intel):
        return True
    if patterns and not intel:
        return True
    return False


async def ai_analyze_command(
    command: str,
    source: str,
    patterns: list[tuple[str, str, str]],
    intel: list[ThreatIntel],
) -> dict:
    if not grok_available() or _should_skip_ai(patterns, intel):
        return _fallback_ai_result(command, patterns, intel)

    intel_summary = []
    for package in intel:
        if not package.exists:
            intel_summary.append(
                f"{package.package} ({package.ecosystem}): does not exist, likely hallucinated or typosquatted"
            )
        elif package.cve_count > 0:
            intel_summary.append(f"{package.package}: {package.cve_count} known vulnerabilities")
        elif package.suspicious_age or package.suspicious_downloads:
            intel_summary.append(
                f"{package.package}: age={package.age_days or '?'} days, downloads={package.weekly_downloads or '?'}"
            )
        else:
            intel_summary.append(f"{package.package}: looks established")

    pattern_summary = [f"{category}: {description}" for category, description, _ in patterns] or ["none"]

    try:
        raw = await call_grok(
            COMMAND_ANALYSIS_PROMPT.format(
                command=command[:1000],
                source=source,
                patterns="; ".join(pattern_summary),
                intel="; ".join(intel_summary) if intel_summary else "no packages",
            ),
            max_tokens=500,
            json_mode=True,
            response_json_schema=COMMAND_ANALYSIS_SCHEMA,
        )
        return parse_agent_json(raw)
    except Exception:
        return _fallback_ai_result(command, patterns, intel)


def _looks_harmless(command: str, patterns: list[tuple[str, str, str]], packages: list[tuple[str, str]]) -> bool:
    if patterns or packages:
        return False
    safe_starts = (
        "ls",
        "dir",
        "pwd",
        "cd ",
        "cat ",
        "type ",
        "echo ",
        "git status",
        "git diff",
        "python --version",
        "node --version",
        "npm --version",
        "pip --version",
    )
    lowered = command.lower()
    return lowered.startswith(safe_starts) and not any(token in command for token in ("|", "&&", ";"))


async def check_command(command: str, source: str = "unknown") -> CommandRisk:
    command = command.strip()
    if not command or len(command) < 3:
        return CommandRisk(
            verdict="SAFE",
            confidence=0.99,
            reasons=[],
            suggestion="",
            category="safe",
            raw_command=command,
        )

    pattern_findings = quick_pattern_check(command)
    packages = parse_packages(command)
    intel_results = await check_packages(packages) if packages else []

    if _looks_harmless(command, pattern_findings, packages):
        return CommandRisk(
            verdict="SAFE",
            confidence=0.98,
            reasons=["No destructive, privileged, network, or package-install behavior detected."],
            suggestion="",
            category="safe",
            packages_checked=intel_results,
            raw_command=command,
        )

    ai_result = await ai_analyze_command(command, source, pattern_findings, intel_results)
    final_verdict = ai_result.get("verdict", "SAFE")
    reasons = list(ai_result.get("all_reasons", []))

    for package in intel_results:
        if not package.exists:
            final_verdict = "BLOCK"
            reasons.insert(
                0,
                f"Package '{package.package}' does not exist on {package.ecosystem} and may be typosquatting.",
            )
        elif package.cve_count > 5 and final_verdict == "SAFE":
            final_verdict = "WARN"
            reasons.append(f"'{package.package}' has {package.cve_count} known vulnerabilities in OSV.")
        elif package.suspicious_age and package.suspicious_downloads and final_verdict == "SAFE":
            final_verdict = "WARN"
            reasons.append(
                f"'{package.package}' is only {package.age_days} days old with {package.weekly_downloads} weekly downloads."
            )

    for category, description, severity in pattern_findings:
        if severity == "BLOCK":
            final_verdict = "BLOCK"
        if description not in reasons:
            reasons.append(description)

    category = ai_result.get("risk_category", "unknown")
    if category == "safe" and packages:
        category = "package_install"

    suggestion = ai_result.get("suggestion") or _default_suggestion(command, category, intel_results)

    return CommandRisk(
        verdict=final_verdict,
        confidence=float(ai_result.get("confidence", 0.8)),
        reasons=reasons[:6],
        suggestion=suggestion,
        category=category,
        packages_checked=intel_results,
        raw_command=command,
    )
