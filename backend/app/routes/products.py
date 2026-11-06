from fastapi import APIRouter, Depends, HTTPException

from app.db import db
from app.schemas import ProductIn
from app.security import get_current_user, require_admin
from app.utils import audit, now_utc, ser, to_oid

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("")
async def list_products(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "admin" else {"is_active": True}
    proj = None if user["role"] == "admin" else {"price_history": 0, "notes": 0}
    docs = await db.products.find(q, proj).sort([("name", 1), ("voltage", 1)]).to_list(5000)
    return ser(docs)


@router.get("/{product_id}")
async def get_product(product_id: str, user: dict = Depends(require_admin)):
    p = await db.products.find_one({"_id": to_oid(product_id, "Produk")})
    if not p:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan.")
    return ser(p)


@router.post("")
async def create_product(body: ProductIn, user: dict = Depends(require_admin)):
    now = now_utc()
    doc = {**body.model_dump(), "price_history": [], "created_at": now, "updated_at": now}
    res = await db.products.insert_one(doc)
    await audit(db, user, "tambah_produk", "products", res.inserted_id, {"name": doc["name"], "voltage": doc["voltage"], "price": doc["price"]})
    return ser(await db.products.find_one({"_id": res.inserted_id}))


@router.put("/{product_id}")
async def update_product(product_id: str, body: ProductIn, user: dict = Depends(require_admin)):
    oid = to_oid(product_id, "Produk")
    old = await db.products.find_one({"_id": oid})
    if not old:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan.")
    now = now_utc()
    data = {**body.model_dump(), "updated_at": now}
    upd = {"$set": data}
    if int(old["price"]) != body.price:
        upd["$push"] = {"price_history": {"changed_at": now, "old_price": int(old["price"]), "new_price": body.price,
                                          "admin_id": user["_id"], "admin_name": user.get("name")}}
    await db.products.update_one({"_id": oid}, upd)
    changes = {k: {"old": old.get(k), "new": data[k]} for k in ("name", "voltage", "price", "is_active") if old.get(k) != data[k]}
    if changes:
        await audit(db, user, "ubah_produk", "products", oid, changes)
    return ser(await db.products.find_one({"_id": oid}))
