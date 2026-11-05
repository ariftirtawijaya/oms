import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from bson import ObjectId
from fastapi import Depends, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app import config
from app.db import db
from app.utils import now_utc

ph = PasswordHasher()
ALGO = "HS256"
CSRF_EXEMPT = ("/api/auth/login", "/api/auth/refresh", "/api/auth/logout", "/api/webhooks/")


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_token(user: dict, kind: str) -> str:
    exp = now_utc() + (timedelta(minutes=config.ACCESS_TOKEN_MINUTES) if kind == "access" else timedelta(days=config.REFRESH_TOKEN_DAYS))
    payload = {"sub": str(user["_id"]), "type": kind, "tv": user.get("token_version", 0), "exp": exp}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=ALGO)


def set_auth_cookies(response: Response, user: dict):
    opts = dict(secure=config.COOKIE_SECURE, samesite="lax", path="/")
    response.set_cookie("access_token", create_token(user, "access"), httponly=True, max_age=config.ACCESS_TOKEN_MINUTES * 60, **opts)
    response.set_cookie("refresh_token", create_token(user, "refresh"), httponly=True, max_age=config.REFRESH_TOKEN_DAYS * 86400, **opts)
    response.set_cookie("csrf_token", secrets.token_urlsafe(32), httponly=False, max_age=config.REFRESH_TOKEN_DAYS * 86400, **opts)


def clear_auth_cookies(response: Response):
    for name in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(name, path="/")


async def user_from_token(token: str, kind: str) -> dict:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir. Silakan login kembali.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Sesi tidak valid.")
    if payload.get("type") != kind:
        raise HTTPException(status_code=401, detail="Sesi tidak valid.")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Akun tidak aktif atau tidak ditemukan.")
    if user.get("token_version", 0) != payload.get("tv", 0):
        raise HTTPException(status_code=401, detail="Sesi telah berakhir. Silakan login kembali.")
    return user


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    return await user_from_token(token, "access")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya admin yang dapat mengakses fitur ini.")
    return user


async def require_reseller(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "reseller" or not user.get("reseller_id"):
        raise HTTPException(status_code=403, detail="Fitur ini khusus akun reseller.")
    return user


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            request.method in ("POST", "PUT", "PATCH", "DELETE")
            and path.startswith("/api/")
            and not path.startswith(CSRF_EXEMPT)
            and request.cookies.get("access_token")
        ):
            cookie = request.cookies.get("csrf_token")
            header = request.headers.get("X-CSRF-Token")
            if not cookie or not header or not secrets.compare_digest(cookie, header):
                return JSONResponse(status_code=403, content={"detail": "Token keamanan (CSRF) tidak valid. Muat ulang halaman."})
        return await call_next(request)


def client_ip(request: Request) -> str:
    real = request.headers.get("X-Real-IP")
    if real:
        return real.strip()
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
