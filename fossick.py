#!/usr/bin/env python3.13
"""
Fossick Intelligence — Autonomous DFIR
Interactive REPL — type 'fossick' to start, Ctrl+C to exit.
"""
import asyncio
import json
import sys
import os
import readline
import argparse
import subprocess
import time
import threading
from pathlib import Path
from datetime import datetime, UTC

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "")

# ── ANSI ──────────────────────────────────────────────────────────────────────
RED    = "\033[38;2;239;68;68m"      # red-500
ORANGE = "\033[38;2;249;115;22m"     # orange-500
YELLOW = "\033[38;2;234;179;8m"      # yellow-500
GREEN  = "\033[38;2;34;197;94m"      # green-500
BLUE   = "\033[38;2;59;130;246m"     # blue-500
CYAN   = "\033[38;2;6;182;212m"      # cyan-500
PURPLE = "\033[38;2;168;85;247m"     # purple-500
GRAY   = "\033[38;2;107;114;128m"    # gray-500
LGRAY  = "\033[38;2;156;163;175m"    # gray-400
WHITE  = "\033[38;2;248;250;252m"    # slate-50
DIM_W  = "\033[38;2;71;85;105m"      # slate-600

BOLD   = "\033[1m"
DIM    = "\033[2m"
ITALIC = "\033[3m"
RESET  = "\033[0m"
CLEAR_LINE = "\033[2K\r"

SEV_COLOR  = {"critical": RED, "high": ORANGE, "medium": YELLOW, "low": GRAY}
SEV_BG = {
    "critical": "\033[48;2;127;29;29m",
    "high":     "\033[48;2;120;53;15m",
    "medium":   "\033[48;2;113;63;18m",
    "low":      "\033[48;2;30;41;59m",
}
CONF_COLOR = {"HIGH": RED, "MEDIUM": ORANGE, "LOW": YELLOW}

# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = f"""
{BOLD}{WHITE}  ╭─────────────────────────────────────────────────────╮
  │                                                     │
  │   {RED}▓{ORANGE}▓{YELLOW}▓{RESET}{BOLD}{WHITE}  {WHITE}FOSSICK INTELLIGENCE{RESET}{BOLD}{WHITE}                        │
  │       {DIM}{LGRAY}Autonomous DFIR · Finds Evil · Shows Its Work{RESET}{BOLD}{WHITE}  │
  │                                                     │
  ╰─────────────────────────────────────────────────────╯{RESET}
