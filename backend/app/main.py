from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Backend API Monitor Listrik Pintar (IoT + AI)",
    version="0.1.0",
)


@app.get("/healthz")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

