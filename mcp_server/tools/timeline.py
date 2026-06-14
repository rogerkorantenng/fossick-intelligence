import asyncio
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from mcp_server.models import TimelineEvent, TimelineResult, ToolCallResult
from mcp_server.tools.integrity import EvidenceContext


def _run_mmls(image_path: str) -> list[dict]:
    """List partition layout using SleuthKit mmls."""
    try:
        result = subprocess.run(
            ["mmls", image_path],
            capture_output=True, text=True, timeout=30
        )
        partitions = []
        for line in result.stdout.splitlines():
            if line.strip() and not line.startswith("DOS"):
                parts = line.split()
                if len(parts) >= 5:
                    partitions.append({
                        "slot": parts[0], "start": parts[2],
                        "end": parts[3], "length": parts[4],
                        "description": " ".join(parts[5:]) if len(parts) > 5 else ""
                    })
        return partitions
    except Exception:
        return []


def _run_fls(image_path: str, offset: str = "") -> list[dict]:
    """List filesystem entries using SleuthKit fls."""
    try:
        cmd = ["fls", "-r", "-l"]
        if offset:
            cmd += ["-o", offset]
        cmd.append(image_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        entries = []
        for line in result.stdout.splitlines()[:200]:
            parts = line.split("\t")
            if len(parts) >= 7:
                # fls output: type|inode \t ... \t mtime \t ... \t name
                entry = {
                    "type": parts[0].strip() if parts else "",
                    "name": parts[-1].strip() if parts else line[:100],
                    "mtime": parts[3].strip() if len(parts) > 3 else "",
                    "size": parts[6].strip() if len(parts) > 6 else "0",
                }
                entries.append(entry)
        return entries
    except Exception:
        return []


def _run_mactime(image_path: str, offset: str = "") -> list[dict]:
    """Generate MAC timeline using SleuthKit fls + mactime."""
    try:
        cmd_fls = ["fls", "-r", "-m", "/"]
        if offset:
            cmd_fls += ["-o", offset]
        cmd_fls.append(image_path)

        fls_result = subprocess.run(cmd_fls, capture_output=True, text=True, timeout=120)
        if not fls_result.stdout:
            return []

        mactime_result = subprocess.run(
            ["mactime", "-b", "-"],
            input=fls_result.stdout,
            capture_output=True, text=True, timeout=60
        )

        events = []
        for line in mactime_result.stdout.splitlines()[:100]:
            parts = line.split("|")
            if len(parts) >= 9:
                ts_str = parts[0].strip()
                try:
                    ts = datetime.strptime(ts_str, "%a %b %d %H:%M:%S %Y")
                    events.append({
                        "timestamp": ts.isoformat(),
                        "size": parts[1].strip(),
                        "activity": parts[2].strip(),
                        "mode": parts[3].strip(),
                        "uid": parts[4].strip(),
                        "gid": parts[5].strip(),
                        "meta": parts[6].strip(),
                        "name": parts[8].strip() if len(parts) > 8 else "",
                    })
                except Exception:
                    continue
        return events
    except Exception:
        return []


def _parse_fls_to_timeline(entries: list[dict], call_id: str) -> list[TimelineEvent]:
    events = []
    suspicious_extensions = {'.exe', '.dll', '.bat', '.ps1', '.vbs', '.cmd', '.scr'}
    suspicious_paths = ['temp', 'tmp', 'appdata\\local', 'appdata\\roaming', 'users\\public']

    for entry in entries[:50]:
        name = entry.get("name", "")
        mtime = entry.get("mtime", "")
        if not name:
            continue

        # Classify artifact type
        ext = Path(name).suffix.lower()
        artifact_type = "fs"
        if ext in ('.lnk',):
            artifact_type = "lnk"
        elif "usb" in name.lower() or "removable" in name.lower():
            artifact_type = "usb"

        # Parse timestamp
        ts = datetime.now()
        if mtime:
            try:
                ts = datetime.fromtimestamp(int(mtime))
            except Exception:
                pass

        # Flag suspicious
        is_suspicious = (
            ext in suspicious_extensions or
            any(sp in name.lower() for sp in suspicious_paths)
        )

        if is_suspicious or artifact_type != "fs":
            events.append(TimelineEvent(
                timestamp=ts,
                source="SleuthKit/fls",
                artifact_type=artifact_type,
                description=f"{'[SUSPICIOUS] ' if is_suspicious else ''}{entry.get('type', '')} {name}",
                evidence_ref=call_id,
                file_path=name,
            ))

    return events


def _run_ewfinfo(image_path: str) -> dict:
    """Get EWF image metadata."""
    try:
        result = subprocess.run(["ewfinfo", image_path], capture_output=True, text=True, timeout=30)
        info = {}
        for line in result.stdout.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                info[k.strip()] = v.strip()
        return info
    except Exception:
        return {}


def _mount_ewf_and_analyze(image_path: str, call_id: str) -> list[TimelineEvent]:
    """Mount EWF image and run fls analysis."""
    import tempfile
    import os
    events = []
    mount_point = tempfile.mkdtemp(prefix="fossick_ewf_")
    try:
        # Mount EWF
        mount_result = subprocess.run(
            ["ewfmount", image_path, mount_point],
            capture_output=True, text=True, timeout=30
        )
        if mount_result.returncode != 0:
            return events

        ewf_raw = os.path.join(mount_point, "ewf1")
        if not os.path.exists(ewf_raw):
            return events

        # Get partition layout
        mmls_result = subprocess.run(
            ["mmls", ewf_raw], capture_output=True, text=True, timeout=15
        )
        offset = ""
        for line in mmls_result.stdout.splitlines():
            if "NTFS" in line or "0x07" in line or "07" in line.split():
                parts = line.split()
                if len(parts) >= 3:
                    offset = parts[2]
                    break

        # Run fls on mounted raw image
        fls_cmd = ["fls", "-r", "-f", "ntfs"]
        if offset:
            fls_cmd += ["-o", offset]
        fls_cmd.append(ewf_raw)

        fls_result = subprocess.run(fls_cmd, capture_output=True, text=True, timeout=120)

        suspicious_ext = {'.exe', '.dll', '.bat', '.ps1', '.vbs', '.cmd', '.scr', '.tmp'}
        suspicious_paths = ['temp', 'tmp', 'appdata', 'users\\public', 'windows\\system32\\tasks']

        for line in fls_result.stdout.splitlines()[:300]:
            parts = line.split("\t")
            name = parts[-1].strip() if parts else ""
            if not name:
                continue
            ext = Path(name.split("/")[-1]).suffix.lower()
            is_sus = ext in suspicious_ext or any(sp in name.lower() for sp in suspicious_paths)
            if is_sus:
                events.append(TimelineEvent(
                    timestamp=datetime.now(),
                    source="SleuthKit/fls",
                    artifact_type="lnk" if ext == ".lnk" else "fs",
                    description=f"[SUSPICIOUS] {name}",
                    evidence_ref=call_id,
                    file_path=name,
                ))

    except Exception as e:
        events.append(TimelineEvent(
            timestamp=datetime.now(), source="error", artifact_type="other",
            description=f"EWF mount/analysis error: {e}", evidence_ref=call_id,
        ))
    finally:
        subprocess.run(["umount", mount_point], capture_output=True)
        subprocess.run(["rmdir", mount_point], capture_output=True)

    return events


def _find_ntfs_offset(image_path: str) -> str:
    """Find NTFS partition offset for fls."""
    try:
        result = subprocess.run(["mmls", image_path], capture_output=True, text=True, timeout=15)
        for line in result.stdout.splitlines():
            if "NTFS" in line or "Basic data" in line or "07" in line:
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2]
    except Exception:
        pass
    return ""


