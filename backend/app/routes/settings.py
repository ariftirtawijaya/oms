from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.db import db
from app.security import client_ip, require_admin, require_super_admin, verify_password
from app.services import cleanup
from app.services.storage import branding_path, save_branding_image
from app.utils import audit, now_utc, ser

router = APIRouter(prefix="/api", tags=["settings"])

BRAND_ID = "branding"
DEFAULT_BRANDING = {"app_name": "RelayLab OMS", "tagline": "Autolight Order System", "logo_file": None, "favicon_file": None}


async def get_branding() -> dict:
    doc = await db.system_settings.find_one({"_id": BRAND_ID}) or {}
    out = {k: doc.get(k, v) for k, v in DEFAULT_BRANDING.items()}
    out["updated_at"] = ser(doc.get("updated_at"))
    return out


def _remove_files(*names: Optional[str]):
    for n in names:
        if n:
            branding_path(n).unlink(missing_ok=True)


@router.get("/branding")
async def read_branding():
    return await get_branding()


@router.get("/branding/files/{filename}")
async def branding_file(filename: str):
    p = branding_path(filename)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    return FileResponse(p, headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"})


@router.put("/settings/branding")
async def update_branding(app_name: str = Form(...), tagline: str = Form(""), remove_logo: bool = Form(False),
                          remove_favicon: bool = Form(False), logo: Optional[UploadFile] = File(None),
                          favicon: Optional[UploadFile] = File(None), user: dict = Depends(require_admin)):
    app_name, tagline = app_name.strip(), tagline.strip()
    if not 2 <= len(app_name) <= 60:
        raise HTTPException(status_code=422, detail="Nama aplikasi harus 2–60 karakter.")
    if len(tagline) > 80:
        raise HTTPException(status_code=422, detail="Subtitle maksimal 80 karakter.")
    old = await get_branding()
    new_logo = await save_branding_image(logo, "logo") if logo and logo.filename else None
    try:
        new_fav = await save_branding_image(favicon, "favicon") if favicon and favicon.filename else None
    except HTTPException:
        _remove_files(new_logo)
        raise
    logo_file = new_logo or (None if remove_logo else old["logo_file"])
    fav_file = new_fav or (None if remove_favicon else old["favicon_file"])
    await db.system_settings.update_one({"_id": BRAND_ID}, {"$set": {
        "app_name": app_name, "tagline": tagline, "logo_file": logo_file, "favicon_file": fav_file,
        "updated_at": now_utc(), "updated_by": user["_id"]}}, upsert=True)
    _remove_files(*(f for f in (old["logo_file"], old["favicon_file"]) if f not in (logo_file, fav_file)))
    await audit(db, user, "branding_update", "system_settings", BRAND_ID, {"app_name": app_name, "tagline": tagline})
    return await get_branding()


@router.post("/settings/branding/reset")
async def reset_branding(user: dict = Depends(require_admin)):
    old = await get_branding()
    await db.system_settings.update_one({"_id": BRAND_ID}, {"$set": {**DEFAULT_BRANDING, "updated_at": now_utc(),
                                                                       "updated_by": user["_id"]}}, upsert=True)
    _remove_files(old["logo_file"], old["favicon_file"])
    await audit(db, user, "branding_reset", "system_settings", BRAND_ID)
    return await get_branding()


class CleanupPreviewIn(BaseModel):
    categories: List[str] = Field(min_length=1)
    reset_order_seq: bool = False


class CleanupExecuteIn(CleanupPreviewIn):
    confirm_text: str
    password: str = Field(min_length=1, max_length=200)


@router.post("/settings/cleanup/preview")
async def cleanup_preview(body: CleanupPreviewIn, user: dict = Depends(require_super_admin)):
    return await cleanup.preview(db, body.categories, body.reset_order_seq)


@router.post("/settings/cleanup/execute")
async def cleanup_execute(body: CleanupExecuteIn, request: Request, user: dict = Depends(require_super_admin)):
    cats = cleanup.normalize(body.categories)
    ip = client_ip(request)
    if body.confirm_text.strip() != cleanup.CONFIRM_TEXT:
        raise HTTPException(status_code=422, detail=f"Ketik {cleanup.CONFIRM_TEXT} dengan benar untuk melanjutkan.")
    if not verify_password(body.password, user["password_hash"]):
        await db.security_logs.insert_one({"action": "pembersihan_data", "actor_id": user["_id"], "actor_name": user.get("name"),
                                           "actor_email": user.get("email"), "ip": ip, "categories": cats,
                                           "result": "ditolak_password_salah", "created_at": now_utc()})
        raise HTTPException(status_code=403, detail="Password Super Admin salah. Pembersihan dibatalkan.")
    return await cleanup.execute(db, user, ip, cats, body.reset_order_seq)


@router.get("/settings/cleanup/history")
async def cleanup_history(user: dict = Depends(require_super_admin)):
    docs = await db.security_logs.find({"action": "pembersihan_data"}).sort("created_at", -1).limit(50).to_list(50)
    return [ser(d) for d in docs]
