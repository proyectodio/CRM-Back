from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.db.session import engine

app = FastAPI(
    title="DIO CRM",
    version="0.1.0",
    description="API de DIO CRM. Cada empresa solo consulta y modifica sus propios datos.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", tags=["health"])
def root() -> dict:
    return {
        "name": "DIO",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1",
    }


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db", tags=["health"])
def health_db() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return {"status": "error", "detail": str(exc.__class__.__name__)}
    return {"status": "ok"}
