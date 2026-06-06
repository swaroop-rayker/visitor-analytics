from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.security import decode_access_token


def require_admin(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> str:
    del db
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    subject = decode_access_token(access_token)
    if subject != settings.admin_username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return subject

