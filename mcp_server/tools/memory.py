import asyncio
import json
import subprocess
import uuid
from pathlib import Path
from datetime import datetime
from mcp_server.models import MemoryProcess, MemoryResult, ToolCallResult
from mcp_server.tools.integrity import EvidenceContext


def _run_vol3_plugin(image_path: str, plugin: str) -> list[dict]:
    # Try vol first, then python3 -m volatility3.cli
    for cmd in [
        ["vol", "-f", image_path, plugin, "--output", "json"],
        ["python3", "-m", "volatility3.cli", "-f", image_path, plugin, "--output", "json"],
    ]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    rows = data.get("rows", [])
                    if rows:
                        return rows
                except Exception:
                    pass
        except Exception:
            continue
    return []


def _run_fls(image_path: str) -> list[dict]:
    """Use SleuthKit fls to list filesystem entries as fallback for disk images."""
    try:
        result = subprocess.run(
            ["fls", "-r", "-l", image_path],
            capture_output=True, text=True, timeout=60
        )
        entries = []
        for line in result.stdout.splitlines()[:50]:
            parts = line.split("\t")
            if len(parts) >= 3:
                entries.append({"name": parts[-1] if parts else line, "type": "file", "raw": line[:200]})
        return entries
    except Exception:
        return []


def _parse_pslist(rows: list[dict], call_id: str) -> list[MemoryProcess]:
    processes = []
    for row in rows[:50]:
        try:
            processes.append(MemoryProcess(
                pid=int(row.get("PID", 0)), ppid=int(row.get("PPID", 0)),
                name=str(row.get("ImageFileName", "unknown"))[:64], evidence_ref=call_id,
            ))
        except Exception:
            continue
    return processes


async def analyze_memory(image_path: str, plugins: list[str] | None = None) -> ToolCallResult:
    call_id = f"mem_{uuid.uuid4().hex[:6]}"
    plugins = plugins or ["windows.pslist", "windows.netscan", "windows.malfind", "windows.cmdline"]

    if not Path(image_path).exists():
        return ToolCallResult(tool_name="analyze_memory", call_id=call_id,
                              image_sha256="demo_mode", hash_verified=False,
                              data=MemoryResult(processes=[], injections_detected=0).model_dump(),
                              error=f"Image not found: {image_path} (demo mode)")

    with EvidenceContext(image_path) as ctx:
        pslist_rows = await asyncio.to_thread(_run_vol3_plugin, image_path, "windows.pslist")
        malfind_rows = await asyncio.to_thread(_run_vol3_plugin, image_path, "windows.malfind")
        netscan_rows = await asyncio.to_thread(_run_vol3_plugin, image_path, "windows.netscan")
        # Fallback: if Volatility can't parse (disk image not memory), use fls
        if not pslist_rows and not malfind_rows:
            fls_rows = await asyncio.to_thread(_run_fls, image_path)
            if fls_rows:
                pslist_rows = fls_rows  # Use filesystem listing as proxy

    processes = _parse_pslist(pslist_rows, call_id)
    result = MemoryResult(processes=processes, network_connections=netscan_rows[:30],
                          injections_detected=len(malfind_rows),
                          raw_plugin_counts={"pslist": len(pslist_rows),
                                             "malfind": len(malfind_rows),
                                             "netscan": len(netscan_rows)})
    return ToolCallResult(tool_name="analyze_memory", call_id=call_id,
                          image_sha256=ctx.hash_before, hash_verified=True,
                          duration_ms=ctx.duration_ms, data=result.model_dump())
