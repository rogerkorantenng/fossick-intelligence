#!/usr/bin/env python3.13
"""
Fossick — Autonomous DFIR Agent
Usage:
  fossick analyze <image_path> [--case-id <id>] [--output json|table]
  fossick list
  fossick report <investigation_id>
  fossick status
"""
import asyncio
import json
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from backend.config import settings
from backend.investigation import run_investigation
from backend.database import list_investigations, get_investigation, init_db
import aiosqlite

# ── ANSI colors ──────────────────────────────────────────────────────────────
RED     = "\033[91m"
ORANGE  = "\033[93m"
YELLOW  = "\033[33m"
GREEN   = "\033[92m"
BLUE    = "\033[94m"
PURPLE  = "\033[95m"
GRAY    = "\033[90m"
BOLD    = "\033[1m"
RESET   = "\033[0m"
DIM     = "\033[2m"

SEV_COLOR = {"critical": RED, "high": ORANGE, "medium": YELLOW, "low": GRAY}
CONF_COLOR = {"HIGH": RED, "MEDIUM": ORANGE, "LOW": YELLOW}

BANNER = f"""
{BOLD}{BLUE}╔═══════════════════════════════════════════════════╗
║  {RED}F O S S I C K{BLUE}  —  Autonomous DFIR Agent           ║
║  {DIM}Finds evil. Shows its work. Catches itself lying.{BLUE}  ║
╚═══════════════════════════════════════════════════╝{RESET}
"""


def print_banner():
    print(BANNER)


def format_finding(finding: dict, index: int) -> str:
    sev = finding.get("severity", "low")
    conf = finding.get("confidence", "LOW")
    color = SEV_COLOR.get(sev, GRAY)
    conf_color = CONF_COLOR.get(conf, GRAY)
    contradiction = " ⚡ CONTRADICTION" if finding.get("contradiction") else ""
    sources = " + ".join(finding.get("sources", []))

    lines = [
        f"\n{color}{BOLD}[{index}] {sev.upper()} — {finding.get('title', '')}{RESET}{contradiction}",
        f"    {finding.get('description', '')[:200]}",
        f"    {DIM}Confidence: {conf_color}{conf}{RESET}  {DIM}Sources: {sources}{RESET}",
    ]
    if finding.get("timestamp"):
        lines.append(f"    {DIM}Timestamp: {finding['timestamp']}{RESET}")
    if finding.get("tool_call_ids"):
        lines.append(f"    {DIM}Tool calls: {', '.join(finding['tool_call_ids'])}{RESET}")
    return "\n".join(lines)


def print_report(report: dict):
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  FOSSICK INVESTIGATION REPORT{RESET}")
    print(f"{'═' * 60}")
    print(f"  Case ID:    {BLUE}{report.get('case_id')}{RESET}")
    print(f"  Image:      {report.get('image_path')}")
    print(f"  SHA-256:    {DIM}{report.get('image_sha256', 'N/A')[:40]}...{RESET}")
    print(f"  Started:    {report.get('started_at', '')[:19]}")
    print(f"  Completed:  {report.get('completed_at', '')[:19]}")

    # Evidence integrity
    integrity = report.get("evidence_integrity_verified", True)
    integrity_str = f"{GREEN}✓ VERIFIED{RESET}" if integrity else f"{RED}⚠ VIOLATION DETECTED{RESET}"
    print(f"  Evidence:   {integrity_str}")
    print(f"{'─' * 60}")

    findings = report.get("findings", [])
    contradictions = [f for f in findings if f.get("contradiction")]
    regular = [f for f in findings if not f.get("contradiction")]

    # Stats
    by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in regular:
        by_sev[f.get("severity", "low")] = by_sev.get(f.get("severity", "low"), 0) + 1

    print(f"\n  {BOLD}SUMMARY{RESET}")
    print(f"  {RED}Critical: {by_sev['critical']}{RESET}  "
          f"{ORANGE}High: {by_sev['high']}{RESET}  "
          f"{YELLOW}Medium: {by_sev['medium']}{RESET}  "
          f"{GRAY}Low: {by_sev['low']}{RESET}")
    print(f"  Contradictions detected: {len(contradictions)}")
    print(f"  Total findings: {len(findings)}")

    # Contradictions first
    if contradictions:
        print(f"\n{BOLD}{YELLOW}  ⚡ CONTRADICTIONS ({len(contradictions)}){RESET}")
        for i, f in enumerate(contradictions, 1):
            print(format_finding(f, i))

    # Findings by severity
    if regular:
        print(f"\n{BOLD}  FINDINGS ({len(regular)}){RESET}")
        for sev in ["critical", "high", "medium", "low"]:
            sev_findings = [f for f in regular if f.get("severity") == sev]
            for f in sev_findings:
                print(format_finding(f, regular.index(f) + 1))

    # Agent execution log
    logs = report.get("execution_log", [])
    if logs:
        print(f"\n{BOLD}  AGENT EXECUTION LOG{RESET}")
        for log in logs:
            agent = log.get("agent", "")
            tool = log.get("tool_name", "")
            ms = log.get("duration_ms", 0)
            duration = f"{ms/1000:.1f}s" if ms > 1000 else f"{ms}ms"
            hash_ok = f"{GREEN}✓{RESET}" if log.get("hash_verified") else f"{DIM}—{RESET}"
            spoliation = f" {RED}⚠ SPOLIATION{RESET}" if log.get("spoliation_detected") else ""
            summary = log.get("result_summary", "")
            print(f"  {PURPLE}{agent:<20}{RESET} {DIM}{tool:<25}{RESET} {duration:>8}  {hash_ok}{spoliation}")
            if summary:
                print(f"  {DIM}  └─ {summary}{RESET}")

    print(f"\n{'═' * 60}\n")


