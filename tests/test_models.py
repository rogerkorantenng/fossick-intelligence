import pytest
from mcp_server.models import TimelineEvent, ToolCallResult
from mcp_server.tools.integrity import compute_sha256, EvidenceSpoliationError, assert_no_spoliation
from datetime import datetime
import tempfile, os


def test_timeline_event_required_fields():
    event = TimelineEvent(
        timestamp=datetime(2024, 1, 15, 14, 32, 0),
        source="WinEvtx",
        artifact_type="evt",
        description="Process created: cmd.exe",
        evidence_ref="tc_001"
    )
    assert event.artifact_type == "evt"


def test_tool_call_result_has_hash():
    result = ToolCallResult(
        tool_name="get_timeline",
        call_id="tc_001",
        image_sha256="abc123",
        hash_verified=True,
        data={"events": []}
    )
    assert result.hash_verified is True


def test_compute_sha256_on_file():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"test forensic image data")
        path = f.name
    try:
        h = compute_sha256(path)
        assert len(h) == 64
        assert h == compute_sha256(path)
    finally:
        os.unlink(path)


def test_spoliation_detection():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"original content")
        path = f.name
    try:
        original_hash = compute_sha256(path)
        with open(path, "wb") as f:
            f.write(b"modified content")
        with pytest.raises(EvidenceSpoliationError):
            assert_no_spoliation(path, original_hash)
    finally:
        os.unlink(path)
