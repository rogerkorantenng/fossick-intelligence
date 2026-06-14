import asyncio
import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from mcp_server.models import TimelineEvent, TimelineResult, ToolCallResult
from mcp_server.tools.integrity import EvidenceContext


def _run_plaso(image_path: str, output_path: str) -> str:
    cmd = ["log2timeline.py", "--parsers", "winevtx,winreg,filestat,lnk,prefetch,usnjrnl",
           "--storage-file", output_path, image_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)


def _run_psort(storage_path: str, output_path: str) -> str:
    cmd = ["psort.py", "--output-format", "json", "--write", output_path, storage_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)


def _parse_plaso_json(json_path: str, limit: int = 50) -> list[TimelineEvent]:
    events = []
    call_id = f"tl_{uuid.uuid4().hex[:6]}"
    try:
        with open(json_path) as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                try:
                    item = json.loads(line.strip())
                    ts_str = item.get("datetime", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        continue
                    source = item.get("source_short", "unknown")
                    artifact_type = "other"
                    sl = source.lower()
                    if "evtx" in sl or "evt" in sl:
                        artifact_type = "evt"
                    elif "lnk" in sl:
                        artifact_type = "lnk"
                    elif "usb" in sl:
                        artifact_type = "usb"
                    elif "browser" in sl or "chrome" in sl or "firefox" in sl:
                        artifact_type = "browser"
                    else:
                        artifact_type = "fs"
                    events.append(TimelineEvent(
                        timestamp=ts, source=source, artifact_type=artifact_type,
                        description=item.get("message", item.get("display_name", ""))[:300],
                        evidence_ref=call_id, file_path=item.get("filename"),
                    ))
                except Exception:
                    continue
    except Exception:
        pass
    return events


async def get_timeline(
    image_path: str, earliest: str = "", latest: str = "",
    artifact_types: list[str] | None = None,
) -> ToolCallResult:
    call_id = f"tl_{uuid.uuid4().hex[:6]}"
    import tempfile, os

    if not Path(image_path).exists():
        return ToolCallResult(tool_name="get_timeline", call_id=call_id,
                              image_sha256="demo_mode", hash_verified=False,
                              data=TimelineResult(events=[], total_count=0).model_dump(),
                              error=f"Image not found: {image_path} (demo mode)")

    with EvidenceContext(image_path) as ctx:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = os.path.join(tmpdir, "timeline.plaso")
            json_path = os.path.join(tmpdir, "timeline.jsonl")
            await asyncio.to_thread(_run_plaso, image_path, storage_path)
            if Path(storage_path).exists():
                await asyncio.to_thread(_run_psort, storage_path, json_path)
            events = []
            if Path(json_path).exists():
                events = await asyncio.to_thread(_parse_plaso_json, json_path, 50)

    result = TimelineResult(events=events, total_count=len(events),
                            earliest=min(e.timestamp for e in events) if events else None,
                            latest=max(e.timestamp for e in events) if events else None)
    return ToolCallResult(tool_name="get_timeline", call_id=call_id,
                          image_sha256=ctx.hash_before, hash_verified=True,
                          duration_ms=ctx.duration_ms, data=result.model_dump())
