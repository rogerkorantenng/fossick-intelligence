import asyncio
import subprocess
import tempfile
import os
import uuid
from pathlib import Path
from datetime import datetime
from mcp_server.models import PersistenceIndicator, PersistenceResult, ToolCallResult
from mcp_server.tools.integrity import EvidenceContext


SUSPICIOUS_STARTUP = {
    "winword.exe", "sysver.dll", "update.exe", "svhost.exe",
    "svchost32.exe", "csrss32.exe", "lsass32.exe",
}

BENIGN_STARTUP = {
    "desktop.ini", "remote assistance.lnk", "windows media player.lnk",
    "microsoft office.lnk", "msn.lnk", "outlook express.lnk",
}


def _get_segments(image_path: str) -> list[str]:
    """Return all EWF segments in order (E01, E02, ...)."""
    p = Path(image_path)
    segments = [image_path]
    if p.suffix.upper() == ".E01":
        i = 2
        while True:
            seg = p.with_suffix(f".E{i:02d}")
            if seg.exists():
                segments.append(str(seg))
                i += 1
            else:
                break
    return segments


def _mount_ewf(image_path: str, mount_point: str) -> bool:
    result = subprocess.run(
        ["ewfmount", image_path, mount_point],
        capture_output=True, text=True, timeout=30
    )
    return result.returncode == 0


def _get_ntfs_offset(image_ref: str | list) -> str:
    cmd = ["mmls"] + (image_ref if isinstance(image_ref, list) else [image_ref])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    for line in result.stdout.splitlines():
        if "NTFS" in line or ("07" in line.split() and len(line.split()) >= 3):
            parts = line.split()
            if len(parts) >= 3:
                return parts[2]
    return "63"


def _extract_inode(image_ref: str | list, offset: str, inode: str, outpath: str) -> bool:
    images = image_ref if isinstance(image_ref, list) else [image_ref]
    result = subprocess.run(
        ["icat", "-f", "ntfs", "-o", offset] + images + [inode],
        stdout=open(outpath, "wb"), stderr=subprocess.PIPE, timeout=30
    )
    return result.returncode == 0 and os.path.getsize(outpath) > 0


def _get_startup_items(image_ref: str | list, offset: str, call_id: str) -> list[PersistenceIndicator]:
    """Extract Windows Startup folder contents using fls.

    Two-pass approach: first find all Startup directory inodes via fls -r,
    then list each Startup directory non-recursively to get only direct children.
    This avoids depth-tracking bugs in recursive output parsing.
    """
    indicators = []
    images = image_ref if isinstance(image_ref, list) else [image_ref]

    # Pass 1: find all directory inodes named exactly "Startup"
    result = subprocess.run(
        ["fls", "-r", "-f", "ntfs", "-o", offset] + images,
        capture_output=True, text=True, timeout=120
    )

    startup_inodes = []
    for line in result.stdout.splitlines():
        if "d/d" not in line or ":" not in line:
            continue
        name = line.split(":")[-1].strip()
        if name != "Startup":
            continue
        # Extract inode number — format is "... d/d INODE:  Name"
        # Inode may look like "3723" or "3723-128-4"
        after_dd = line.split("d/d")[-1].split(":")[0].strip()
        inode = after_dd.split("-")[0].strip()
        if inode.isdigit():
            startup_inodes.append(inode)

    # Pass 2: list each Startup directory's direct children (non-recursive)
    for inode in startup_inodes:
        dir_result = subprocess.run(
            ["fls", "-f", "ntfs", "-o", offset] + images + [inode],
            capture_output=True, text=True, timeout=30
        )
        for line in dir_result.stdout.splitlines():
            if ("r/r" not in line and "r/-" not in line) or ":" not in line:
                continue
            name = line.split(":")[-1].strip()
            name_lower = name.lower()
            if name_lower in BENIGN_STARTUP or name_lower == "desktop.ini":
                continue
            is_suspicious = (
                name_lower in SUSPICIOUS_STARTUP or
                any(name_lower.endswith(ext) for ext in [".exe", ".dll", ".bat", ".vbs", ".ps1"])
            )
            if is_suspicious:
                indicators.append(PersistenceIndicator(
                    source="scheduled_task",
                    name=name,
                    path=f"Startup\\{name}",
                    evidence_ref=call_id,
                ))

    return indicators[:50]


