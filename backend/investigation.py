import asyncio
import uuid
from datetime import datetime
from pathlib import Path
import aiosqlite
from backend.config import settings
from backend.database import init_db, save_investigation
from backend.models import InvestigationReport
from backend.docker_client import get_docker_client
from backend.agents.timeline_agent import TimelineAgent
from backend.agents.memory_agent import MemoryAgent
from backend.agents.persistence_agent import PersistenceAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.slack_webhook import send_slack, format_finding_card, format_contradiction_card, format_completion_card
from mcp_server.tools.integrity import compute_sha256


async def run_investigation(image_path: str, case_id: str | None = None) -> InvestigationReport:
    investigation_id = str(uuid.uuid4())
    case_id = case_id or f"case_{investigation_id[:8]}"
    started_at = datetime.utcnow()

    image_sha256 = ""
    if Path(image_path).exists():
        image_sha256 = compute_sha256(image_path)

    report = InvestigationReport(
        id=investigation_id, case_id=case_id, image_path=image_path,
        image_sha256=image_sha256, status="running", started_at=started_at,
    )

    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        await save_investigation(db, report)

    docker_client = get_docker_client()
    print(f"[Fossick] Starting {investigation_id} on {image_path}")
    print(f"[Fossick] SHA-256: {image_sha256 or 'N/A (demo mode)'}")

    results = await asyncio.gather(
        TimelineAgent(docker_client).run(image_path),
        MemoryAgent(docker_client).run(image_path),
        PersistenceAgent(docker_client).run(image_path),
        return_exceptions=True,
    )

    def safe(r, default):
        return r if not isinstance(r, Exception) else default

    timeline_findings, timeline_logs = safe(results[0], ([], []))
    memory_findings, memory_logs = safe(results[1], ([], []))
    persistence_findings, persistence_logs = safe(results[2], ([], []))

    all_logs = list(timeline_logs) + list(memory_logs) + list(persistence_logs)
    print(f"[Fossick] Timeline:{len(timeline_findings)} Memory:{len(memory_findings)} Persistence:{len(persistence_findings)}")

    verified_findings, contradiction_findings, verifier_logs = await VerifierAgent().run(
        timeline_findings, memory_findings, persistence_findings, all_logs
    )
    all_logs.extend(verifier_logs)
    print(f"[Fossick] Contradictions: {len(contradiction_findings)}")

    all_final = verified_findings + contradiction_findings
    for finding in all_final:
        if finding.contradiction:
            await send_slack(format_contradiction_card(finding, case_id))
        elif finding.confidence == "LOW":
            finding.slack_status = "pending_review"
            await send_slack(format_finding_card(finding, case_id))
        else:
            finding.slack_status = "auto_confirmed"

    evidence_ok = True
    if image_sha256 and Path(image_path).exists():
        final_hash = compute_sha256(image_path)
        evidence_ok = (final_hash == image_sha256)
        if not evidence_ok:
            print(f"[Fossick] ⚠️  EVIDENCE INTEGRITY VIOLATION!")

    report.findings = all_final
    report.contradictions_detected = len(contradiction_findings)
    report.contradictions_resolved = len([c for c in contradiction_findings if c.confidence != "LOW"])
    report.execution_log = all_logs
    report.evidence_integrity_verified = evidence_ok
    report.status = "completed"
    report.completed_at = datetime.utcnow()

    async with aiosqlite.connect(settings.db_path) as db:
        await save_investigation(db, report)

    await send_slack(format_completion_card(case_id, len(all_final), len(contradiction_findings), evidence_ok))
    print(f"[Fossick] Complete: {len(all_final)} findings, evidence_ok={evidence_ok}")
    return report
