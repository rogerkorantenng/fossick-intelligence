from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class TimelineEvent(BaseModel):
    timestamp: datetime
    source: str
    artifact_type: Literal["fs", "evt", "lnk", "usb", "browser", "other"]
    description: str
    evidence_ref: str
    pid: Optional[int] = None
    file_path: Optional[str] = None
    file_hash: Optional[str] = None


class MemoryProcess(BaseModel):
    pid: int
    ppid: int
    name: str
    cmdline: Optional[str] = None
    create_time: Optional[datetime] = None
    network_connections: list[dict] = Field(default_factory=list)
    injected_code: bool = False
    loaded_dlls: list[str] = Field(default_factory=list)
    evidence_ref: str


class PersistenceIndicator(BaseModel):
    source: Literal["amcache", "prefetch", "registry", "scheduled_task"]
    name: str
    path: str
    timestamp: Optional[datetime] = None
    execution_count: Optional[int] = None
    file_hash: Optional[str] = None
    registry_key: Optional[str] = None
    evidence_ref: str


class TimelineResult(BaseModel):
    events: list[TimelineEvent]
    total_count: int
    earliest: Optional[datetime] = None
    latest: Optional[datetime] = None


class MemoryResult(BaseModel):
    processes: list[MemoryProcess]
    network_connections: list[dict] = Field(default_factory=list)
    injections_detected: int = 0
    raw_plugin_counts: dict = Field(default_factory=dict)


class PersistenceResult(BaseModel):
    indicators: list[PersistenceIndicator]
    total_count: int


class ToolCallResult(BaseModel):
    tool_name: str
    call_id: str
    image_sha256: str
    hash_verified: bool
    duration_ms: int = 0
    data: dict
    error: Optional[str] = None