async def cmd_analyze(image_path: str, case_id: str | None, output: str):
    print_banner()

    if not Path(image_path).exists():
        # Check if it's inside case_data
        alt = Path(settings.case_data_path) / Path(image_path).name
        if alt.exists():
            image_path = str(alt)
            print(f"{DIM}  Resolved to: {image_path}{RESET}")
        else:
            print(f"{YELLOW}  ⚠ Image not found: {image_path}{RESET}")
            print(f"{DIM}  Running in demo mode — agents will return empty findings{RESET}")

    print(f"{BOLD}  Analyzing:{RESET} {image_path}")
    print(f"{BOLD}  Case ID: {RESET}{case_id or 'auto'}")
    print(f"\n{DIM}  Spawning agents...{RESET}\n")

    # Progress indicators
    print(f"  {BLUE}[1/4]{RESET} Timeline Agent    {DIM}(Plaso — filesystem, events, LNK){RESET}")
    print(f"  {RED}[2/4]{RESET} Memory Agent      {DIM}(Volatility3 — processes, network, injections){RESET}")
    print(f"  {ORANGE}[3/4]{RESET} Persistence Agent {DIM}(AmCache, Prefetch, Registry){RESET}")
    print(f"  {PURPLE}[4/4]{RESET} Verifier Agent    {DIM}(cross-reference, contradiction detection){RESET}")
    print(f"\n  {DIM}Running in parallel...{RESET}\n")

    start = datetime.utcnow()
    report = await run_investigation(image_path=image_path, case_id=case_id)
    elapsed = (datetime.utcnow() - start).total_seconds()

    print(f"\n  {GREEN}✓ Complete{RESET} in {elapsed:.1f}s")

    if output == "json":
        print(json.dumps(report.model_dump(), indent=2, default=str))
    else:
        print_report(report.model_dump())

    return report


async def cmd_list():
    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        investigations = await list_investigations(db)

    if not investigations:
        print(f"\n{DIM}  No investigations yet. Run: fossick analyze <image_path>{RESET}\n")
        return

    print(f"\n{BOLD}  INVESTIGATIONS{RESET}\n")
    print(f"  {'ID':10} {'Case':20} {'Status':10} {'Findings':10} {'Started':20}")
    print(f"  {'─'*10} {'─'*20} {'─'*10} {'─'*10} {'─'*20}")

    for inv in investigations:
        status = inv.get("status", "")
        status_str = (f"{GREEN}done{RESET}" if status == "completed"
                      else f"{BLUE}running{RESET}" if status == "running"
                      else f"{RED}failed{RESET}")
        contradictions = inv.get("contradictions_detected", 0)
        contra_str = f" {YELLOW}⚡{contradictions}{RESET}" if contradictions > 0 else ""
        started = inv.get("started_at", "")[:16]
        print(f"  {DIM}{inv['id'][:8]}...{RESET}  {inv['case_id']:<20} {status_str:<20} {contra_str:<15} {started}")

    print()


