import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import api_burst_limiter, get_trusted_client_ip
from app.config import get_settings, validate_startup_credentials
from app.db import init_db
from app.mqtt_ingest import ingest_service
from app.routers import admin, anomalies, auth, devices, public, users
from app.routers import settings as settings_router
from app.services.bot import init_and_start_bot, stop_bot
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_path = request.url.path
        if settings.app_env != "test" and req_path.startswith("/api/"):
            client_ip = get_trusted_client_ip(request)
            limited, retry_after = api_burst_limiter.check_and_record(client_ip)
            if limited:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": 429,
                            "message": "Terlalu banyak permintaan. Coba beberapa saat lagi.",
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' data: blob:; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com; "
            "style-src 'self' 'unsafe-inline' "
            "https://fonts.googleapis.com https://accounts.google.com; "
            "frame-src 'self' https://accounts.google.com; "
            "connect-src 'self' http: https: ws: wss:; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").lower()
        if proto == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        if req_path in (
            "/",
            "/index.html",
            "/sw.js",
            "/manifest.webmanifest",
            "/reset-password",
            "/admin",
            "/admin/manifest.webmanifest",
        ) or req_path.startswith("/admin/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        elif req_path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Validasi ketat kredensial saat startup
    validate_startup_credentials(settings)

    # Inisialisasi Database
    init_db()

    # Jalankan background worker, MQTT client, scheduler, dan bot hanya jika bukan mode test
    if settings.app_env != "test":
        ingest_service.start_worker()
        ingest_service.start_mqtt()
        if settings.is_scheduler_active:
            start_scheduler()
        from app.services.notifier import setup_notifier

        setup_notifier(settings)
        if settings.is_bot_active and settings.telegram_bot_token:
            await init_and_start_bot()

    yield

    # Shutdown
    if settings.app_env != "test":
        if settings.is_bot_active:
            await stop_bot()
        if settings.is_scheduler_active:
            stop_scheduler()
        ingest_service.stop_mqtt()
        ingest_service.stop_worker()


_is_prod = settings.app_env == "production"
app = FastAPI(
    title=settings.app_name,
    description="Backend API VoltKu (IoT + AI)",
    version="0.2.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

# Pasang Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# Pasang CORS Middleware hanya untuk origin tepercaya (konfigurasi di ALLOWED_CORS_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


# Standardize error format to {"error": {"code": ..., "message": ...}}
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    headers = exc.headers or {}
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=headers)
    message = str(exc.detail) if exc.detail else "An error occurred"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": message}},
        headers=headers,
    )


# Registrasi Endpoint API
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(public.router)
app.include_router(public.payment_router)
app.include_router(admin.auth_router)
app.include_router(admin.router)
app.include_router(devices.router)
app.include_router(settings_router.router)
app.include_router(anomalies.router)


@app.get("/healthz", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint publik."""
    return {"status": "ok"}


@app.get("/admin/manifest.webmanifest", include_in_schema=False)
async def get_admin_pwa_manifest():
    """Manifest PWA terpisah khusus Portal Admin (/admin), terinspirasi DigiPoint."""
    return JSONResponse(
        content={
            "id": "/admin",
            "name": "VoltKu - Admin",
            "short_name": "VoltKu Admin",
            "description": "Portal Pengelolaan Tenant, Perangkat IoT, dan Sistem",
            "start_url": "/admin",
            "scope": "/admin",
            "display": "standalone",
            "orientation": "portrait-primary",
            "background_color": "#f4f6f9",
            "theme_color": "#ffffff",
            "categories": ["business", "utilities"],
            "icons": [
                {"src": "/pwa-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": "/pwa-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {
                    "src": "/pwa-512-maskable.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        media_type="application/manifest+json",
    )


# Mount Dashboard Web UI
dashboard_path = None
candidates = [
    Path("/app/dashboard"),
    Path(__file__).resolve().parent.parent.parent / "dashboard",
    Path("dashboard").resolve(),
]
for p in candidates:
    if p.exists() and p.is_dir():
        dashboard_path = p
        break

if dashboard_path:
    @app.get("/reset-password", include_in_schema=False)
    async def serve_reset_password_spa():
        return FileResponse(dashboard_path / "index.html")

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{subpath:path}", include_in_schema=False)
    async def serve_admin_spa(subpath: str = ""):
        return FileResponse(dashboard_path / "index.html")

    app.mount("/", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")
