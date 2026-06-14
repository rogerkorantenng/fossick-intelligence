import json
import uuid
import anthropic
from datetime import datetime
from backend.models import Finding, ToolCallLog
from backend.config import settings


class MemoryAgent:
    def __init__(self, docker_client, anthropic_key: str | None = None):
        self.docker_client = docker_client
        self.client = anthropic.AsyncAnthropic(api_key=anthropic_key or settings.anthropic_api_key)

    async def run(self, image_path: str) -> tuple[list[Finding], list[ToolCallLog]]:
        raw = await self.docker_client.call_tool("analyze_memory", {
            "image_path": image_path,
            "plugins": ["windows.pslist", "windows.netscan", "windows.malfind", "windows.cmdline"],
        })

        call_id = raw.get("call_id", f"mem_{uuid.uuid4().hex[:6]}")
        data = raw.get("data", {})
        log = ToolCallLog(
            id=call_id, tool_name="analyze_memory", agent="MemoryAgent",
            called_at=datetime.utcnow(), duration_ms=raw.get("duration_ms", 0),
            params={"image_path": image_path},
            result_summary=f"{len(data.get('processes', []))} processes, {data.get('injections_detected', 0)} injections",
            image_sha256=raw.get("image_sha256", ""), hash_verified=raw.get("hash_verified", False),
        )

        if raw.get("error") or not data.get("processes"):
            return [], [log]

        prompt = f"""You are a memory forensics analyst. Analyze Volatility 3 output.
Identify malicious processes, code injection, suspicious network connections.

Processes: {json.dumps(data.get('processes', [])[:30], default=str)}
Network: {json.dumps(data.get('network_connections', [])[:20], default=str)}
Injections detected: {data.get('injections_detected', 0)}

Return JSON array only:
[{{"severity":"critical|high|medium|low","title":"...","description":"...","pid":null}}]"""

        message = await self.client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        findings = []
        try:
            text = message.content[0].text.strip()
            start, end = text.find("["), text.rfind("]") + 1
            for i, f in enumerate(json.loads(text[start:end])[:10]):
                findings.append(Finding(
                    id=f"mem_f_{i}_{uuid.uuid4().hex[:4]}",
                    severity=f.get("severity", "medium"), title=f.get("title", "Memory finding"),
                    description=f.get("description", ""), confidence="LOW",
                    sources=["memory"], tool_call_ids=[call_id],
                ))
        except Exception:
            pass

        return findings, [log]