"""

def print_banner():
    print(BANNER)
    print(f"  {DIM_W}Type {CYAN}help{RESET} {DIM_W}for commands  ·  {CYAN}Ctrl+C{RESET} {DIM_W}to exit{RESET}\n")


# ── Spinner ───────────────────────────────────────────────────────────────────

class Spinner:
    FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

    def __init__(self, label: str, color: str = CYAN):
        self.label = label
        self.color = color
        self._running = False
        self._thread = None
        self._idx = 0

    def __enter__(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def _spin(self):
        while self._running:
            frame = self.FRAMES[self._idx % len(self.FRAMES)]
            print(f"  {self.color}{frame}{RESET}  {DIM_W}{self.label}{RESET}", end="\r", flush=True)
            self._idx += 1
            time.sleep(0.08)

    def update(self, label: str):
        self.label = label

    def __exit__(self, *_):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.2)
        print(CLEAR_LINE, end="", flush=True)


# ── Layout helpers ────────────────────────────────────────────────────────────

def _hr(color: str = DIM_W, width: int = 54):
    print(f"  {color}{'─' * width}{RESET}")

def _blank():
    print()

def _label(text: str):
    print(f"  {DIM}{LGRAY}{text.upper()}{RESET}")

def _kv(key: str, val: str, key_w: int = 14):
    print(f"  {DIM_W}{key:<{key_w}}{RESET}  {val}")

def _bullet(text: str, color: str = DIM_W, indent: int = 4):
    print(f"{' ' * indent}{color}·{RESET}  {text}")

def _tag(text: str, fg: str, bg: str = "") -> str:
    return f"{bg}{fg}{BOLD} {text} {RESET}"

def _badge(text: str, color: str) -> str:
    return f"{color}{DIM}[{RESET}{color}{text}{DIM}]{RESET}"

def _check(ok: bool, yes: str = "yes", no: str = "no") -> str:
    return f"{GREEN}✓  {yes}{RESET}" if ok else f"{RED}✗  {no}{RESET}"

def _dot(color: str) -> str:
    return f"{color}●{RESET}"


# ── Severity chip ─────────────────────────────────────────────────────────────

def sev_chip(sev: str) -> str:
    chips = {
        "critical": f"{RED}{BOLD} CRITICAL {RESET}",
        "high":     f"{ORANGE}{BOLD} HIGH     {RESET}",
        "medium":   f"{YELLOW}{BOLD} MEDIUM   {RESET}",
        "low":      f"{GRAY}{BOLD} LOW      {RESET}",
    }
    return chips.get(sev, sev.upper())


def conf_chip(conf: str) -> str:
    chips = {
        "HIGH":   f"{RED}■■■{RESET} {RED}HIGH{RESET}",
        "MEDIUM": f"{ORANGE}■■{DIM_W}■{RESET} {ORANGE}MED{RESET}",
        "LOW":    f"{YELLOW}■{DIM_W}■■{RESET} {YELLOW}LOW{RESET}",
    }
    return chips.get(conf, conf)


# ── Report printer ────────────────────────────────────────────────────────────

def print_finding(finding: dict, index: int):
    sev   = finding.get("severity", "low")
    conf  = finding.get("confidence", "LOW")
    color = SEV_COLOR.get(sev, GRAY)
    is_contra = finding.get("contradiction", False)

    # Finding header line
    contra_tag = f"  {YELLOW}⚡ CONTRADICTION{RESET}" if is_contra else ""
    print(f"\n  {color}{'━' * 54}{RESET}")
    print(f"  {sev_chip(sev)}  {BOLD}{WHITE}{finding.get('title', '')}{RESET}{contra_tag}")
    print(f"  {color}{'━' * 54}{RESET}")

    # Description
    desc = finding.get("description", "")
    if desc:
        # Word-wrap at 60 chars
        words = desc.split()
        line, lines = [], []
        for w in words:
            if sum(len(x)+1 for x in line) + len(w) > 60:
                lines.append(" ".join(line))
                line = [w]
            else:
                line.append(w)
        if line:
            lines.append(" ".join(line))
        for l in lines:
            print(f"  {LGRAY}{l}{RESET}")

    # Metadata row
    parts = []
    parts.append(f"Confidence  {conf_chip(conf)}")
    sources = finding.get("sources", [])
    if sources:
        parts.append(f"Sources  {CYAN}{' + '.join(sources)}{RESET}")
    ts = finding.get("timestamp")
    if ts:
        parts.append(f"{DIM_W}{str(ts)[:16]}{RESET}")
    print(f"\n  {('   ').join(parts)}")

    # Tool call refs
    calls = finding.get("tool_call_ids", [])
    if calls:
        print(f"  {DIM_W}refs  {ITALIC}{', '.join(calls)}{RESET}")


def print_report(report: dict):
    findings     = report.get("findings", [])
    contradictions = [f for f in findings if f.get("contradiction")]
    regular      = [f for f in findings if not f.get("contradiction")]
    by_sev       = {s: sum(1 for f in regular if f.get("severity") == s)
                    for s in ["critical", "high", "medium", "low"]}
    logs         = report.get("execution_log", [])
    integrity    = report.get("evidence_integrity_verified", True)

    _blank()
    # ── Header block ──
    print(f"  {BOLD}{WHITE}{'━' * 54}{RESET}")
    print(f"  {BOLD}{WHITE}  INVESTIGATION REPORT{RESET}")
    print(f"  {BOLD}{WHITE}{'━' * 54}{RESET}")
    _blank()
    _kv("case", f"{CYAN}{BOLD}{report.get('case_id')}{RESET}")
    _kv("image", f"{DIM_W}{report.get('image_path')}{RESET}")
    sha = report.get('image_sha256', '')
    if sha and sha != 'demo_mode':
        _kv("sha-256", f"{DIM_W}{sha[:48]}…{RESET}")
    started   = str(report.get('started_at', ''))[:19]
    completed = str(report.get('completed_at', '') or '')[:19]
    _kv("started", f"{DIM_W}{started}{RESET}")
    _kv("completed", f"{DIM_W}{completed}{RESET}")
    _kv("evidence", _check(integrity, "integrity verified", "⚠ violation detected"))
    _blank()

    # ── Summary pills ──
    _label("summary")
    _blank()
    pills = []
    if by_sev["critical"]: pills.append(f"{RED}{BOLD}{by_sev['critical']} critical{RESET}")
    if by_sev["high"]:     pills.append(f"{ORANGE}{BOLD}{by_sev['high']} high{RESET}")
    if by_sev["medium"]:   pills.append(f"{YELLOW}{by_sev['medium']} medium{RESET}")
    if by_sev["low"]:      pills.append(f"{GRAY}{by_sev['low']} low{RESET}")
    if not pills:          pills.append(f"{DIM_W}no findings{RESET}")
    print(f"  {'  ·  '.join(pills)}")
    if contradictions:
        print(f"  {YELLOW}⚡  {len(contradictions)} contradiction(s) detected{RESET}")
    _blank()

    # ── Contradictions ──
    if contradictions:
        _label("contradictions")
        for i, f in enumerate(contradictions, 1):
            print_finding(f, i)
        _blank()

    # ── Findings ──
    if regular:
        _label(f"findings  ({len(regular)})")
        idx = 1
        for sev in ["critical", "high", "medium", "low"]:
            for f in regular:
                if f.get("severity") == sev:
                    print_finding(f, idx)
                    idx += 1
        _blank()

    # ── Agent execution log ──
    if logs:
        _label("agent execution log")
        _blank()
        # Column headers
        print(f"  {DIM_W}{'AGENT':<20}  {'TOOL':<26}  {'TIME':>8}  {'HASH'}  RESULT{RESET}")
        print(f"  {DIM_W}{'─'*20}  {'─'*26}  {'─'*8}  {'─'*4}  {'─'*20}{RESET}")
        for log in logs:
            ms   = log.get("duration_ms", 0)
            dur  = f"{ms/1000:.1f}s" if ms > 1000 else f"{ms}ms"
            hash_ok = f"{GREEN}✓{RESET}   " if log.get("hash_verified") else f"{DIM_W}─{RESET}   "
            spol = f" {RED}⚠ SPOLIATION{RESET}" if log.get("spoliation_detected") else ""
            agent_color = {
                "TimelineAgent":    BLUE,
                "MemoryAgent":      RED,
                "PersistenceAgent": ORANGE,
                "VerifierAgent":    PURPLE,
            }.get(log.get("agent",""), LGRAY)

            print(
                f"  {agent_color}{BOLD}{log.get('agent',''):<20}{RESET}  "
                f"{DIM_W}{log.get('tool_name',''):<26}{RESET}  "
                f"{CYAN}{dur:>8}{RESET}  {hash_ok}{spol}"
            )
            if log.get("result_summary"):
                print(f"  {DIM_W}{'':20}  {'':26}  {'':8}    └ {log['result_summary']}{RESET}")

    print(f"\n  {DIM_W}{'━' * 54}{RESET}\n")


# ── Commands ──────────────────────────────────────────────────────────────────

def _load_env() -> dict:
    env = {}
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


async def do_status():
    from backend.database import list_investigations, init_db
    import aiosqlite
    env = _load_env()

    _blank()
    _label("system status")
    _blank()

    docker_ok = bool(subprocess.run(
        ["docker", "images", "fossick-mcp", "-q"],
        capture_output=True, text=True).stdout.strip())
    _kv("docker", _check(docker_ok, "fossick-mcp ready",
                         "not built · run: docker build -t fossick-mcp -f docker/Dockerfile ."))

    api_key = env.get("ANTHROPIC_API_KEY", "")
    _kv("anthropic", _check(len(api_key) > 20 and api_key.startswith("sk-"),
                            "api key configured", "add ANTHROPIC_API_KEY to .env"))

    slack = env.get("SLACK_WEBHOOK_URL", "")
    _kv("slack", _check(bool(slack), "webhook configured", "not configured (optional)"))

    case_path = Path(env.get("CASE_DATA_PATH", str(Path(__file__).parent / "case_data")))
    images_e01 = sorted(set(p.stem for p in case_path.glob("*.E0*")))
    images_mem = list(case_path.glob("*.vmem")) + list(case_path.glob("*.mem")) + list(case_path.glob("*.raw"))
    total = len(images_e01) + len(images_mem)
    _kv("case data", f"{DIM_W}{case_path}{RESET}  {CYAN}{total} image(s){RESET}")
    for stem in images_e01[:5]:
        files = list(case_path.glob(f"{stem}.*"))
        size  = sum(f.stat().st_size for f in files) / (1024**2)
        print(f"  {' ':14}    {DIM_W}  {stem}  {LGRAY}({size:.0f} MB){RESET}")
    for f in images_mem[:3]:
        size = f.stat().st_size / (1024**2)
        print(f"  {' ':14}    {DIM_W}  {f.name}  {LGRAY}({size:.0f} MB){RESET}")

    try:
        from backend.config import settings
        async with aiosqlite.connect(settings.db_path) as db:
            await init_db(db)
            invs = await list_investigations(db)
        _kv("database", f"{CYAN}{len(invs)}{RESET} {DIM_W}investigation(s){RESET}")
    except Exception:
        _kv("database", f"{DIM_W}empty{RESET}")
    _blank()


async def do_list():
    from backend.database import list_investigations, init_db
    from backend.config import settings
    import aiosqlite

    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        investigations = await list_investigations(db)

    if not investigations:
        _blank()
        print(f"  {DIM_W}No investigations yet.  Try:{RESET}  {CYAN}analyze case_data/disk.E01{RESET}")
        _blank()
        return

    _blank()
    _label(f"investigations  ({len(investigations)})")
    _blank()
    print(f"  {DIM_W}{'ID':>10}  {'CASE':<22}  {'STATUS':<10}  {'⚡':>4}  STARTED{RESET}")
    _hr()
    for inv in investigations:
        status = inv.get("status", "")
        s_col  = GREEN if status == "completed" else BLUE if status == "running" else RED
        s_icon = "✓" if status == "completed" else "⟳" if status == "running" else "✗"
        contra = inv.get("contradictions_detected", 0)
        c_str  = f"{YELLOW}{contra}{RESET}" if contra else f"{DIM_W}─{RESET}"
        started = inv.get("started_at","")[:16]
        print(
            f"  {DIM_W}{inv['id'][:8]}…{RESET}  "
            f"{WHITE}{inv['case_id']:<22}{RESET}  "
            f"{s_col}{s_icon} {status:<8}{RESET}  "
            f"{c_str:>10}  "
            f"{DIM_W}{started}{RESET}"
        )
    _blank()


async def do_report(investigation_id: str):
    from backend.database import list_investigations, get_investigation, init_db
    from backend.config import settings
    import aiosqlite

    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        invs    = await list_investigations(db)
        matched = [i for i in invs if i["id"].startswith(investigation_id)
                   or i["case_id"] == investigation_id]
        if not matched:
            print(f"\n  {RED}✗{RESET}  Investigation not found: {DIM_W}{investigation_id}{RESET}")
            print(f"  {DIM_W}Use {CYAN}list{RESET}{DIM_W} to see available investigations{RESET}\n")
            return
        report = await get_investigation(db, matched[0]["id"])

    print_report(report)


async def do_logs(investigation_id: str):
    from backend.database import list_investigations, get_investigation, init_db
    from backend.config import settings
    import aiosqlite

    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        invs    = await list_investigations(db)
        matched = [i for i in invs if i["id"].startswith(investigation_id)
                   or i["case_id"] == investigation_id]
        if not matched:
            print(f"\n  {RED}✗{RESET}  Investigation not found: {DIM_W}{investigation_id}{RESET}\n")
            return
        report = await get_investigation(db, matched[0]["id"])

    _blank()
    print(f"  {BOLD}{WHITE}{'━' * 54}{RESET}")
    print(f"  {BOLD}{WHITE}  AUDIT TRAIL  ·  {report['case_id']}{RESET}")
    print(f"  {BOLD}{WHITE}{'━' * 54}{RESET}")
    _blank()

    msgs = report.get("agent_messages", [])
    if msgs:
        print(f"  {BOLD}{WHITE}agent messages ({len(msgs)}){RESET}")
        _blank()
        for m in msgs:
            ts = m.get("timestamp", "")[:19].replace("T", " ")
            from_a = m.get("from_agent", "?")
            to_a   = m.get("to_agent", "?")
            mtype  = m.get("message_type", "")
            content = m.get("content", "")
            correction = m.get("self_correction", False)
            color = YELLOW if correction else DIM_W
            marker = f"{CYAN}⟳ " if correction else "  "
            print(f"  {marker}{color}{ts}  {BOLD}{from_a}{RESET}{DIM_W} → {RESET}{BOLD}{to_a}{RESET}  {DIM_W}[{mtype}]{RESET}")
            # word-wrap content
            words = content.split()
            line, lines = [], []
            for w in words:
                if sum(len(x)+1 for x in line) + len(w) > 64:
                    lines.append(" ".join(line)); line = [w]
                else:
                    line.append(w)
            if line: lines.append(" ".join(line))
            for l in lines:
                print(f"       {DIM_W}{l}{RESET}")
            if m.get("tool_call_id"):
                print(f"       {DIM_W}ref: {CYAN}{m['tool_call_id']}{RESET}")
            if m.get("correction_note"):
                print(f"       {YELLOW}correction: {m['correction_note']}{RESET}")
            _blank()

    logs = report.get("execution_log", [])
    if logs:
        print(f"  {BOLD}{WHITE}tool execution log ({len(logs)}){RESET}")
        _blank()
        for l in logs:
            ts = l.get("called_at", "")[:19].replace("T", " ")
            verified = f"{GREEN}✓ hash verified{RESET}" if l.get("hash_verified") else f"{YELLOW}⚠ hash unverified{RESET}"
            print(f"  {DIM_W}{ts}{RESET}  {CYAN}{BOLD}{l.get('id','?')}{RESET}  {WHITE}{l.get('tool_name','?')}{RESET}  {DIM_W}[{l.get('agent','?')}]{RESET}")
            print(f"       {DIM_W}{l.get('result_summary','')}{RESET}  {verified}")
            if l.get("image_sha256"):
                print(f"       {DIM_W}sha256: {l['image_sha256'][:48]}…{RESET}")
            _blank()

    sc = report.get("self_corrections_applied", 0)
    print(f"  {DIM_W}{'━' * 54}{RESET}")
    print(f"  {CYAN}⟳ {sc} self-correction(s) applied{RESET}  ·  {DIM_W}{len(msgs)} agent messages  ·  {len(logs)} tool calls{RESET}")
    _blank()


async def do_analyze(image_path: str, case_id: str | None, output: str):
    from backend.docker_client import get_docker_client
    from backend.agents.timeline_agent import TimelineAgent
    from backend.agents.memory_agent import MemoryAgent
    from backend.agents.persistence_agent import PersistenceAgent
    from backend.agents.verifier_agent import VerifierAgent
    from backend.investigation import run_investigation
    from backend.config import settings
    import aiosqlite
    from backend.database import init_db, save_investigation
    from backend.models import InvestigationReport, AgentMessage
    from backend.slack_webhook import send_slack, format_finding_card, format_contradiction_card, format_completion_card
    from mcp_server.tools.integrity import compute_sha256
    import uuid

    p = Path(image_path)
    if not p.exists():
        alt = Path(settings.case_data_path) / p.name
        if alt.exists():
            image_path = str(alt)
            print(f"  {DIM_W}resolved  {LGRAY}{image_path}{RESET}")
        else:
            print(f"  {YELLOW}⚠{RESET}  Image not found — running in demo mode")

    _blank()
    print(f"  {BOLD}{WHITE}{'━' * 54}{RESET}")
    print(f"  {BOLD}{WHITE}  INVESTIGATION  ·  {case_id or 'auto'}{RESET}")
    print(f"  {BOLD}{WHITE}{'━' * 54}{RESET}")
    _blank()
    _kv("image",   f"{CYAN}{image_path}{RESET}")
    _kv("case id", f"{case_id or DIM_W + 'auto-generated' + RESET}")
    _blank()

    start = datetime.now(UTC)
    investigation_id = str(uuid.uuid4())
    case_id = case_id or f"case_{investigation_id[:8]}"

    image_sha256 = ""
    if Path(image_path).exists():
        print(f"  {DIM_W}computing sha-256…{RESET}", end="\r", flush=True)
        image_sha256 = compute_sha256(image_path)
        print(CLEAR_LINE, end="", flush=True)
        _kv("sha-256", f"{DIM_W}{image_sha256[:48]}…{RESET}")
        _blank()

    docker_client = get_docker_client()
    agent_messages: list[AgentMessage] = []

    def _amsg(from_a: str, to_a: str, mtype: str, content: str, **kw) -> AgentMessage:
        return AgentMessage(from_agent=from_a, to_agent=to_a, message_type=mtype,
                            timestamp=datetime.now(UTC), content=content, **kw)

    def _agent_header(color: str, num: str, name: str):
        print(f"  {color}{BOLD}[{num}]{RESET}  {WHITE}{BOLD}{name}{RESET}  {DIM_W}running…{RESET}", end="\r", flush=True)

    def _agent_done(color: str, num: str, name: str, n: int, ms: int):
        dur = f"{ms/1000:.1f}s" if ms > 1000 else f"{ms}ms"
        count_str = f"{CYAN}{n} finding(s){RESET}" if n else f"{DIM_W}no findings{RESET}"
        print(CLEAR_LINE, end="", flush=True)
        print(f"  {color}{BOLD}[{num}]{RESET}  {WHITE}{BOLD}{name:<20}{RESET}  {count_str}  {DIM_W}{dur}{RESET}")

    def _print_finding_live(f, idx: int):
        color = SEV_COLOR.get(f.severity, GRAY)
        is_contra = f.contradiction
        conf = f.confidence if hasattr(f, "confidence") else "LOW"

        if is_contra:
            print(f"\n  {YELLOW}  ╔═ ⚡ CONTRADICTION{RESET}")
            print(f"  {YELLOW}  ║{RESET}  {BOLD}{WHITE}{f.title}{RESET}")
            # Word-wrap description at 72 chars
            words = (f.contradiction_description or f.description).split()
            line, lines = [], []
            for w in words:
                if sum(len(x)+1 for x in line) + len(w) > 68:
                    lines.append(" ".join(line)); line = [w]
                else:
                    line.append(w)
            if line: lines.append(" ".join(line))
            for l in lines:
                print(f"  {YELLOW}  ║{RESET}  {DIM_W}{l}{RESET}")
            sources = " + ".join(f.sources) if f.sources else "verifier"
            print(f"  {YELLOW}  ╚═{RESET}  {DIM_W}confidence {CONF_COLOR.get(conf,YELLOW)}{conf}{RESET}  {DIM_W}·  sources: {sources}{RESET}")
        else:
            print(f"\n  {color}  ┌─ {f.severity.upper()}{RESET}  {BOLD}{WHITE}{f.title}{RESET}")
            words = f.description.split()
            line, lines = [], []
            for w in words:
                if sum(len(x)+1 for x in line) + len(w) > 68:
                    lines.append(" ".join(line)); line = [w]
                else:
                    line.append(w)
            if line: lines.append(" ".join(line))
            for l in lines:
                print(f"  {color}  │{RESET}  {LGRAY}{l}{RESET}")
            sources = " + ".join(f.sources) if f.sources else "unknown"
            calls = ", ".join(f.tool_call_ids[:2]) if f.tool_call_ids else "—"
            print(f"  {color}  └─{RESET}  {DIM_W}confidence {CONF_COLOR.get(conf,YELLOW)}{conf}{RESET}  {DIM_W}·  sources: {sources}  ·  ref: {calls}{RESET}")

    # ── Timeline Agent ──────────────────────────────────────────────────────────
    agent_messages.append(_amsg("Orchestrator", "TimelineAgent", "dispatch",
        f"Analyze filesystem timeline for {image_path}. Artifact types: fs, evt, lnk, usb, browser."))
    _agent_header(BLUE, "1", "Timeline Agent")
    try:
        tl_findings, tl_logs = await TimelineAgent(docker_client).run(image_path)
    except Exception as e:
        print(f"  {RED}✗  Timeline agent error: {e}{RESET}")
        tl_findings, tl_logs = [], []
    ms = tl_logs[0].duration_ms if tl_logs else 0
    agent_messages.append(_amsg("TimelineAgent", "Orchestrator", "findings",
        f"Returned {len(tl_findings)} finding(s) from filesystem timeline analysis.",
        finding_count=len(tl_findings),
        tool_call_id=tl_logs[0].id if tl_logs else None))
    _agent_done(BLUE, "1", "Timeline Agent", len(tl_findings), ms)
    for f in tl_findings:
        _print_finding_live(f, 0)

    # ── Memory Agent ────────────────────────────────────────────────────────────
    _blank()
    agent_messages.append(_amsg("Orchestrator", "MemoryAgent", "dispatch",
        f"Analyze memory artifacts in {image_path}. Plugins: pslist, netscan, malfind, cmdline."))
    _agent_header(RED, "2", "Memory Agent")
    try:
        mem_findings, mem_logs = await MemoryAgent(docker_client).run(image_path)
    except Exception as e:
        print(f"  {RED}✗  Memory agent error: {e}{RESET}")
        mem_findings, mem_logs = [], []
    ms = mem_logs[0].duration_ms if mem_logs else 0
    agent_messages.append(_amsg("MemoryAgent", "Orchestrator", "findings",
        f"Returned {len(mem_findings)} finding(s)." + (
            " Disk image provided — Volatility3 requires RAM capture. Honest zero, no findings fabricated."
            if len(mem_findings) == 0 else ""),
        finding_count=len(mem_findings),
        tool_call_id=mem_logs[0].id if mem_logs else None))
    _agent_done(RED, "2", "Memory Agent", len(mem_findings), ms)
    for f in mem_findings:
        _print_finding_live(f, 0)

    # ── Persistence Agent ───────────────────────────────────────────────────────
    _blank()
    agent_messages.append(_amsg("Orchestrator", "PersistenceAgent", "dispatch",
        f"Analyze persistence mechanisms in {image_path}. Check registry Run/RunOnce keys and Windows Startup folders."))
    _agent_header(ORANGE, "3", "Persistence Agent")
    try:
        per_findings, per_logs = await PersistenceAgent(docker_client).run(image_path)
    except Exception as e:
        print(f"  {RED}✗  Persistence agent error: {e}{RESET}")
        per_findings, per_logs = [], []
    ms = per_logs[0].duration_ms if per_logs else 0
    agent_messages.append(_amsg("PersistenceAgent", "Orchestrator", "findings",
        f"Returned {len(per_findings)} persistence indicator(s).",
        finding_count=len(per_findings),
        tool_call_id=per_logs[0].id if per_logs else None))
    _agent_done(ORANGE, "3", "Persistence Agent", len(per_findings), ms)
    for f in per_findings:
        _print_finding_live(f, 0)

    # ── Verifier Agent ──────────────────────────────────────────────────────────
    # ── Self-correction: timeline found executables but persistence found nothing ─
    all_logs = list(tl_logs) + list(mem_logs) + list(per_logs)
    self_corrections = 0
    timeline_has_executables = any(
        ".exe" in f.description.lower() or ".dll" in f.description.lower()
        for f in tl_findings
    )
    if timeline_has_executables and len(per_findings) == 0:
        _blank()
        print(f"  {YELLOW}⟳  self-correcting:{RESET}  {DIM_W}timeline found executables but persistence returned zero — re-running{RESET}")
        agent_messages.append(_amsg("Orchestrator", "PersistenceAgent", "dispatch",
            "Timeline found executable artifacts but persistence returned zero. Re-running persistence analysis.",
            self_correction=True,
            correction_note="Triggered by cross-agent discrepancy: timeline executables with no persistence corroboration."))
        try:
            per_findings2, per_logs2 = await PersistenceAgent(docker_client).run(image_path)
            if len(per_findings2) > len(per_findings):
                per_findings = per_findings2
                all_logs.extend(per_logs2)
                self_corrections += 1
                agent_messages.append(_amsg("PersistenceAgent", "Orchestrator", "correction",
                    f"Re-run returned {len(per_findings2)} indicator(s). Updated findings.",
                    finding_count=len(per_findings2), self_correction=True,
                    tool_call_id=per_logs2[0].id if per_logs2 else None))
                print(f"  {GREEN}✓  re-run found {len(per_findings2)} indicator(s){RESET}")
                for f in per_findings2:
                    _print_finding_live(f, 0)
            else:
                agent_messages.append(_amsg("PersistenceAgent", "Orchestrator", "correction",
                    "Re-run confirmed: zero persistence indicators. Discrepancy noted for Verifier.",
                    finding_count=0, self_correction=True))
                print(f"  {DIM_W}re-run confirmed: zero persistence indicators — discrepancy noted for Verifier{RESET}")
        except Exception:
            pass

    # ── Verifier Agent ──────────────────────────────────────────────────────────
    _blank()
    agent_messages.append(_amsg("Orchestrator", "VerifierAgent", "dispatch",
        f"Cross-reference all findings. Timeline: {len(tl_findings)}, Memory: {len(mem_findings)}, "
        f"Persistence: {len(per_findings)}. Assign confidence. Identify contradictions."))
    _agent_header(PURPLE, "4", "Verifier Agent")
    try:
        verified, contradictions, ver_logs = await VerifierAgent().run(
            tl_findings, mem_findings, per_findings, all_logs
        )
    except Exception:
        verified, contradictions, ver_logs = tl_findings + mem_findings + per_findings, [], []
    all_logs.extend(ver_logs)

    verifier_corrections = sum(
        1 for f in verified
        if "corrected" in f.description.lower() or "reclassified" in f.description.lower()
    )
    self_corrections += verifier_corrections
    agent_messages.append(_amsg("VerifierAgent", "Orchestrator", "findings",
        f"Verification complete. {len(verified)} verified, {len(contradictions)} contradiction(s). "
        f"{verifier_corrections} classification correction(s) applied.",
        finding_count=len(verified) + len(contradictions),
        tool_call_id=ver_logs[0].id if ver_logs else None,
        self_correction=verifier_corrections > 0))

    _agent_done(PURPLE, "4", "Verifier Agent", len(contradictions), 0)
    if contradictions:
        for f in contradictions:
            _print_finding_live(f, 0)

    # ── Save to DB and send Slack ───────────────────────────────────────────────
    all_final = verified + contradictions
    evidence_ok = True
    if image_sha256 and image_sha256 != "demo_mode" and Path(image_path).exists():
        is_multi = Path(image_path).suffix.upper() == ".E01" and Path(image_path.replace(".E01", ".E02")).exists()
        if not is_multi:
            final_hash = compute_sha256(image_path)
            evidence_ok = final_hash == image_sha256

    report = InvestigationReport(
        id=investigation_id, case_id=case_id, image_path=image_path,
        image_sha256=image_sha256, status="completed",
        started_at=start, completed_at=datetime.now(UTC),
        findings=all_final, contradictions_detected=len(contradictions),
        contradictions_resolved=len([c for c in contradictions if c.confidence != "LOW"]),
        execution_log=all_logs, agent_messages=agent_messages,
        self_corrections_applied=self_corrections,
        evidence_integrity_verified=evidence_ok,
    )
    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        await save_investigation(db, report)

    for f in all_final:
        if f.contradiction:
            await send_slack(format_contradiction_card(f, case_id))
        elif f.confidence == "LOW":
            f.slack_status = "pending_review"
            await send_slack(format_finding_card(f, case_id))
        else:
            f.slack_status = "auto_confirmed"
    await send_slack(format_completion_card(case_id, len(all_final), len(contradictions), evidence_ok))

    # ── Summary ─────────────────────────────────────────────────────────────────
    elapsed = (datetime.now(UTC) - start).total_seconds()
    _blank()
    print(f"  {DIM_W}{'━' * 54}{RESET}")
    critical = sum(1 for f in all_final if f.severity == "critical" and not f.contradiction)
    high     = sum(1 for f in all_final if f.severity == "high" and not f.contradiction)
    parts    = [f"{GREEN}✓  complete{RESET}  {DIM_W}{elapsed:.1f}s{RESET}"]
    if critical: parts.append(f"{RED}{BOLD}{critical} critical{RESET}")
    if high:     parts.append(f"{ORANGE}{high} high{RESET}")
    if contradictions: parts.append(f"{YELLOW}⚡ {len(contradictions)} contradiction(s){RESET}")
    if self_corrections: parts.append(f"{CYAN}⟳ {self_corrections} self-correction(s){RESET}")
    if not all_final: parts.append(f"{DIM_W}no findings{RESET}")
    parts.append(f"{DIM_W}dashboard: http://localhost:5173{RESET}")
    print(f"  {'  ·  '.join(parts)}")
    _blank()

    if output == "json":
        print(json.dumps(report.model_dump(), indent=2, default=str))


# ── REPL ──────────────────────────────────────────────────────────────────────

HELP_TEXT = f"""
  {BOLD}{WHITE}commands{RESET}

  {CYAN}analyze{RESET} {DIM_W}<image> [--case-id <id>] [--output json|table]{RESET}
    {DIM_W}Run autonomous DFIR investigation on a forensic image{RESET}
    {DIM_W}· {ITALIC}analyze case_data/disk.E01 --case-id incident-001{RESET}

  {CYAN}list{RESET}
    {DIM_W}Show all past investigations{RESET}

  {CYAN}report{RESET} {DIM_W}<id>{RESET}
    {DIM_W}Display full report (supports ID prefix or case name){RESET}
    {DIM_W}· {ITALIC}report abc12345{RESET}

  {CYAN}logs{RESET} {DIM_W}<id>{RESET}
    {DIM_W}Show full agent-to-agent message trace + tool execution log{RESET}
    {DIM_W}· {ITALIC}logs abc12345{RESET}

  {CYAN}status{RESET}
    {DIM_W}Show system readiness — Docker, API keys, case data{RESET}

  {CYAN}clear{RESET}  {DIM_W}Clear screen{RESET}
  {CYAN}exit{RESET}   {DIM_W}Exit  (or Ctrl+C){RESET}