def _parse_registry_hive(hive_path: str, call_id: str) -> list[PersistenceIndicator]:
    """Parse a registry hive using regipy to find Run/RunOnce keys."""
    indicators = []
    try:
        import regipy
        from regipy.registry import RegistryHive

        hive = RegistryHive(hive_path)

        # Check common persistence keys (try canonical path only — regipy is case-insensitive)
        run_keys = [
            "\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            "\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
        ]

        seen_names = set()
        for key_path in run_keys:
            try:
                key = hive.get_key(key_path)
                for val in key.get_values():
                    name = str(val.name or "")
                    data = str(val.value or "")
                    if name and data and name != "(Default)" and name not in seen_names:
                        seen_names.add(name)
                        indicators.append(PersistenceIndicator(
                            source="registry",
                            name=name,
                            path=key_path,
                            registry_key=f"{key_path}\\{name}",
                            evidence_ref=call_id,
                        ))
            except Exception:
                continue

    except ImportError:
        # regipy not available — use strings-based extraction
        try:
            result = subprocess.run(
                ["python3", "-c",
                 f"""
import struct, sys

with open('{hive_path}', 'rb') as f:
    data = f.read()

# Search for Run key signatures
run_markers = [b'Run\x00\x00', b'RunOnce\x00', b'CurrentVersion\\\\Run']
found = set()
for marker in run_markers:
    idx = 0
    while True:
        pos = data.find(marker, idx)
        if pos == -1:
            break
        # Extract nearby strings
        nearby = data[max(0,pos-200):pos+500]
        for b in nearby.split(b'\x00'):
            s = b.decode('utf-8', errors='ignore').strip()
            if len(s) > 5 and ('\\\\' in s or '.exe' in s.lower() or '.dll' in s.lower()):
                found.add(s[:200])
        idx = pos + 1

for s in list(found)[:10]:
    print(s)
"""],
                capture_output=True, text=True, timeout=15
            )
            for line in result.stdout.splitlines()[:10]:
                line = line.strip()
                if line and (".exe" in line.lower() or ".dll" in line.lower()):
                    indicators.append(PersistenceIndicator(
                        source="registry",
                        name=line[:80],
                        path="HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                        evidence_ref=call_id,
                    ))
        except Exception:
            pass

    return indicators


async def get_persistence(image_path: str) -> ToolCallResult:
    call_id = f"per_{uuid.uuid4().hex[:6]}"

    if not Path(image_path).exists():
        return ToolCallResult(
            tool_name="get_persistence", call_id=call_id,
            image_sha256="demo_mode", hash_verified=False,
            data=PersistenceResult(indicators=[], total_count=0).model_dump(),
            error=f"Image not found: {image_path} (demo mode)"
        )

    with EvidenceContext(image_path) as ctx:
        indicators = []
        segments = _get_segments(image_path)

        try:
            offset = await asyncio.to_thread(_get_ntfs_offset, segments)

            # 1. Startup folder entries
            startup_items = await asyncio.to_thread(_get_startup_items, segments, offset, call_id)
            indicators.extend(startup_items)

            # 2. Extract and parse NTUSER.DAT hives
            with tempfile.TemporaryDirectory() as tmpdir:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["fls", "-r", "-f", "ntfs", "-o", offset] + segments,
                    capture_output=True, text=True, timeout=120
                )

                # Find all NTUSER.DAT inodes — format: "++ r/r 10226-128-4:\tNTUSER.DAT"
                ntuser_inodes = []
                for line in result.stdout.splitlines():
                    if "NTUSER.DAT" not in line or "r/r" not in line or "LOG" in line:
                        continue
                    name = line.split(":")[-1].strip().lower()
                    if name != "ntuser.dat":
                        continue
                    # Extract inode from between "r/r " and ":"
                    after_rr = line.split("r/r")[-1].split(":")[0].strip()
                    if after_rr:
                        ntuser_inodes.append(after_rr)

                for i, inode in enumerate(ntuser_inodes[:6]):  # check up to 6 users
                    hive_path = os.path.join(tmpdir, f"ntuser_{i}.dat")
                    extracted = await asyncio.to_thread(
                        _extract_inode, segments, offset, inode, hive_path
                    )
                    if extracted:
                        reg_items = await asyncio.to_thread(
                            _parse_registry_hive, hive_path, call_id
                        )
                        indicators.extend(reg_items)

        except Exception as e:
            indicators.append(PersistenceIndicator(
                source="scheduled_task",
                name=f"Analysis note: {str(e)[:100]}",
                path="system",
                evidence_ref=call_id,
            ))

    result = PersistenceResult(indicators=indicators, total_count=len(indicators))
    return ToolCallResult(
        tool_name="get_persistence", call_id=call_id,
        image_sha256=ctx.hash_before, hash_verified=True,
        duration_ms=ctx.duration_ms, data=result.model_dump()
    )
