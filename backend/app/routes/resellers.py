from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from app.db import db
from app.schemas import ResellerIn, ResetPasswordIn, UserIn, UserUpdate
from app.security import hash_password, require_admin
from app.utils import audit, normalize_phone, now_utc, ser, to_oid

router = APIRouter(prefix="/api/resellers", tags=["resellers"])
users_router = APIRouter(prefix="/api/users", tags=["users"])


def new_user_doc(email: str, name: str, role: str, password: str, reseller_id=None, must_change=True) -> dict:
    return {"email": email.lower(), "name": name, "role": role, "reseller_id": reseller_id,
            "password_hash": hash_password(password), "is_active": True, "must_change_password": must_change,
            "token_version": 0, "created_at": now_utc()}


@router.get("")
async def list_resellers(user: dict = Depends(require_admin)):
    docs = await db.resellers.find().sort("name", 1).to_list(5000)
    users = await db.users.find({"role": "reseller"}, {"email": 1, "reseller_id": 1, "is_active": 1}).to_list(10000)
    stats = {s["_id"]: s async for s in db.orders.aggregate([
        {"$group": {"_id": "$reseller_id", "orders": {"$sum": 1}, "total": {"$sum": "$grand_total"}, "paid": {"$sum": "$total_paid"}}}])}
    out = []
    for r in docs:
        d = ser(r)
        d["users"] = [ser(u) for u in users if u.get("reseller_id") == r["_id"]]
        s = stats.get(r["_id"], {})
        d.update(order_count=s.get("orders", 0), total_order=s.get("total", 0), total_paid=s.get("paid", 0))
        out.append(d)
    return out


@router.get("/{reseller_id}")
async def get_reseller(reseller_id: str, user: dict = Depends(require_admin)):
    r = await db.resellers.find_one({"_id": to_oid(reseller_id, "Reseller")})
    if not r:
        raise HTTPException(status_code=404, detail="Reseller tidak ditemukan.")
    return ser(r)


@router.post("")
async def create_reseller(body: ResellerIn, user: dict = Depends(require_admin)):
    wa = normalize_phone(body.wa)
    if len(wa) < 10:
        raise HTTPException(status_code=422, detail="Nomor WhatsApp tidak valid.")
    if bool(body.login_email) != bool(body.login_password):
        raise HTTPException(status_code=422, detail="Isi email dan password login secara lengkap, atau kosongkan keduanya.")
    if body.login_email and await db.users.find_one({"email": body.login_email.lower()}):
        raise HTTPException(status_code=409, detail="Email login sudah digunakan.")
    now = now_utc()
    doc = {"name": body.name.strip(), "wa": body.wa.strip(), "wa_normalized": wa, "address": body.address.strip(),
           "is_special": body.is_special, "notes": body.notes, "created_at": now, "updated_at": now}
    res = await db.resellers.insert_one(doc)
    if body.login_email:
        await db.users.insert_one(new_user_doc(body.login_email, doc["name"], "reseller", body.login_password, res.inserted_id))
    await audit(db, user, "tambah_reseller", "resellers", res.inserted_id, {"name": doc["name"], "is_special": body.is_special})
    return ser(await db.resellers.find_one({"_id": res.inserted_id}))


@router.put("/{reseller_id}")
async def update_reseller(reseller_id: str, body: ResellerIn, user: dict = Depends(require_admin)):
    oid = to_oid(reseller_id, "Reseller")
    old = await db.resellers.find_one({"_id": oid})
    if not old:
        raise HTTPException(status_code=404, detail="Reseller tidak ditemukan.")
    wa = normalize_phone(body.wa)
    if len(wa) < 10:
        raise HTTPException(status_code=422, detail="Nomor WhatsApp tidak valid.")
    data = {"name": body.name.strip(), "wa": body.wa.strip(), "wa_normalized": wa, "address": body.address.strip(),
            "is_special": body.is_special, "notes": body.notes, "updated_at": now_utc()}
    await db.resellers.update_one({"_id": oid}, {"$set": data})
    changes = {k: {"old": old.get(k), "new": data[k]} for k in ("name", "wa", "is_special") if old.get(k) != data[k]}
    if changes:
        await audit(db, user, "ubah_reseller", "resellers", oid, changes)
    return ser(await db.resellers.find_one({"_id": oid}))


@users_router.get("")
async def list_users(user: dict = Depends(require_admin)):
    docs = await db.users.find().sort("created_at", -1).to_list(10000)
    rmap = {r["_id"]: r["name"] async for r in db.resellers.find({}, {"name": 1})}
    out = []
    for u in docs:
        d = ser(u)
        d["reseller_name"] = rmap.get(u.get("reseller_id"))
        out.append(d)
    return out


@users_router.post("")
async def create_user(body: UserIn, user: dict = Depends(require_admin)):
    rid = None
    if body.role == "reseller":
        if not body.reseller_id:
            raise HTTPException(status_code=422, detail="Pilih reseller untuk akun reseller.")
        rid = to_oid(body.reseller_id, "Reseller")
        if not await db.resellers.find_one({"_id": rid}):
            raise HTTPException(status_code=404, detail="Reseller tidak ditemukan.")
    try:
        res = await db.users.insert_one(new_user_doc(body.email, body.name, body.role, body.password, rid, body.must_change_password))
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Email sudah digunakan.")
    await audit(db, user, "tambah_user", "users", res.inserted_id, {"email": body.email, "role": body.role})
    return ser(await db.users.find_one({"_id": res.inserted_id}))


@users_router.patch("/{user_id}")
async def update_user(user_id: str, body: UserUpdate, user: dict = Depends(require_admin)):
    oid = to_oid(user_id, "User")
    target = await db.users.find_one({"_id": oid})
    if not target:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    upd: dict = {}
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.is_active is not None:
        if oid == user["_id"] and not body.is_active:
            raise HTTPException(status_code=422, detail="Anda tidak dapat menonaktifkan akun sendiri.")
        if target.get("is_super_admin") and not body.is_active:
            raise HTTPException(status_code=403, detail="Akun Super Admin tidak dapat dinonaktifkan.")
        upd["is_active"] = body.is_active
    if body.reseller_id is not None and target["role"] == "reseller":
        upd["reseller_id"] = to_oid(body.reseller_id, "Reseller")
    inc = {"token_version": 1} if body.is_active is False else {}
    await db.users.update_one({"_id": oid}, {"$set": upd, **({"$inc": inc} if inc else {})})
    await audit(db, user, "ubah_user", "users", oid, {k: str(v) for k, v in upd.items()})
    return ser(await db.users.find_one({"_id": oid}))


@users_router.post("/{user_id}/reset-password")
async def reset_password(user_id: str, body: ResetPasswordIn, user: dict = Depends(require_admin)):
    oid = to_oid(user_id, "User")
    target = await db.users.find_one({"_id": oid}, {"email": 1, "is_super_admin": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    if target.get("is_super_admin") and oid != user["_id"]:
        raise HTTPException(status_code=403, detail="Password Super Admin hanya dapat diubah oleh pemiliknya.")
    res = await db.users.update_one({"_id": oid}, {"$set": {
        "password_hash": hash_password(body.new_password), "must_change_password": body.must_change_password},
        "$inc": {"token_version": 1}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    await db.login_attempts.delete_one({"identifier": f"email:{target['email']}"})
    await audit(db, user, "reset_password", "users", oid)
    return {"ok": True}
