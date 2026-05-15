from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Domain(str, Enum):
    CIVIL_ENGINEERING = "civil_engineering"
    MECHANICAL_ENGINEERING = "mechanical_engineering"
    SOFTWARE_DEVELOPMENT = "software_development"
    FINANCIAL_MODELING = "financial_modeling"
    HEALTHCARE = "healthcare"
    INFRASTRUCTURE = "infrastructure"
    CONSTRUCTION = "construction"
    GENERAL = "general"


class AgentVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


class FinalVerdict(str, Enum):
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    BLOCKED = "BLOCKED"


class AgentResult(BaseModel):
    agent_id: int
    agent_name: str
    verdict: AgentVerdict
    confidence: float = Field(ge=0.0, le=1.0)
    issues: List[str]
    reasoning: str
    execution_time_ms: int


class VerificationRequest(BaseModel):
    content: str
    domain: Optional[Domain] = None
    context: Optional[str] = None
    source: Optional[str] = None


class VerdictResponse(BaseModel):
    request_id: str
    timestamp: datetime
    domain: Domain
    agent_results: List[AgentResult]
    final_verdict: FinalVerdict
    overall_confidence: float = Field(ge=0.0, le=1.0)
    fail_count: int
    issues_summary: List[str]
    correction: Optional[str] = None
    correction_diff: Optional[str] = None
    execution_time_ms: int


class HistoryEntry(BaseModel):
    id: int
    request_id: str
    timestamp: datetime
    domain: str
    final_verdict: str
    fail_count: int
    source: str
    content_preview: str
