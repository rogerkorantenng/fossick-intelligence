#!/usr/bin/env python3.13
"""
Fossick — Autonomous DFIR Agent
Interactive REPL — type 'fossick' to start, Ctrl+C to exit.
"""
import asyncio
import json
import sys
import os
import readline
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "")

# ── ANSI colors ──────────────────────────────────────────────────────────────
RED    = "\033[91m"
ORANGE = "\033[93m"
YELLOW = "\033[33m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
PURPLE = "\033[95m"
GRAY   = "\033[90m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

SEV_COLOR  = {"critical": RED, "high": ORANGE, "medium": YELLOW, "low": GRAY}
CONF_COLOR = {"HIGH": RED, "MEDIUM": ORANGE, "LOW": YELLOW}

BANNER = f"""
{BOLD}{BLUE}  ╔══════════════════════════════════════════════════╗
  ║  {RED}F O S S I C K{BLUE}  ─  Autonomous DFIR Agent          ║
  ║  {DIM}Finds evil. Shows its work. Catches itself lying.{BLUE}  ║
  ╚══════════════════════════════════════════════════╝{RESET}
"""

HELP_TEXT = f"""
{BOLD}Available commands:{RESET}

  {CYAN}analyze{RESET} {DIM}<image_path>{RESET} {DIM}[--case-id <id>] [--output json|table]{RESET}
      Run autonomous DFIR investigation on a disk or memory image.
      {DIM}Example: analyze case_data/disk.E01 --case-id incident-001{RESET}

  {CYAN}list{RESET}
      Show all past investigations with status and findings count.

  {CYAN}report{RESET} {DIM}<investigation_id>{RESET}
      Display full report for an investigation (supports ID prefix).
      {DIM}Example: report abc12345{RESET}

  {CYAN}status{RESET}
      Show system status — Docker, API keys, case data, investigations.

  {CYAN}clear{RESET}
      Clear the terminal screen.

  {CYAN}help{RESET}
      Show this help message.

  {CYAN}exit{RESET} {DIM}or{RESET} {CYAN}quit{RESET} {DIM}or{RESET} {BOLD}Ctrl+C{RESET}
      Exit Fossick.
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_env() -> dict:
    env = {}
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _print(msg: str = ""):
    print(msg)


def _ok(msg: str):
    print(f"  {GREEN}✓{RESET} {msg}")


def _warn(msg: str):
    print(f"  {YELLOW}⚠{RESET} {msg}")


def _err(msg: str):
    print(f"  {RED}✗{RESET} {msg}")


def _section(title: str):
    print(f"\n  {BOLD}{title}{RESET}")
    print(f"  {'─' * (len(title) + 2)}")


def format_finding(finding: dict, index: int) -> str:
    sev   = finding.get("severity", "low")
    conf  = finding.get("confidence", "LOW")
    color = SEV_COLOR.get(sev, GRAY)
    contradiction = f"  {YELLOW}⚡ CONTRADICTION{RESET}" if finding.get("contradiction") else ""
    sources = " + ".join(finding.get("sources", []))
    return (
        f"\n  {color}{BOLD}[{index}] {sev.upper()} — {finding.get('title', '')}{RESET}{contradiction}\n"
        f"      {finding.get('description', '')[:200]}\n"
        f"      {DIM}Confidence: {CONF_COLOR.get(conf, GRAY)}{conf}{RESET}  "
        f"{DIM}Sources: {sources}{RESET}"
        + (f"\n      {DIM}Timestamp: {finding['timestamp']}{RESET}" if finding.get("timestamp") else "")
        + (f"\n      {DIM}Tool calls: {', '.join(finding['tool_call_ids'])}{RESET}" if finding.get("tool_call_ids") else "")
    )


def print_report(report: dict):
    _print(f"\n  {BOLD}{'═' * 56}{RESET}")
    _print(f"  {BOLD}  FOSSICK INVESTIGATION REPORT{RESET}")
    _print(f"  {'═' * 56}")
    _print(f"  Case ID:    {BLUE}{report.get('case_id')}{RESET}")
    _print(f"  Image:      {report.get('image_path')}")
    sha = report.get('image_sha256', '')
    if sha and sha != 'demo_mode':
        _print(f"  SHA-256:    {DIM}{sha[:48]}...{RESET}")
    _print(f"  Started:    {report.get('started_at', '')[:19]}")
    _print(f"  Completed:  {report.get('completed_at', '')[:19]}")
    integrity = report.get("evidence_integrity_verified", True)
    _print(f"  Evidence:   {GREEN + '✓ VERIFIED' + RESET if integrity else RED + '⚠ VIOLATION DETECTED' + RESET}")
    _print(f"  {'─' * 56}")

    findings     = report.get("findings", [])
    contradictions = [f for f in findings if f.get("contradiction")]
    regular      = [f for f in findings if not f.get("contradiction")]
    by_sev       = {s: sum(1 for f in regular if f.get("severity") == s)
                    for s in ["critical", "high", "medium", "low"]}

    _print(f"\n  {BOLD}SUMMARY{RESET}")
    _print(
        f"  {RED}Critical: {by_sev['critical']}{RESET}  "
        f"{ORANGE}High: {by_sev['high']}{RESET}  "
        f"{YELLOW}Medium: {by_sev['medium']}{RESET}  "
        f"{GRAY}Low: {by_sev['low']}{RESET}"
    )
    _print(f"  Contradictions: {len(contradictions)}  |  Total findings: {len(findings)}")

    if contradictions:
        _print(f"\n  {BOLD}{YELLOW}⚡ CONTRADICTIONS ({len(contradictions)}){RESET}")
        for i, f in enumerate(contradictions, 1):
            _print(format_finding(f, i))

    if regular:
        _print(f"\n  {BOLD}FINDINGS ({len(regular)}){RESET}")
        idx = 1
        for sev in ["critical", "high", "medium", "low"]:
            for f in regular:
                if f.get("severity") == sev:
                    _print(format_finding(f, idx))
                    idx += 1

    logs = report.get("execution_log", [])
    if logs:
        _print(f"\n  {BOLD}AGENT EXECUTION LOG{RESET}")
        for log in logs:
            ms       = log.get("duration_ms", 0)
            dur      = f"{ms/1000:.1f}s" if ms > 1000 else f"{ms}ms"
            hash_ok  = f"{GREEN}✓{RESET}" if log.get("hash_verified") else f"{DIM}─{RESET}"
            spoliation = f" {RED}⚠ SPOLIATION{RESET}" if log.get("spoliation_detected") else ""
            _print(
                f"  {PURPLE}{log.get('agent',''):<20}{RESET}  "
                f"{DIM}{log.get('tool_name',''):<26}{RESET}  "
                f"{dur:>8}  {hash_ok}{spoliation}"
            )
            if log.get("result_summary"):
                _print(f"  {DIM}  └─ {log['result_summary']}{RESET}")

    _print(f"\n  {'═' * 56}\n")


# ── Commands ─────────────────────────────────────────────────────────────────

async def do_status():
    from backend.database import list_investigations, init_db
    import aiosqlite
    env = _load_env()

    _section("System Status")
    docker_ok = bool(subprocess.run(
        ["docker", "images", "fossick-mcp", "-q"],
        capture_output=True, text=True).stdout.strip())
    _print(f"  Docker image:   fossick-mcp {GREEN + '✓' + RESET if docker_ok else RED + '✗ run: docker build -t fossick-mcp -f docker/Dockerfile .' + RESET}")

    api_key = env.get("ANTHROPIC_API_KEY", "")
    _print(f"  Anthropic API:  {GREEN + '✓ configured' + RESET if len(api_key) > 20 and api_key.startswith('sk-') else RED + '✗ add ANTHROPIC_API_KEY to .env' + RESET}")

    slack = env.get("SLACK_WEBHOOK_URL", "")
    _print(f"  Slack webhook:  {GREEN + '✓ configured' + RESET if slack else YELLOW + '⚠ not configured (optional)' + RESET}")

    case_path = Path(env.get("CASE_DATA_PATH",
                              str(Path(__file__).parent / "case_data")))
    images = (list(case_path.glob("*.E01")) + list(case_path.glob("*.E0[2-9]")) +
              list(case_path.glob("*.vmem")) + list(case_path.glob("*.mem")) +
              list(case_path.glob("*.raw")))
    _print(f"  Case data:      {case_path} — {len(images)} image(s)")
    for img in sorted(set(i.stem for i in images))[:5]:
        files = list(case_path.glob(f"{img}.*"))
        total = sum(f.stat().st_size for f in files) / (1024**2)
        _print(f"    {DIM}└─ {img}  ({total:.0f} MB){RESET}")

    try:
        from backend.config import settings
        async with aiosqlite.connect(settings.db_path) as db:
            await init_db(db)
            invs = await list_investigations(db)
        _print(f"  Investigations: {len(invs)} in database")
    except Exception:
        _print(f"  Investigations: {DIM}no database yet{RESET}")
    _print()


async def do_list():
    from backend.database import list_investigations, init_db
    from backend.config import settings
    import aiosqlite

    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        investigations = await list_investigations(db)

    if not investigations:
        _print(f"\n  {DIM}No investigations yet.{RESET}")
        _print(f"  {DIM}Try: analyze case_data/disk.E01{RESET}\n")
        return

    _print(f"\n  {BOLD}{'ID':10} {'Case':22} {'Status':14} {'Contradictions':16} {'Started'}{RESET}")
    _print(f"  {'─'*10} {'─'*22} {'─'*14} {'─'*16} {'─'*18}")
    for inv in investigations:
        status = inv.get("status", "")
        s_str  = (f"{GREEN}done{RESET}"    if status == "completed" else
                  f"{BLUE}running{RESET}"  if status == "running"   else
                  f"{RED}failed{RESET}")
        contra = inv.get("contradictions_detected", 0)
        c_str  = f"{YELLOW}⚡ {contra}{RESET}" if contra else f"{DIM}─{RESET}"
        _print(
            f"  {DIM}{inv['id'][:8]}…{RESET}  "
            f"{inv['case_id']:<22}  {s_str:<24}  {c_str:<26}  "
            f"{inv.get('started_at','')[:16]}"
        )
    _print()


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
            _err(f"Investigation not found: {investigation_id}")
            _print(f"  {DIM}Use 'list' to see available investigations{RESET}")
            return
        report = await get_investigation(db, matched[0]["id"])

    print_report(report)


async def do_analyze(image_path: str, case_id: str | None, output: str):
    from backend.investigation import run_investigation

    # Resolve path
    p = Path(image_path)
    if not p.exists():
        from backend.config import settings
        alt = Path(settings.case_data_path) / p.name
        if alt.exists():
            image_path = str(alt)
            _print(f"  {DIM}Resolved: {image_path}{RESET}")
        else:
            _warn(f"Image not found: {image_path} — running in demo mode")

    _print(f"\n  {BOLD}Starting investigation{RESET}")
    _print(f"  Image:   {CYAN}{image_path}{RESET}")
    _print(f"  Case ID: {case_id or 'auto-generated'}\n")
    _print(f"  Spawning 4 agents in parallel:")
    _print(f"  {BLUE}  [1] Timeline Agent    {DIM}Plaso — filesystem, events, LNK, USB{RESET}")
    _print(f"  {RED}  [2] Memory Agent      {DIM}Volatility3 — processes, injections, network{RESET}")
    _print(f"  {ORANGE}  [3] Persistence Agent {DIM}AmCache, Prefetch, Registry, Tasks{RESET}")
    _print(f"  {PURPLE}  [4] Verifier Agent    {DIM}cross-reference, contradiction detection{RESET}")
    _print(f"\n  {DIM}Running... (this may take several minutes for real images){RESET}\n")

    start  = datetime.utcnow()
    report = await run_investigation(image_path=image_path, case_id=case_id)
    elapsed = (datetime.utcnow() - start).total_seconds()

    _print(f"  {GREEN}✓ Complete{RESET} in {elapsed:.1f}s  |  "
           f"{len(report.findings)} findings  |  "
           f"{report.contradictions_detected} contradictions")

    if output == "json":
        _print(json.dumps(report.model_dump(), indent=2, default=str))
    else:
        print_report(report.model_dump())


# ── REPL ─────────────────────────────────────────────────────────────────────

def parse_line(line: str) -> tuple[str, list[str]]:
    """Parse a command line into (command, args_list)."""
    parts = line.strip().split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


def get_prompt() -> str:
    return f"{BOLD}{BLUE}fossick{RESET} {GRAY}❯{RESET} "


async def repl():
    print(BANNER)
    _print(f"  Type {CYAN}help{RESET} for available commands. "
           f"Press {BOLD}Ctrl+C{RESET} or type {CYAN}exit{RESET} to quit.\n")

    # Setup readline for history and tab completion
    commands = ["analyze", "list", "report", "status", "help", "clear", "exit", "quit"]
    def completer(text, state):
        options = [c for c in commands if c.startswith(text)]
        return options[state] if state < len(options) else None
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")

    history_file = Path.home() / ".fossick_history"
    try:
        readline.read_history_file(str(history_file))
    except FileNotFoundError:
        pass

    try:
        while True:
            try:
                line = input(get_prompt()).strip()
            except EOFError:
                _print(f"\n  {DIM}Goodbye.{RESET}\n")
                break

            if not line:
                continue

            cmd, args = parse_line(line)

            if cmd in ("exit", "quit"):
                _print(f"\n  {DIM}Goodbye.{RESET}\n")
                break

            elif cmd == "help":
                _print(HELP_TEXT)

            elif cmd == "clear":
                os.system("clear")
                _print(BANNER)

            elif cmd == "status":
                await do_status()

            elif cmd == "list":
                await do_list()

            elif cmd == "report":
                if not args:
                    _err("Usage: report <investigation_id>")
                    _print(f"  {DIM}Example: report abc12345{RESET}")
                else:
                    await do_report(args[0])

            elif cmd == "analyze":
                if not args:
                    _err("Usage: analyze <image_path> [--case-id <id>] [--output json|table]")
                    _print(f"  {DIM}Example: analyze case_data/disk.E01 --case-id incident-001{RESET}")
                    continue

                # Parse inline args
                image_path = args[0]
                case_id    = None
                output     = "table"
                i = 1
                while i < len(args):
                    if args[i] == "--case-id" and i + 1 < len(args):
                        case_id = args[i + 1]; i += 2
                    elif args[i] == "--output" and i + 1 < len(args):
                        output = args[i + 1]; i += 2
                    else:
                        i += 1

                await do_analyze(image_path, case_id, output)

            else:
                _err(f"Unknown command: {cmd}")
                _print(f"  {DIM}Type 'help' to see available commands{RESET}")

    except KeyboardInterrupt:
        _print(f"\n\n  {DIM}Interrupted. Goodbye.{RESET}\n")
    finally:
        try:
            readline.write_history_file(str(history_file))
        except Exception:
            pass


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    # If called with arguments, run single command and exit (non-interactive)
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

        sub.add_parser("status")

        args = parser.parse_args()

        if args.command == "analyze":
            asyncio.run(do_analyze(args.image_path, args.case_id, args.output))
        elif args.command == "list":
            asyncio.run(do_list())
        elif args.command == "report":
            asyncio.run(do_report(args.investigation_id))
        elif args.command == "status":
            asyncio.run(do_status())
        else:
            parser.print_help()
    else:
        # No arguments — launch interactive REPL
        asyncio.run(repl())


if __name__ == "__main__":
    main()
