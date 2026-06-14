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


def _mount_ewf(image_path: str, mount_point: str) -> bool:
    result = subprocess.run(
        ["ewfmount", image_path, mount_point],
        capture_output=True, text=True, timeout=30
    )
    return result.returncode == 0


def _get_ntfs_offset(ewf_raw: str) -> str:
    result = subprocess.run(["mmls", ewf_raw], capture_output=True, text=True, timeout=15)
    for line in result.stdout.splitlines():
        if "NTFS" in line or ("07" in line.split() and len(line.split()) >= 3):
            parts = line.split()
            if len(parts) >= 3:
                return parts[2]
    return "63"


def _extract_inode(ewf_raw: str, offset: str, inode: str, outpath: str) -> bool:
    result = subprocess.run(
        ["icat", "-f", "ntfs", "-o", offset, ewf_raw, inode],
        stdout=open(outpath, "wb"), stderr=subprocess.PIPE, timeout=30
    )
    return result.returncode == 0 and os.path.getsize(outpath) > 0


def _get_startup_items(ewf_raw: str, offset: str, call_id: str) -> list[PersistenceIndicator]:
    """Extract Startup folder contents using fls."""
    indicators = []
    result = subprocess.run(
        ["fls", "-r", "-f", "ntfs", "-o", offset, ewf_raw],
        capture_output=True, text=True, timeout=120
    )

    in_startup = False
    for line in result.stdout.splitlines():
        name_lower = Path(line.split(":")[-1].strip()).name.lower() if ":" in line else ""

        if "Startup" in line and "d/d" in line:
            in_startup = True
            continue

        if in_startup and ("r/r" in line or "r/-" in line) and ":" in line:
            name = line.split(":")[-1].strip()
            name_lower = name.lower()

            if name_lower in BENIGN_STARTUP or name_lower == "desktop.ini":
                in_startup = False
                continue

            # Flag suspicious startup entries
            is_suspicious = (
                name_lower in SUSPICIOUS_STARTUP or
                any(ext in name_lower for ext in [".exe", ".dll", ".bat", ".vbs", ".ps1"]) and
                name_lower not in BENIGN_STARTUP
            )

            if is_suspicious:
                indicators.append(PersistenceIndicator(
                    source="scheduled_task",  # reusing for startup
                    name=name,
                    path=f"Startup\\{name}",
                    evidence_ref=call_id,
                ))
        else:
            in_startup = False

    return indicators


def _parse_registry_hive(hive_path: str, call_id: str) -> list[PersistenceIndicator]:
    """Parse a registry hive using regipy to find Run/RunOnce keys."""
    indicators = []
    try:
        import regipy
        from regipy.registry import RegistryHive

        hive = RegistryHive(hive_path)

        # Check common persistence keys
        run_keys = [
            "\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            "\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
            "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
            "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
        ]

        for key_path in run_keys:
            try:
                key = hive.get_key(key_path)
                for val in key.get_values():
                    name = str(val.name or "")
                    data = str(val.value or "")
                    if name and data and name != "(Default)":
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
        mount_point = tempfile.mkdtemp(prefix="fossick_per_")

        try:
            if not _mount_ewf(image_path, mount_point):
                raise Exception("ewfmount failed")

            ewf_raw = os.path.join(mount_point, "ewf1")
            if not os.path.exists(ewf_raw):
                raise Exception("ewf1 not found after mount")

            offset = await asyncio.to_thread(_get_ntfs_offset, ewf_raw)

            # 1. Startup folder entries
            startup_items = await asyncio.to_thread(_get_startup_items, ewf_raw, offset, call_id)
            indicators.extend(startup_items)

            # 2. Extract and parse NTUSER.DAT hives
            with tempfile.TemporaryDirectory() as tmpdir:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["fls", "-r", "-f", "ntfs", "-o", offset, ewf_raw],
                    capture_output=True, text=True, timeout=120
                )

                # Find all NTUSER.DAT inodes
                ntuser_inodes = []
                for line in result.stdout.splitlines():
                    if "NTUSER.DAT" in line and "r/r" in line and "LOG" not in line:
                        parts = line.split()
                        for p in parts:
                            if "-128-" in p or "-128-4" in p:
                                ntuser_inodes.append(p.strip(":"))
                                break

                for i, inode in enumerate(ntuser_inodes[:3]):  # max 3 users
                    hive_path = os.path.join(tmpdir, f"ntuser_{i}.dat")
                    extracted = await asyncio.to_thread(
                        _extract_inode, ewf_raw, offset, inode, hive_path
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
        finally:
            subprocess.run(["umount", mount_point], capture_output=True)
            subprocess.run(["rmdir", mount_point], capture_output=True)

    result = PersistenceResult(indicators=indicators, total_count=len(indicators))
    return ToolCallResult(
        tool_name="get_persistence", call_id=call_id,
        image_sha256=ctx.hash_before, hash_verified=True,
        duration_ms=ctx.duration_ms, data=result.model_dump()
    )
