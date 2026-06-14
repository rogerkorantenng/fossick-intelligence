from contextlib import asynccontextmanager
import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.config import settings
from backend.routes.investigations import router as inv_router
from backend.routes.slack import router as slack_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with aiosqlite.connect(settings.db_path) as db:
        await init_db(db)
    yield


app = FastAPI(title="Fossick Intelligence — Autonomous DFIR", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inv_router)
app.include_router(slack_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Fossick Intelligence"}
