import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.db import db
from app.schemas import ChangePasswordIn, LoginIn, ProfileIn
from app.security import (clear_auth_cookies, client_ip, get_current_user, hash_password,
                          require_reseller, set_auth_cookies, user_from_token, verify_password)
from app.utils import audit, now_utc, ser

router = APIRouter(prefix="/api/auth", tags=["auth"])
me_router = APIRouter(prefix="/api/me", tags=["me"])

MAX_FAILS = 5
LOCK_MINUTES = 15
_ip_hits: dict = defaultdict(deque)


def ip_rate_limit(ip: str, limit: int = 30, window: int = 300):
    q = _ip_hits[ip]
    t = time.time()
    while q and q[0] < t - window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan login dari jaringan anda. Coba lagi beberapa menit lagi.")
    q.append(t)


def reseller_public(r: dict) -> dict:
    out = ser(r)
    out["min_qty"] = 1 if r.get("is_special") else 10
    out.pop("is_special", None)
    out.pop("notes", None)
    return out


async def user_payload(user: dict) -> dict:
    out = ser(user)
    if user.get("reseller_id"):
        r = await db.resellers.find_one({"_id": user["reseller_id"]})
        out["reseller"] = reseller_public(r) if r else None
    return out


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    ip = client_ip(request)
    ip_rate_limit(ip)
    email = body.email.lower()
    ident = f"email:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until") and att["locked_until"] > now_utc():
        mins = int((att["locked_until"] - now_utc()).total_seconds() // 60) + 1
        raise HTTPException(status_code=429, detail=f"Akun dikunci sementara karena terlalu banyak percobaan gagal. Coba lagi dalam {mins} menit.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        fails = (att.get("count", 0) if att else 0) + 1
        upd = {"count": fails, "last_at": now_utc(), "ip": ip}
        if fails >= MAX_FAILS:
            upd.update(locked_until=now_utc() + timedelta(minutes=LOCK_MINUTES), count=0)
        await db.login_attempts.update_one({"identifier": ident}, {"$set": upd}, upsert=True)
        raise HTTPException(status_code=401, detail="Email atau password salah.")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Akun anda dinonaktifkan. Hubungi admin RelayLab.")
    await db.login_attempts.delete_one({"identifier": ident})
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": now_utc()}})
    set_auth_cookies(response, user)
    return await user_payload(user)


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Sesi telah berakhir. Silakan login kembali.")
    user = await user_from_token(token, "refresh")
    set_auth_cookies(response, user)
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return await user_payload(user)


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, response: Response, user: dict = Depends(get_current_user)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=422, detail="Password saat ini salah.")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=422, detail="Password baru harus berbeda dari password saat ini.")
    tv = user.get("token_version", 0) + 1
    await db.users.update_one({"_id": user["_id"]}, {"$set": {
        "password_hash": hash_password(body.new_password), "must_change_password": False,
        "token_version": tv, "password_changed_at": now_utc()}})
    user["token_version"] = tv
    set_auth_cookies(response, user)
    await audit(db, user, "ubah_password", "users", user["_id"])
    return {"ok": True}


@me_router.get("/profile")
async def get_profile(user: dict = Depends(require_reseller)):
    r = await db.resellers.find_one({"_id": user["reseller_id"]})
    return reseller_public(r)


@me_router.put("/profile")
async def update_profile(body: ProfileIn, user: dict = Depends(require_reseller)):
    await db.resellers.update_one({"_id": user["reseller_id"]}, {"$set": {"address": body.address.strip(), "updated_at": now_utc()}})
    await audit(db, user, "ubah_profil", "resellers", user["reseller_id"], {"address": body.address})
    return reseller_public(await db.resellers.find_one({"_id": user["reseller_id"]}))
