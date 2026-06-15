import json
from backend.agents.base import AgentBase
import uuid
import anthropic
from datetime import datetime
from backend.models import Finding, ToolCallLog
from backend.config import settings


class TimelineAgent(AgentBase):
    def __init__(self, docker_client, anthropic_key: str | None = None):
        self.docker_client = docker_client
        self._anthropic_key = anthropic_key

    async def run(self, image_path: str) -> tuple[list[Finding], list[ToolCallLog]]:
        raw = await self.docker_client.call_tool("get_timeline", {
            "image_path": image_path,
            "artifact_types": ["fs", "evt", "lnk", "usb", "browser"],
        })

        call_id = raw.get("call_id", f"tl_{uuid.uuid4().hex[:6]}")
        retry_count = 0
        retry_reason = None

        # Self-correction: if tool errors, retry with reduced artifact scope
        if raw.get("error") and "timeout" not in str(raw.get("error", "")).lower():
            retry_reason = f"Tool error: {str(raw['error'])[:100]}. Retrying with filesystem-only scope."
            raw = await self.docker_client.call_tool("get_timeline", {
                "image_path": image_path,
                "artifact_types": ["fs"],
            })
            retry_count = 1
        elif raw.get("error") and "timeout" in str(raw.get("error", "")).lower():
            retry_reason = f"Tool timeout: {str(raw['error'])[:100]}. Retrying with filesystem-only scope."
            raw = await self.docker_client.call_tool("get_timeline", {
                "image_path": image_path,
                "artifact_types": ["fs"],
            })
            retry_count = 1

        events = raw.get("data", {}).get("events", []) if not raw.get("error") else []
        log = ToolCallLog(
            id=call_id, tool_name="get_timeline", agent="TimelineAgent",
            called_at=datetime.now(), duration_ms=raw.get("duration_ms", 0),
            params={"image_path": image_path},
            result_summary=f"{len(events)} timeline events",
            image_sha256=raw.get("image_sha256", ""),
            hash_verified=raw.get("hash_verified", False),
            retry_count=retry_count,
            retry_reason=retry_reason,
        )

        if raw.get("error") or not events:
            return [], [log]

        prompt = f"""You are a DFIR analyst. Analyze these {len(events)} timeline events.
Identify suspicious activity. Return JSON array only.

Events: {json.dumps(events[:50], default=str)}

[{{"severity":"critical|high|medium|low","title":"...","description":"...","timestamp":"ISO8601 or null","file_path":"path or null"}}]"""

        message = await self._get_client().messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        log.tokens_used = message.usage.input_tokens + message.usage.output_tokens

        findings = []
        try:
            text = message.content[0].text.strip()
            start, end = text.find("["), text.rfind("]") + 1
            for i, f in enumerate(json.loads(text[start:end])[:10]):
                findings.append(Finding(
                    id=f"tl_f_{i}_{uuid.uuid4().hex[:4]}",
                    severity=f.get("severity", "medium"), title=f.get("title", "Timeline event"),
                    description=f.get("description", ""), confidence="LOW",
                    sources=["timeline"], tool_call_ids=[call_id],
                    timestamp=datetime.fromisoformat(f["timestamp"]) if f.get("timestamp") else None,
                ))
        except Exception:
            pass

        return findings, [log]
