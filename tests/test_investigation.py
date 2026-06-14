import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import AsyncMock, patch
from backend.investigation import run_investigation


@pytest.mark.asyncio
async def test_investigation_runs_in_demo_mode():
    with patch("backend.investigation.send_slack", new=AsyncMock(return_value=True)):
        report = await run_investigation(
            image_path="/tmp/nonexistent_fossick_test.E01",
            case_id="test-demo-001"
        )
    assert report.status == "completed"
    assert report.case_id == "test-demo-001"
    assert isinstance(report.findings, list)
    assert isinstance(report.execution_log, list)
    print(f"Demo run: {len(report.findings)} findings, {len(report.execution_log)} tool calls")


@pytest.mark.asyncio
async def test_investigation_evidence_integrity_on_missing_image():
    with patch("backend.investigation.send_slack", new=AsyncMock(return_value=True)):
        report = await run_investigation("/tmp/missing_fossick.E01", "test-002")
    assert report.status == "completed"
    assert report.evidence_integrity_verified is True
