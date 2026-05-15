import asyncio
from pathlib import Path

from server.agents.fact_verifier import run_fact_verifier
from server.agents.logic_auditor import run_logic_auditor
from server.agents.math_validator import run_math_validator
from server.agents.standards_checker import run_standards_checker
from server.domain_detector import detect_domain


def _load_demo(name: str) -> str:
    return (Path(__file__).parent / "demo_scenarios" / name).read_text(encoding="utf-8")


def test_domain_detection_healthcare():
    content = _load_demo("healthcare.py")
    domain = asyncio.run(detect_domain(content))
    assert domain.value == "healthcare"


def test_fact_verifier_catches_software_demo():
    content = _load_demo("software_dev.py")
    result = asyncio.run(run_fact_verifier(content, "software_development"))
    assert result.verdict.value in {"FAIL", "UNCERTAIN"}


def test_math_validator_catches_financial_formula():
    content = _load_demo("financial_modeling.py")
    result = asyncio.run(run_math_validator(content, "financial_modeling"))
    assert result.verdict.value in {"FAIL", "UNCERTAIN"}


def test_logic_auditor_runs():
    content = _load_demo("civil_engineering.py")
    result = asyncio.run(run_logic_auditor(content, "civil_engineering"))
    assert result.verdict.value in {"PASS", "FAIL", "UNCERTAIN"}


def test_standards_checker_runs():
    content = _load_demo("healthcare.py")
    result = asyncio.run(run_standards_checker(content, "healthcare"))
    assert result.verdict.value in {"PASS", "FAIL", "UNCERTAIN"}