async def cmd_report(investigation_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        # Support partial ID match
        investigations = await list_investigations(db)
        matched = [i for i in investigations if i["id"].startswith(investigation_id)]
        if not matched:
            print(f"{RED}  Investigation not found: {investigation_id}{RESET}")
            return
        full_id = matched[0]["id"]
        report = await get_investigation(db, full_id)

    if not report:
        print(f"{RED}  Investigation not found{RESET}")
        return

    print_report(report)


async def cmd_status():
    # Read .env directly to avoid pydantic-settings caching
    env_vars = {}
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    print_banner()
    print(f"  {BOLD}System Status{RESET}\n")

    # Check Docker
    import subprocess
    docker_ok = subprocess.run(["docker", "images", "fossick-mcp", "-q"],
                               capture_output=True, text=True).stdout.strip()
    print(f"  Docker image:  {'fossick-mcp ' + GREEN + '✓' + RESET if docker_ok else RED + '✗ not built' + RESET}")

    # Check Anthropic key
    api_key = env_vars.get("ANTHROPIC_API_KEY", "")
    key_ok = len(api_key) > 20 and api_key.startswith("sk-")
    print(f"  Anthropic API: {GREEN + '✓ configured' + RESET if key_ok else RED + '✗ not configured (.env)' + RESET}")

    # Check Slack
    slack_ok = bool(env_vars.get("SLACK_WEBHOOK_URL", ""))
    print(f"  Slack webhook: {GREEN + '✓ configured' + RESET if slack_ok else YELLOW + '⚠ not configured (optional)' + RESET}")

    # Check case_data
    case_path = Path(env_vars.get("CASE_DATA_PATH", "./case_data"))
    images = list(case_path.glob("*.E01")) + list(case_path.glob("*.vmem")) + \
             list(case_path.glob("*.mem")) + list(case_path.glob("*.raw"))
    print(f"  Case data:     {case_path} — {len(images)} image(s) found")
    for img in images[:5]:
        size = img.stat().st_size / (1024 ** 2)
        print(f"    {DIM}└─ {img.name} ({size:.0f} MB){RESET}")

    # DB stats
    try:
        async with aiosqlite.connect(settings.db_path) as db:
            await init_db(db)
            investigations = await list_investigations(db)
        print(f"  Investigations: {len(investigations)} in database")
    except Exception:
        print(f"  Investigations: {DIM}no database yet{RESET}")

    print()


def main():
    parser = argparse.ArgumentParser(
        prog="fossick",
        description="Fossick — Autonomous DFIR Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  fossick analyze /case_data/disk.E01
  fossick analyze disk.E01 --case-id incident-2026-001
  fossick analyze disk.E01 --output json > report.json
  fossick list
  fossick report abc12345
  fossick status
        """
    )
    subparsers = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze a forensic image")
    p_analyze.add_argument("image_path", help="Path to disk or memory image (.E01, .vmem, .mem)")
    p_analyze.add_argument("--case-id", default=None, help="Case identifier (auto-generated if not provided)")
    p_analyze.add_argument("--output", choices=["table", "json"], default="table")

    # list
    subparsers.add_parser("list", help="List all investigations")

    # report
    p_report = subparsers.add_parser("report", help="Show full report for an investigation")
    p_report.add_argument("investigation_id", help="Investigation ID or prefix")

    # status
    subparsers.add_parser("status", help="Show system status")

    args = parser.parse_args()

    if args.command == "analyze":
        asyncio.run(cmd_analyze(args.image_path, args.case_id, args.output))
    elif args.command == "list":
        asyncio.run(cmd_list())
    elif args.command == "report":
        asyncio.run(cmd_report(args.investigation_id))
    elif args.command == "status":
        asyncio.run(cmd_status())
    else:
        print_banner()
        parser.print_help()


if __name__ == "__main__":
    main()
