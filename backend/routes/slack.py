import hashlib
import hmac
import json
import time
import urllib.parse
from fastapi import APIRouter, Request, HTTPException
from backend.slack_webhook import send_slack
from backend.config import settings

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
        label = "✅ Confirmed by analyst" if decision == "confirmed" else "✗ Marked false positive"
        if response_url:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(response_url, json={
                    "replace_original": True,
                    "blocks": [
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"Finding `{finding_id[:8]}`"}},
                        {"type": "context", "elements": [{"type": "mrkdwn", "text": label}]},
                    ],
                })
    return {"ok": True}
