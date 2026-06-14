import aiosqlite
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from backend.database import get_investigation, list_investigations, init_db
from backend.investigation import run_investigation
from backend.config import settings

router = APIRouter()


class InvestigateRequest(BaseModel):
    image_path: str
    case_id: str | None = None


@router.post("/investigate")
async def start_investigation(req: InvestigateRequest, background_tasks: BackgroundTasks):
    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
    background_tasks.add_task(run_investigation, req.image_path, req.case_id)
    return {"status": "started", "image_path": req.image_path}


@router.post("/investigate/sync")
async def investigate_sync(req: InvestigateRequest):
    report = await run_investigation(req.image_path, req.case_id)
    return report.model_dump()


@router.get("/investigations")
async def list_all():
    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
        return await list_investigations(db)


@router.get("/investigations/{investigation_id}")
async def get_one(investigation_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        result = await get_investigation(db, investigation_id)
        if not result:
            raise HTTPException(status_code=404, detail="Investigation not found")
        return result
