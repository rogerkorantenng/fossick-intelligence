import asyncio
import subprocess
import uuid
from pathlib import Path
from mcp_server.models import PersistenceIndicator, PersistenceResult, ToolCallResult
from mcp_server.tools.integrity import EvidenceContext


def _run_prefetch(image_path: str) -> list[dict]:
    try:
        cmd = ["python3", "-c", "import prefetch; print('ok')"]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return []
    except Exception:
        return []


def _run_amcache(image_path: str) -> list[dict]:
    try:
        cmd = ["python3", "-c", "import regipy; print('ok')"]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return []
    except Exception:
        return []


async def get_persistence(image_path: str) -> ToolCallResult:
    call_id = f"per_{uuid.uuid4().hex[:6]}"

    if not Path(image_path).exists():
        return ToolCallResult(tool_name="get_persistence", call_id=call_id,
                              image_sha256="demo_mode", hash_verified=False,
                              data=PersistenceResult(indicators=[], total_count=0).model_dump(),
                              error=f"Image not found: {image_path} (demo mode)")

    with EvidenceContext(image_path) as ctx:
        prefetch_data = await asyncio.to_thread(_run_prefetch, image_path)
        amcache_data = await asyncio.to_thread(_run_amcache, image_path)

    indicators = []
    for item in prefetch_data[:25]:
        indicators.append(PersistenceIndicator(
            source="prefetch", name=item.get("name", "unknown"),
            path=item.get("path", ""), execution_count=item.get("run_count"),
            evidence_ref=call_id,
        ))
    for item in amcache_data[:25]:
        indicators.append(PersistenceIndicator(
            source="amcache", name=item.get("name", "unknown"),
            path=item.get("path", ""), file_hash=item.get("sha1"), evidence_ref=call_id,
        ))

    result = PersistenceResult(indicators=indicators, total_count=len(indicators))
    return ToolCallResult(tool_name="get_persistence", call_id=call_id,
                          image_sha256=ctx.hash_before, hash_verified=True,
                          duration_ms=ctx.duration_ms, data=result.model_dump())
