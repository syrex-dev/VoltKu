from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db
from app.mqtt_ingest import ingest_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    init_db()
    ingest_service.start_worker()
    ingest_service.start_mqtt()
    yield
    # Shutdown
    ingest_service.stop_mqtt()
    ingest_service.stop_worker()


app = FastAPI(
    title=settings.app_name,
    description="Backend API Monitor Listrik Pintar (IoT + AI)",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/healthz")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
