from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW"]
FindingSeverity = Literal["critical", "high", "medium", "low"]
SlackStatus = Literal["auto_confirmed", "pending_review", "confirmed", "false_positive"]
InvestigationStatus = Literal["running", "completed", "failed"]


class Finding(BaseModel):
    id: str
    severity: FindingSeverity
    title: str
    description: str
    confidence: ConfidenceLevel
    sources: list[str] = Field(default_factory=list)
    tool_call_ids: list[str] = Field(default_factory=list)
    timestamp: Optional[datetime] = None
    contradiction: bool = False
    contradiction_description: Optional[str] = None
    slack_status: Optional[SlackStatus] = None


class ToolCallLog(BaseModel):
    id: str
    tool_name: str
    agent: str
    called_at: datetime
    duration_ms: int = 0
    params: dict = Field(default_factory=dict)
    result_summary: str = ""
    image_sha256: str = ""
    hash_verified: bool = False
    spoliation_detected: bool = False
    tokens_used: int = 0
    retry_count: int = 0
    retry_reason: Optional[str] = None


class AgentMessage(BaseModel):
    from_agent: str
    to_agent: str
    message_type: Literal["dispatch", "findings", "correction", "contradiction", "constraint_verified"]
    timestamp: datetime
    content: str
    finding_count: int = 0
    tool_call_id: Optional[str] = None
    self_correction: bool = False
    correction_note: Optional[str] = None


class InvestigationReport(BaseModel):
    id: str
    case_id: str
    image_path: str
    image_sha256: str
    status: InvestigationStatus = "running"
    started_at: datetime
    completed_at: Optional[datetime] = None
    findings: list[Finding] = Field(default_factory=list)
    contradictions_detected: int = 0
    contradictions_resolved: int = 0
    execution_log: list[ToolCallLog] = Field(default_factory=list)
    agent_messages: list[AgentMessage] = Field(default_factory=list)
    self_corrections_applied: int = 0
    evidence_integrity_verified: bool = False
    error: Optional[str] = None
