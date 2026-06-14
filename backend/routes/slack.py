import hashlib
import hmac
import json
import time
import urllib.parse
import aiosqlite
from fastapi import APIRouter, Request, HTTPException
from backend.slack_webhook import send_slack
from backend.config import settings
from backend.database import get_investigation, save_investigation, init_db
from backend.models import InvestigationReport, Finding

router = APIRouter()


def _verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if not settings.slack_signing_secret:
        return True
    if abs(time.time() - int(timestamp)) > 300:
        return False
    sig_base = f"v0:{timestamp}:{body.decode()}"
    expected = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(), sig_base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _update_finding_slack_status(finding_id: str, status: str) -> bool:
    """Update the slack_status of a finding in all investigations."""
    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        # Fetch all investigations and find the one with this finding
        async with db.execute("SELECT id FROM investigations") as cur:
            ids = [row[0] async for row in cur]

        for inv_id in ids:
            inv_data = await get_investigation(db, inv_id)
            if not inv_data:
                continue
            findings = inv_data.get("findings", [])
            updated = False
            for f in findings:
                if f.get("id") == finding_id:
                    f["slack_status"] = status
                    updated = True
                    break
            if updated:
                # Save back — rebuild the report object
                from datetime import datetime
                report = InvestigationReport(
                    id=inv_data["id"],
                    case_id=inv_data["case_id"],
                    image_path=inv_data["image_path"],
                    image_sha256=inv_data["image_sha256"],
                    status=inv_data["status"],
                    started_at=datetime.fromisoformat(inv_data["started_at"]),
                    completed_at=datetime.fromisoformat(inv_data["completed_at"]) if inv_data.get("completed_at") else None,
                    findings=[Finding(**f) for f in findings],
                    contradictions_detected=inv_data.get("contradictions_detected", 0),
                    contradictions_resolved=inv_data.get("contradictions_resolved", 0),
                    execution_log=[],
                    evidence_integrity_verified=bool(inv_data.get("evidence_integrity_verified")),
                    error=inv_data.get("error"),
                )
                await save_investigation(db, report)
                return True
    return False


@router.post("/slack/action")
async def slack_action(request: Request):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    signature = request.headers.get("X-Slack-Signature", "")
    if settings.slack_signing_secret and not _verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    form_data = urllib.parse.parse_qs(body.decode())
    payload = json.loads(form_data.get("payload", ["{}"])[0])
    actions = payload.get("actions", [])
    if not actions:
        return {"ok": True}

    action = actions[0]
    action_id = action.get("action_id", "")
    value = json.loads(action.get("value", "{}"))
    response_url = payload.get("response_url", "")
    finding_id = value.get("finding_id", "")
    decision = value.get("decision", "dismissed")

    if action_id in ("confirm_finding", "false_positive"):
        # Map decision to slack_status
        slack_status = "confirmed" if decision == "confirmed" else "false_positive"
        label = "✅ Confirmed by analyst" if decision == "confirmed" else "✗ Marked as false positive"

        # Update the finding in the DB
        updated = await _update_finding_slack_status(finding_id, slack_status)

        # Update the Slack card
        if response_url:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(response_url, json={
                    "replace_original": True,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"Finding `{finding_id[:8]}…`"}
                        },
                        {
                            "type": "context",
                            "elements": [{"type": "mrkdwn", "text": f"{label}  ·  {'Tracked in dashboard ✓' if updated else 'ID not found'}"}]
                        },
                    ],
                })

    return {"ok": True}
