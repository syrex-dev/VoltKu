from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import (
    create_access_token,
    get_trusted_client_ip,
    login_limiter,
    verify_password,
)

router = APIRouter(prefix="/api", tags=["Auth"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request):
    """Endpoint login dashboard dengan proteksi brute-force backoff per IP."""
    client_ip = get_trusted_client_ip(request)
    is_limited, retry_after = login_limiter.check_rate_limit(client_ip)
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": 429,
                    "message": "Too many failed attempts. Please retry later.",
                }
            },
        )

    if not verify_password(req.password):
        delay = login_limiter.record_failure(client_ip)
        headers = {"Retry-After": str(delay)} if delay > 0 else {}
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
            content={"error": {"code": 401, "message": "Invalid password"}},
        )

    login_limiter.record_success(client_ip)
    token = create_access_token(subject="dashboard_admin")
    return {"token": token, "token_type": "bearer"}
