import json
import httpx
from backend.config import settings
from backend.models import Finding

CONFIDENCE_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "⚠️"}


def format_finding_card(finding: Finding, case_id: str) -> dict:
    emoji = CONFIDENCE_EMOJI.get(finding.confidence, "⚪")
    sources_str = " + ".join(finding.sources) if finding.sources else "unknown"
    return {
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text":
                f"{emoji} *{finding.severity.upper()} — {finding.title}*\n"
                f"{finding.description[:300]}\n"
                f"Confidence: {finding.confidence} | Sources: {sources_str} | Case: `{case_id}`"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "✓ Confirm Finding"},
                 "style": "primary", "action_id": "confirm_finding",
                 "value": json.dumps({"finding_id": finding.id, "decision": "confirmed"})},
                {"type": "button", "text": {"type": "plain_text", "text": "✗ False Positive"},
                 "style": "danger", "action_id": "false_positive",
                 "value": json.dumps({"finding_id": finding.id, "decision": "false_positive"})},
            ]},
        ]
    }


def format_contradiction_card(finding: Finding, case_id: str) -> dict:
    return {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text":
        f"🔒 *CONTRADICTION — Re-investigating*\n{finding.contradiction_description or finding.description}\nCase: `{case_id}`"}}]}


def format_completion_card(case_id: str, finding_count: int, contradictions: int, integrity_ok: bool) -> dict:
    return {"text":
        f"✅ *Fossick Complete — {case_id}*\n"
        f"{finding_count} findings · {contradictions} contradictions · "
        f"Evidence: {'✓ verified' if integrity_ok else '⚠️ CHECK REQUIRED'}"}


async def send_slack(payload: dict) -> bool:
    if not settings.slack_webhook_url:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.slack_webhook_url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False
