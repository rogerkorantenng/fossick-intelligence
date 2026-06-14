import json
from backend.agents.base import AgentBase
import uuid
import anthropic
from backend.models import Finding, ToolCallLog
from backend.config import settings
from datetime import datetime


def detect_contradictions(
    memory_findings: list[Finding],
    persistence_findings: list[Finding],
    timeline_findings: list[Finding],
) -> list[dict]:
    contradictions = []
    memory_processes = [f for f in memory_findings if "process" in f.title.lower() or "inject" in f.description.lower()]
    for mf in memory_processes:
        covered = any(mf.title.lower().split()[-1] in pf.description.lower() for pf in persistence_findings)
        if not covered and len(persistence_findings) > 0:
            contradictions.append({
                "type": "missing_execution_artifact",
                "description": f"Memory finding '{mf.title}' has no corresponding execution artifact in AmCache/Prefetch — possible fileless malware",
                "memory_finding_id": mf.id,
                "severity": "high",
            })
    return contradictions


class VerifierAgent(AgentBase):
    def __init__(self, anthropic_key: str | None = None):
        self._anthropic_key = anthropic_key

    async def run(
        self,
        timeline_findings: list[Finding],
        memory_findings: list[Finding],
        persistence_findings: list[Finding],
        all_logs: list[ToolCallLog],
    ) -> tuple[list[Finding], list[Finding], list[ToolCallLog]]:
        call_id = f"ver_{uuid.uuid4().hex[:6]}"
        contradictions = detect_contradictions(memory_findings, persistence_findings, timeline_findings)
        all_findings = timeline_findings + memory_findings + persistence_findings

        if not all_findings:
            return [], [], []

        synthesis_prompt = f"""You are a senior DFIR analyst verifying findings from three independent forensic agents.

Timeline Agent findings ({len(timeline_findings)}):
{json.dumps([f.model_dump() for f in timeline_findings[:5]], default=str)}

Memory Agent findings ({len(memory_findings)}):
{json.dumps([f.model_dump() for f in memory_findings[:5]], default=str)}

Persistence Agent findings ({len(persistence_findings)}):
{json.dumps([f.model_dump() for f in persistence_findings[:5]], default=str)}

Rule-based contradictions detected: {json.dumps(contradictions, default=str)}

Cross-reference findings. Assign confidence: HIGH (3 sources corroborate), MEDIUM (2), LOW (1).
Identify any additional contradictions.

Return JSON:
{{"verified_findings":[{{"id":"original_id","confidence":"HIGH|MEDIUM|LOW","corroborating_sources":["timeline","memory","persistence"]}}],"new_contradictions":[{{"title":"...","description":"...","severity":"high|medium"}}]}}"""

        message = await self._get_client().messages.create(
            model="claude-sonnet-4-6", max_tokens=2048,
            messages=[{"role": "user", "content": synthesis_prompt}],
        )

        log = ToolCallLog(
            id=call_id, tool_name="verifier_synthesis", agent="VerifierAgent",
            called_at=datetime.now(),
            params={"finding_count": len(all_findings)},
            result_summary=f"Verified {len(all_findings)} findings, {len(contradictions)} contradictions",
        )

        verified = list(all_findings)
        contradiction_findings = []

        try:
            text = message.content[0].text.strip()
            start, end = text.find("{"), text.rfind("}") + 1
            data = json.loads(text[start:end])
            id_map = {f.id: f for f in all_findings}
            for vf in data.get("verified_findings", []):
                finding = id_map.get(vf.get("id"))
                if finding:
                    finding.confidence = vf.get("confidence", finding.confidence)
                    finding.sources = vf.get("corroborating_sources", finding.sources)
            for c in data.get("new_contradictions", []):
                contradiction_findings.append(Finding(
                    id=f"con_{uuid.uuid4().hex[:6]}",
                    severity=c.get("severity", "medium"),
                    title=f"CONTRADICTION: {c.get('title', 'Cross-source inconsistency')}",
                    description=c.get("description", ""),
                    confidence="LOW", sources=["verifier"], tool_call_ids=[call_id],
                    contradiction=True, contradiction_description=c.get("description"),
                ))
        except Exception:
            pass

        return verified, contradiction_findings, [log]