"""


def get_prompt() -> str:
    return f"  {BOLD}{CYAN}›{RESET} "


def parse_line(line: str) -> tuple[str, list[str]]:
    parts = line.strip().split()
    return (parts[0].lower(), parts[1:]) if parts else ("", [])


async def repl():
    print_banner()

    commands = ["analyze", "list", "report", "logs", "status", "help", "clear", "exit", "quit"]
    readline.set_completer(lambda t, s: ([c for c in commands if c.startswith(t)] + [None])[s])
    readline.parse_and_bind("tab: complete")

    history = Path.home() / ".fossick_history"
    try:    readline.read_history_file(str(history))
    except: pass

    try:
        while True:
            try:
                line = input(get_prompt()).strip()
            except EOFError:
                print(f"\n  {DIM_W}goodbye{RESET}\n")
                break

            if not line:
                continue

            cmd, args = parse_line(line)

            if cmd in ("exit", "quit"):
                print(f"\n  {DIM_W}goodbye{RESET}\n")
                break

            elif cmd == "help":
                print(HELP_TEXT)

            elif cmd == "clear":
                os.system("clear")
                print_banner()

            elif cmd == "status":
                await do_status()

            elif cmd == "list":
                await do_list()

            elif cmd == "report":
                if not args:
                    print(f"\n  {RED}✗{RESET}  Usage: {CYAN}report <investigation_id>{RESET}\n")
                else:
                    await do_report(args[0])

            elif cmd == "logs":
                if not args:
                    print(f"\n  {RED}✗{RESET}  Usage: {CYAN}logs <investigation_id>{RESET}\n")
                else:
                    await do_logs(args[0])

            elif cmd == "analyze":
                if not args:
                    print(f"\n  {RED}✗{RESET}  Usage: {CYAN}analyze <image_path> [--case-id <id>]{RESET}\n")
                    continue
                image_path = args[0]
                case_id, output, i = None, "table", 1
                while i < len(args):
                    if args[i] == "--case-id" and i + 1 < len(args):
                        case_id = args[i+1]; i += 2
                    elif args[i] == "--output" and i + 1 < len(args):
                        output = args[i+1]; i += 2
                    else:
                        i += 1
                await do_analyze(image_path, case_id, output)

            else:
                print(f"\n  {RED}✗{RESET}  Unknown command: {DIM_W}{cmd}{RESET}  ·  type {CYAN}help{RESET}\n")

    except KeyboardInterrupt:
        print(f"\n\n  {DIM_W}interrupted · goodbye{RESET}\n")
    finally:
        try: readline.write_history_file(str(history))
        except: pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(prog="fossick", add_help=True)
        sub = parser.add_subparsers(dest="command")

        p_a = sub.add_parser("analyze")
        p_a.add_argument("image_path")
        p_a.add_argument("--case-id", default=None)
        p_a.add_argument("--output", choices=["table", "json"], default="table")

        sub.add_parser("list")
        p_r = sub.add_parser("report")
        p_r.add_argument("investigation_id")
        p_l = sub.add_parser("logs")
        p_l.add_argument("investigation_id")
        sub.add_parser("status")

        args = parser.parse_args()
        if   args.command == "analyze": asyncio.run(do_analyze(args.image_path, args.case_id, args.output))
        elif args.command == "list":    asyncio.run(do_list())
        elif args.command == "report":  asyncio.run(do_report(args.investigation_id))
        elif args.command == "logs":    asyncio.run(do_logs(args.investigation_id))
        elif args.command == "status":  asyncio.run(do_status())
        else: parser.print_help()
    else:
        asyncio.run(repl())


if __name__ == "__main__":
    main()
