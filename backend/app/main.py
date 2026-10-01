"""RehabX AI — FastAPI application entrypoint."""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

# Ensure the repo root is importable so `rehabilitation` resolves even if
# the package is not pip-installed.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.api import admin, analysis, auth, dashboard, exercises, tracking, uploads  # noqa: E402

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RehabX AI",
    description=(
        "AI-assisted hand/wrist X-ray analysis and rehabilitation guidance. "
        "Research/prototype system — not a medical device, does not diagnose."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (auth.router, uploads.router, analysis.router, exercises.router, tracking.router, dashboard.router, admin.router):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(_: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=500, content={"detail": "Database error occurred"})