async def get_timeline(
    image_path: str,
    earliest: str = "",
    latest: str = "",
    artifact_types: list[str] | None = None,
) -> ToolCallResult:
    call_id = f"tl_{uuid.uuid4().hex[:6]}"

    if not Path(image_path).exists():
        return ToolCallResult(
            tool_name="get_timeline", call_id=call_id,
            image_sha256="demo_mode", hash_verified=False,
            data=TimelineResult(events=[], total_count=0).model_dump(),
            error=f"Image not found: {image_path} (demo mode)"
        )

    with EvidenceContext(image_path) as ctx:
        # Get partition layout via mmls (works on E01 first segment for metadata)
        partitions = await asyncio.to_thread(_run_mmls, image_path)

        # Try EWF mount approach for multi-segment images
        events = await asyncio.to_thread(_mount_ewf_and_analyze, image_path, call_id)

        # Fallback: direct fls on E01 (partial — only first segment)
        if not events:
            offset = await asyncio.to_thread(_find_ntfs_offset, image_path)
            fls_entries = await asyncio.to_thread(_run_fls, image_path, offset)
            events = _parse_fls_to_timeline(fls_entries, call_id)

    # Add partition info as context event
    if partitions:
        events.insert(0, TimelineEvent(
            timestamp=datetime.now(),
            source="SleuthKit/mmls",
            artifact_type="fs",
            description=f"Disk layout: {len(partitions)} partition(s) — " +
                        ", ".join(p.get("description", "") for p in partitions[:3]),
            evidence_ref=call_id,
        ))

    result = TimelineResult(
        events=events, total_count=len(events),
        earliest=min(e.timestamp for e in events) if events else None,
        latest=max(e.timestamp for e in events) if events else None,
    )
    return ToolCallResult(
        tool_name="get_timeline", call_id=call_id,
        image_sha256=ctx.hash_before, hash_verified=True,
        duration_ms=ctx.duration_ms, data=result.model_dump()
    )
