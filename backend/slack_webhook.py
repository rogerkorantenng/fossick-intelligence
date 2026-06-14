import json
import httpx
from backend.config import settings
from backend.models import Finding

SEV_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "⚪",
}

CONF_BAR = {
    "HIGH":   "▓▓▓ HIGH",
    "MEDIUM": "▓▓░ MED",
    "LOW":    "▓░░ LOW",
}


def format_finding_card(finding: Finding, case_id: str) -> dict:
    sev_emoji   = SEV_EMOJI.get(finding.severity, "⚪")
    conf_bar    = CONF_BAR.get(finding.confidence, finding.confidence)
    sources_str = " · ".join(finding.sources) if finding.sources else "unknown"
    desc        = finding.description[:400]

    return {
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text":
                    f"{sev_emoji}  *{finding.severity.upper()} — {finding.title}*\n\n"
                    f"{desc}"},
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text":
                    f"`{conf_bar}`   Sources: _{sources_str}_   Case: `{case_id}`"}],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✓  Confirm Finding"},
                        "style": "primary",
                        "action_id": "confirm_finding",
                        "value": json.dumps({"finding_id": finding.id, "decision": "confirmed"}),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✗  False Positive"},
                        "style": "danger",
                        "action_id": "false_positive",
                        "value": json.dumps({"finding_id": finding.id, "decision": "false_positive"}),
                    },
                ],
            },
        ]
    }


def format_contradiction_card(finding: Finding, case_id: str) -> dict:
    reasoning = finding.contradiction_description or finding.description
    return {
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text":
                    f"🔒  *CONTRADICTION DETECTED*\n\n{reasoning[:500]}"},
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text":
                    f"Verifier Agent  ·  Case: `{case_id}`  ·  _re-investigating…_"}],
            },
        ]
    }


def format_completion_card(
    case_id: str, finding_count: int, contradictions: int, integrity_ok: bool
) -> dict:
    integrity_str = "✓  evidence verified" if integrity_ok else "⚠️  evidence check required"
    sev_summary   = f"{finding_count} finding(s)"
    contra_str    = f"{contradictions} contradiction(s)" if contradictions else "no contradictions"

    return {
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text":
                    f"✅  *Investigation Complete — `{case_id}`*\n\n"
                    f"{sev_summary}  ·  {contra_str}  ·  {integrity_str}"},
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text":
                    "Open the Fossick Intelligence dashboard for the full report"}],
            },
        ]
    }


async def send_slack(payload: dict) -> bool:
    if not settings.slack_webhook_url:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.slack_webhook_url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False
