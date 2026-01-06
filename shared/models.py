"""
Shared Pydantic models for inter-service communication.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class JobStatus(str, Enum):
    """Status of an analysis job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentVerdict(str, Enum):
    """Agent decision verdicts."""
    APPROVE = "approve"
    REJECT = "reject"
    WARN = "warn"
    SKIP = "skip"


class RiskLevel(str, Enum):
    """Risk level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(str, Enum):
    """Types of code changes."""
    DB = "db"
    API = "api"
    UI = "ui"
    CONFIG = "config"
    DEPENDENCY = "dependency"
    TEST = "test"
    DOCS = "docs"
    OTHER = "other"


# ============================================================================
# Event Models
# ============================================================================

class CodeAnalysisRequestedEvent(BaseModel):
    """Event published when code analysis is requested."""
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID = Field(default_factory=uuid4)
    repo_name: str
    commit_hash: str
    commit_message: str
    diff: str
    branch: str
    author: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentResultEvent(BaseModel):
    """Event published by agents with their analysis results."""
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    agent_name: str
    verdict: AgentVerdict
    confidence: float = Field(ge=0.0, le=1.0)
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReleaseDecisionEvent(BaseModel):
    """Final release decision from arbiter agent."""
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    decision: AgentVerdict
    explanation: str
    agent_results: List[AgentResultEvent]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Agent Payloads
# ============================================================================

class DiffAgentPayload(BaseModel):
    """Payload from Diff Analysis Agent."""
    files_changed: int
    lines_added: int
    lines_deleted: int
    change_types: List[ChangeType]
    risk_level: RiskLevel
    affected_modules: List[str]


class IntentAgentPayload(BaseModel):
    """Payload from Commit Intent Agent."""
    intent_match: bool
    reason: str
    commit_intent: str
    actual_changes: str
    discrepancies: List[str]


class SecurityAgentPayload(BaseModel):
    """Payload from Security Agent."""
    secrets_detected: bool
    vulnerabilities: List[Dict[str, Any]]
    security_score: float = Field(ge=0.0, le=1.0)
    issues: List[str]


class PerformanceAgentPayload(BaseModel):
    """Payload from Performance Agent."""
    performance_issues: List[Dict[str, Any]]
    n_plus_one_queries: int
    blocking_calls: int
    heavy_loops: int
    performance_score: float = Field(ge=0.0, le=1.0)


class TestAgentPayload(BaseModel):
    """Payload from Test Impact Agent."""
    tests_affected: int
    coverage_delta: float
    untested_paths: List[str]
    test_score: float = Field(ge=0.0, le=1.0)


class ArbiterPayload(BaseModel):
    """Payload from Release Arbiter Agent."""
    weighted_score: float = Field(ge=0.0, le=1.0)
    agent_weights: Dict[str, float]
    decision_matrix: Dict[str, Any]
    blocking_issues: List[str]


# ============================================================================
# API Request/Response Models
# ============================================================================

class AnalysisJobRequest(BaseModel):
    """Request to create an analysis job."""
    repo_name: str
    commit_hash: str
    commit_message: str
    diff: str
    branch: str = "main"
    author: str


class AnalysisJobResponse(BaseModel):
    """Response with job details."""
    job_id: UUID
    status: JobStatus
    created_at: datetime


class JobStatusResponse(BaseModel):
    """Response with job status and results."""
    job_id: UUID
    status: JobStatus
    decision: Optional[AgentVerdict] = None
    explanation: Optional[str] = None
    agent_results: List[AgentResultEvent] = []
    created_at: datetime
    completed_at: Optional[datetime] = None
