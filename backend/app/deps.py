import logging

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=True)
logger = logging.getLogger("app.auth")


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        logger.warning(
            "Auth failed: access token expired. method=%s path=%s token_prefix=%s",
            request.method,
            request.url.path,
            token[:12],
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "Auth failed: invalid access token (%s). method=%s path=%s token_prefix=%s",
            type(exc).__name__,
            request.method,
            request.url.path,
            token[:12],
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(
            "Auth failed: user not found. method=%s path=%s user_id=%s token_prefix=%s",
            request.method,
            request.url.path,
            user_id,
            token[:12],
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def verify_dify_import_api_key(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> None:
    if x_api_key != settings.dify_import_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
