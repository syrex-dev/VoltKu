from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.auth import create_access_token, login_limiter, verify_password

router = APIRouter(prefix="/api", tags=["Auth"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, response: Response):
    """Endpoint login dashboard dengan proteksi brute-force backoff."""
    is_limited, retry_after = login_limiter.check_rate_limit()
    if is_limited:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        response.headers["Retry-After"] = str(retry_after)
        msg = "Too many failed attempts. Please retry later."
        return Response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content=f'{{"error":{{"code":429,"message":"{msg}"}}}}',
            media_type="application/json",
        )

    if not verify_password(req.password):
        delay = login_limiter.record_failure()
        headers = {"Retry-After": str(delay)} if delay > 0 else {}
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
            content='{"error":{"code":401,"message":"Invalid password"}}',
            media_type="application/json",
        )

    login_limiter.record_success()
    token = create_access_token(subject="dashboard_admin")
    return {"token": token, "token_type": "bearer"}
