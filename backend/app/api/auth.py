from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import require_admin
from app.models import AuditLog
from app.schemas import LoginRequest
from app.services.security import (
    create_access_token,
    enforce_rate_limit,
    verify_admin_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def audit(db: Session, action: str, actor: str, outcome: str, details: dict | None = None) -> None:
    db.add(
        AuditLog(
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            action=action,
            actor=actor[:80],
            outcome=outcome,
            details=details,
        )
    )
    db.commit()


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    enforce_rate_limit(request, "login", settings.login_rate_limit_per_minute)
    valid = payload.username == settings.admin_username and verify_admin_password(payload.password)
    if not valid:
        audit(db, "login", payload.username, "denied")
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(settings.admin_username)
    is_secure = settings.is_production or request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    audit(db, "login", settings.admin_username, "success")
    return {"authenticated": True, "username": settings.admin_username}


@router.post("/logout")
def logout(
    response: Response,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    response.delete_cookie("access_token", path="/")
    audit(db, "logout", admin, "success")
    return {"authenticated": False}


@router.get("/session")
def session(admin: str = Depends(require_admin)) -> dict:
    return {"authenticated": True, "username": admin}
