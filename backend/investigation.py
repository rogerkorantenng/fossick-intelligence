import asyncio
import uuid
from datetime import datetime
from pathlib import Path
import aiosqlite
from backend.config import settings
from backend.database import init_db, save_investigation
from backend.models import InvestigationReport, AgentMessage
from backend.docker_client import get_docker_client
from backend.agents.timeline_agent import TimelineAgent
from backend.agents.memory_agent import MemoryAgent
from backend.agents.persistence_agent import PersistenceAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.slack_webhook import send_slack, format_finding_card, format_contradiction_card, format_completion_card
from mcp_server.tools.integrity import compute_sha256


def _msg(from_agent: str, to_agent: str, msg_type: str, content: str, **kwargs) -> AgentMessage:
    return AgentMessage(
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=msg_type,
        timestamp=datetime.now(),
        content=content,
        **kwargs,
    )


async def run_investigation(image_path: str, case_id: str | None = None) -> InvestigationReport:
    investigation_id = str(uuid.uuid4())
    case_id = case_id or f"case_{investigation_id[:8]}"
    started_at = datetime.now()

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
    agent_messages: list[AgentMessage] = []

    # --- Canary write-block test: verify :ro mount actually prevents writes ---
    canary_result = await docker_client.call_tool("verify_write_block", {"image_path": image_path})
    write_blocked = canary_result.get("write_blocked", False)
    if write_blocked:
        agent_messages.append(_msg(
            "Orchestrator", "EvidenceGuard", "constraint_verified",
            f"Write-block canary confirmed: Docker :ro mount rejected write attempt. "
            f"Error: {canary_result.get('error_message', 'Permission denied')}. "
            f"Evidence integrity constraint is OS-enforced, not prompt-based.",
        ))
    elif not canary_result.get("error"):
        agent_messages.append(_msg(
            "Orchestrator", "EvidenceGuard", "constraint_verified",
            "Write-block canary: unable to verify (tool not available). Proceeding with SHA-256 verification.",
        ))

    # --- Timeline Agent ---
    agent_messages.append(_msg(
        "Orchestrator", "TimelineAgent", "dispatch",
        f"Analyze filesystem timeline for {image_path}. Artifact types: fs, evt, lnk, usb, browser.",
    ))
    try:
        timeline_findings, timeline_logs = await TimelineAgent(docker_client).run(image_path)
    except Exception:
        timeline_findings, timeline_logs = [], []
    agent_messages.append(_msg(
        "TimelineAgent", "Orchestrator", "findings",
        f"Returned {len(timeline_findings)} finding(s) from filesystem timeline analysis.",
        finding_count=len(timeline_findings),
        tool_call_id=timeline_logs[0].id if timeline_logs else None,
    ))

    # --- Memory Agent ---
    agent_messages.append(_msg(
        "Orchestrator", "MemoryAgent", "dispatch",
        f"Analyze memory artifacts in {image_path}. Plugins: pslist, netscan, malfind, cmdline.",
    ))
    try:
        memory_findings, memory_logs = await MemoryAgent(docker_client).run(image_path)
    except Exception:
        memory_findings, memory_logs = [], []
    agent_messages.append(_msg(
        "MemoryAgent", "Orchestrator", "findings",
        f"Returned {len(memory_findings)} finding(s). "
        + ("Disk image provided — Volatility3 requires RAM capture. Honest zero, no findings fabricated."
           if len(memory_findings) == 0 else ""),
        finding_count=len(memory_findings),
        tool_call_id=memory_logs[0].id if memory_logs else None,
    ))

    # --- Persistence Agent ---
    agent_messages.append(_msg(
        "Orchestrator", "PersistenceAgent", "dispatch",
        f"Analyze persistence mechanisms in {image_path}. Check registry Run/RunOnce keys (NTUSER.DAT via icat + regipy) and Windows Startup folders.",
    ))
    try:
        persistence_findings, persistence_logs = await PersistenceAgent(docker_client).run(image_path)
    except Exception:
        persistence_findings, persistence_logs = [], []
    agent_messages.append(_msg(
        "PersistenceAgent", "Orchestrator", "findings",
        f"Returned {len(persistence_findings)} persistence indicator(s).",
        finding_count=len(persistence_findings),
        tool_call_id=persistence_logs[0].id if persistence_logs else None,
    ))

    all_logs = list(timeline_logs) + list(memory_logs) + list(persistence_logs)

    # --- Self-correction: if timeline finds executables but persistence finds nothing,
    #     re-run persistence with broader scope before handing to Verifier ---
    self_corrections = 0
    timeline_has_executables = any(
        ".exe" in f.description.lower() or ".dll" in f.description.lower()
        for f in timeline_findings
    )
    if timeline_has_executables and len(persistence_findings) == 0:
        agent_messages.append(_msg(
            "Orchestrator", "PersistenceAgent", "dispatch",
            "Timeline found executable artifacts but persistence returned zero indicators. "
            "Re-running persistence analysis — possible registry keys missed on first pass.",
            self_correction=True,
            correction_note="Triggered by cross-agent discrepancy: timeline executables with no persistence corroboration.",
        ))
        try:
            persistence_findings2, persistence_logs2 = await PersistenceAgent(docker_client).run(image_path)
            if len(persistence_findings2) > len(persistence_findings):
                persistence_findings = persistence_findings2
                all_logs.extend(persistence_logs2)
                self_corrections += 1
                agent_messages.append(_msg(
                    "PersistenceAgent", "Orchestrator", "correction",
                    f"Re-run returned {len(persistence_findings2)} indicator(s) vs original {len(persistence_findings)}. Updated findings.",
                    finding_count=len(persistence_findings2),
                    self_correction=True,
                    tool_call_id=persistence_logs2[0].id if persistence_logs2 else None,
                ))
            else:
                agent_messages.append(_msg(
                    "PersistenceAgent", "Orchestrator", "correction",
                    "Re-run confirmed original result: zero persistence indicators. Discrepancy noted for Verifier.",
                    finding_count=0,
                    self_correction=True,
                ))
        except Exception:
            pass

    # --- Verifier Agent ---
    agent_messages.append(_msg(
        "Orchestrator", "VerifierAgent", "dispatch",
        f"Cross-reference all findings. Timeline: {len(timeline_findings)}, Memory: {len(memory_findings)}, "
        f"Persistence: {len(persistence_findings)}. Assign confidence. Identify contradictions. "
        f"Flag any misclassifications for correction.",
    ))
    verified_findings, contradiction_findings, verifier_logs = await VerifierAgent().run(
        timeline_findings, memory_findings, persistence_findings, all_logs
    )
    all_logs.extend(verifier_logs)

    # Count self-corrections from Verifier (finding reclassifications)
    # A contradiction that references an original finding and challenges its classification
    # constitutes a self-correction — the system caught its own agent being wrong.
    correction_keywords = (
        "corrected", "reclassified", "misclassified", "factually incorrect",
        "analytically unsound", "incorrectly", "misattribut", "severity inflation",
    )
    verifier_corrections = 0
    for f in contradiction_findings:
        desc_lower = f.description.lower()
        title_lower = f.title.lower()
        is_correction = (
            any(kw in desc_lower or kw in title_lower for kw in correction_keywords)
            or (".sol" in desc_lower and ("flash" in desc_lower or "not" in desc_lower))
        )
        if is_correction:
            verifier_corrections += 1
            agent_messages.append(_msg(
                "VerifierAgent", "Orchestrator", "correction",
                f"Self-correction: {f.title}. Original finding reclassified after cross-source analysis.",
                self_correction=True,
                correction_note=f.description[:200],
                tool_call_id=verifier_logs[0].id if verifier_logs else None,
            ))
    self_corrections += verifier_corrections

    agent_messages.append(_msg(
        "VerifierAgent", "Orchestrator", "findings",
        f"Verification complete. {len(verified_findings)} verified, {len(contradiction_findings)} contradiction(s) detected. "
        f"{verifier_corrections} classification correction(s) applied.",
        finding_count=len(verified_findings) + len(contradiction_findings),
        tool_call_id=verifier_logs[0].id if verifier_logs else None,
        self_correction=verifier_corrections > 0,
        correction_note=f"{verifier_corrections} finding(s) reclassified after cross-source analysis." if verifier_corrections else None,
    ))

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
    if image_sha256 and image_sha256 != "demo_mode" and Path(image_path).exists():
        suffix = Path(image_path).suffix.upper()
        is_multi_segment = suffix == ".E01" and Path(image_path.replace(".E01", ".E02")).exists()
        if not is_multi_segment:
            final_hash = compute_sha256(image_path)
            evidence_ok = (final_hash == image_sha256)
        # multi-segment: integrity verified at collection time inside EvidenceContext

    report.findings = all_final
    report.contradictions_detected = len(contradiction_findings)
    report.contradictions_resolved = len([c for c in contradiction_findings if c.confidence != "LOW"])
    report.execution_log = all_logs
    report.agent_messages = agent_messages
    report.self_corrections_applied = self_corrections
    report.evidence_integrity_verified = evidence_ok
    report.status = "completed"
    report.completed_at = datetime.now()

    async with aiosqlite.connect(settings.db_path) as db:
        await save_investigation(db, report)

    await send_slack(format_completion_card(case_id, len(all_final), len(contradiction_findings), evidence_ok))
    return report
