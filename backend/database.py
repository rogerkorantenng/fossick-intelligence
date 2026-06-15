import json
import aiosqlite
from backend.models import InvestigationReport
from backend.config import settings


async def init_db(db: aiosqlite.Connection) -> None:
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS investigations (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            image_path TEXT NOT NULL,
            image_sha256 TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            findings TEXT NOT NULL DEFAULT '[]',
            contradictions_detected INTEGER DEFAULT 0,
            contradictions_resolved INTEGER DEFAULT 0,
            execution_log TEXT NOT NULL DEFAULT '[]',
            agent_messages TEXT NOT NULL DEFAULT '[]',
            self_corrections_applied INTEGER DEFAULT 0,
            evidence_integrity_verified INTEGER DEFAULT 0,
            error TEXT
        )
    """)
    # Add new columns if they don't exist yet (safe on existing DBs)
    for col, definition in [
        ("agent_messages", "TEXT NOT NULL DEFAULT '[]'"),
        ("self_corrections_applied", "INTEGER DEFAULT 0"),
        ("accuracy_assessment", "TEXT"),
    ]:
        try:
            await db.execute(f"ALTER TABLE investigations ADD COLUMN {col} {definition}")
            await db.commit()
        except Exception:
            pass  # column already exists


async def save_investigation(db: aiosqlite.Connection, report: InvestigationReport) -> None:
    await db.execute(
        """INSERT OR REPLACE INTO investigations
           (id, case_id, image_path, image_sha256, status, started_at, completed_at,
            findings, contradictions_detected, contradictions_resolved,
            execution_log, agent_messages, self_corrections_applied,
            evidence_integrity_verified, accuracy_assessment, error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (report.id, report.case_id, report.image_path, report.image_sha256,
         report.status, report.started_at.isoformat(),
         report.completed_at.isoformat() if report.completed_at else None,
         json.dumps([f.model_dump() for f in report.findings], default=str),
         report.contradictions_detected, report.contradictions_resolved,
         json.dumps([l.model_dump() for l in report.execution_log], default=str),
         json.dumps([m.model_dump() for m in report.agent_messages], default=str),
         report.self_corrections_applied,
         int(report.evidence_integrity_verified),
         json.dumps(report.accuracy_assessment.model_dump()) if report.accuracy_assessment else None,
         report.error),
    )
    await db.commit()


async def get_investigation(db: aiosqlite.Connection, investigation_id: str) -> dict | None:
    async with db.execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,)) as cur:
        row = await cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        result = dict(zip(cols, row))
        result["findings"] = json.loads(result["findings"])
        result["execution_log"] = json.loads(result["execution_log"])
        result["agent_messages"] = json.loads(result.get("agent_messages") or "[]")
        result["accuracy_assessment"] = json.loads(result["accuracy_assessment"]) if result.get("accuracy_assessment") else None
        return result


async def list_investigations(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        "SELECT id, case_id, image_path, status, started_at, completed_at, contradictions_detected FROM investigations ORDER BY started_at DESC"
    ) as cur:
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]
