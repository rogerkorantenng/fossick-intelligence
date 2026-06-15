import json
from backend.agents.base import AgentBase
import uuid
import anthropic
from datetime import datetime
from backend.models import Finding, ToolCallLog
from backend.config import settings


class PersistenceAgent(AgentBase):
    def __init__(self, docker_client, anthropic_key: str | None = None):
        self.docker_client = docker_client
        self._anthropic_key = anthropic_key

    async def run(self, image_path: str) -> tuple[list[Finding], list[ToolCallLog]]:
        raw = await self.docker_client.call_tool("get_persistence", {"image_path": image_path})

        call_id = raw.get("call_id", f"per_{uuid.uuid4().hex[:6]}")
        data = raw.get("data", {})
        log = ToolCallLog(
            id=call_id, tool_name="get_persistence", agent="PersistenceAgent",
            called_at=datetime.now(), duration_ms=raw.get("duration_ms", 0),
            params={"image_path": image_path},
            result_summary=f"{data.get('total_count', 0)} persistence indicators",
            image_sha256=raw.get("image_sha256", ""), hash_verified=raw.get("hash_verified", False),
        )

        if raw.get("error") or not data.get("indicators"):
            return [], [log]

        prompt = f"""You are a Windows persistence forensics analyst.
Analyze these persistence indicators extracted from a disk image:
- Startup folder entries (files placed in Windows Startup folders)
- Registry Run/RunOnce key values

Indicators: {json.dumps(data.get('indicators', [])[:30], default=str)}

For each indicator assess:
- Is this expected/benign (Windows defaults, well-known software)?
- Is this suspicious (unusual executable in Startup, obfuscated name, unknown path)?
- What is the likely malicious purpose if suspicious?

Focus on WINWORD.EXE in Startup (unusual), unknown DLLs, executables with typosquatting names.
Ignore desktop.ini, common browser/office shortcuts unless truly unusual.

Return JSON array only:
[{{"severity":"critical|high|medium|low","title":"...","description":"...","path":"..."}}]"""

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
                    id=f"per_f_{i}_{uuid.uuid4().hex[:4]}",
                    severity=f.get("severity", "medium"), title=f.get("title", "Persistence finding"),
                    description=f.get("description", ""), confidence="LOW",
                    sources=["persistence"], tool_call_ids=[call_id],
                ))
        except Exception:
            pass

        return findings, [log]
