import uuid
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from app.utils import JKT, item_display, now_utc, to_oid

STATUS_LABELS = {
    "menunggu_konfirmasi": "Menunggu Konfirmasi",
    "diproses": "Diproses",
    "selesai": "Selesai",
}


def min_qty(is_special: bool) -> int:
    return 1 if is_special else 10


async def next_order_code(db) -> str:
    d = now_utc().astimezone(JKT).strftime("%d%m%y")
    doc = await db.system_settings.find_one_and_update(
        {"_id": f"order_seq:{d}"},
        {"$inc": {"seq": 1}, "$setOnInsert": {"kind": "order_counter"}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"RL-{d}-{doc['seq']:04d}"


def recompute_items(items: List[dict]) -> dict:
    for it in items:
        p = it.get("unit_price_snapshot")
        it["subtotal"] = int(p) * int(it["qty_order"]) if p is not None else 0
    return {
        "items": items,
        "total_qty": sum(int(i["qty_order"]) for i in items),
        "grand_total": sum(int(i["subtotal"]) for i in items),
        "price_pending": any(i.get("unit_price_snapshot") is None for i in items),
    }


def payment_status(grand_total: int, total_paid: int) -> str:
    if total_paid <= 0:
        return "belum_ada_pembayaran"
    if total_paid < grand_total:
        return "belum_lunas"
    if total_paid > grand_total:
        return "lebih_bayar"
    return "lunas"


def enrich(order: dict) -> dict:
    gt = int(order.get("grand_total", 0))
    paid = int(order.get("total_paid", 0))
    order["remaining"] = gt - paid
    order["payment_status"] = payment_status(gt, paid)
    order["overpaid"] = max(paid - gt, 0)
    order["status_label"] = STATUS_LABELS.get(order.get("status"), order.get("status"))
    for it in order.get("items", []):
        it["qty_remaining_ship"] = max(int(it["qty_order"]) - int(it["qty_shipped"]), 0)
        it["display_name"] = item_display(it["product_name_snapshot"], it.get("voltage_snapshot"))
    return order


async def build_items(db, items_in, is_special: bool, check_prices: bool) -> List[dict]:
    mq = min_qty(is_special)
    errors, changes, merged = [], [], {}
    customs = []
    for idx, it in enumerate(items_in):
        if it.qty < mq:
            errors.append({"index": idx, "product_id": it.product_id, "custom_name": it.custom_name,
                           "message": f"Qty minimal per item untuk akun anda adalah {mq} pcs."})
        if it.product_id:
            key = it.product_id
            if key in merged:
                merged[key]["qty"] += it.qty
            else:
                merged[key] = {"qty": it.qty, "expected_price": it.expected_price, "index": idx}
        else:
            name = (it.custom_name or "").strip()
            if len(name) < 2:
                errors.append({"index": idx, "message": "Nama produk custom wajib diisi."})
            customs.append({"name": name, "qty": it.qty})

    oids = []
    for pid in merged:
        try:
            oids.append(ObjectId(pid))
        except Exception:
            errors.append({"product_id": pid, "message": "Produk tidak ditemukan."})
    products = {str(p["_id"]): p async for p in db.products.find({"_id": {"$in": oids}})}

    out = []
    for pid, m in merged.items():
        p = products.get(pid)
        if not p or not p.get("is_active", True):
            errors.append({"index": m["index"], "product_id": pid, "message": "Produk tidak tersedia atau sudah tidak aktif."})
            continue
        if check_prices and m["expected_price"] is not None and int(m["expected_price"]) != int(p["price"]):
            changes.append({"product_id": pid, "name": item_display(p["name"], p.get("voltage")),
                            "old_price": m["expected_price"], "new_price": p["price"]})
        out.append({
            "item_id": uuid.uuid4().hex,
            "product_id": p["_id"],
            "is_custom": False,
            "custom_name": None,
            "product_code_snapshot": p.get("code"),
            "product_name_snapshot": p["name"],
            "voltage_snapshot": p.get("voltage", "-"),
            "unit_price_snapshot": int(p["price"]),
            "price_status": "confirmed",
            "qty_order": m["qty"],
            "subtotal": int(p["price"]) * m["qty"],
            "qty_done": 0,
            "qty_shipped": 0,
        })
    for c in customs:
        out.append({
            "item_id": uuid.uuid4().hex,
            "product_id": None,
            "is_custom": True,
            "custom_name": c["name"],
            "product_code_snapshot": "CUSTOM",
            "product_name_snapshot": c["name"],
            "voltage_snapshot": "-",
            "unit_price_snapshot": None,
            "price_status": "pending",
            "qty_order": c["qty"],
            "subtotal": 0,
            "qty_done": 0,
            "qty_shipped": 0,
        })
    if errors:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION", "message": errors[0]["message"], "errors": errors})
    if changes:
        raise HTTPException(status_code=409, detail={
            "code": "PRICE_CHANGED",
            "message": "Harga beberapa produk telah berubah. Periksa kembali keranjang anda sebelum konfirmasi.",
            "changes": changes,
        })
    return out


async def get_order_for(db, order_id: str, user: dict) -> dict:
    order = await db.orders.find_one({"_id": to_oid(order_id, "Order")})
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan.")
    if user["role"] != "admin" and order["reseller_id"] != user.get("reseller_id"):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke order ini.")
    # Internal use only (keeps ObjectId for updates); routes serialize via ser()/enrich().
    return dict(order.items())


async def update_versioned(db, order: dict, set_fields: dict, push: Optional[dict] = None):
    upd = {"$set": {**set_fields, "updated_at": now_utc()}, "$inc": {"version": 1}}
    if push:
        upd["$push"] = push
    res = await db.orders.update_one({"_id": order["_id"], "version": order.get("version", 0)}, upd)
    if res.modified_count == 0:
        raise HTTPException(status_code=409, detail="Order baru saja diubah oleh proses lain. Muat ulang halaman lalu coba lagi.")


async def recalc_paid(db, order_id: ObjectId) -> int:
    agg = await db.order_payments.aggregate([
        {"$match": {"order_id": order_id, "is_void": {"$ne": True}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(1)
    total = int(agg[0]["total"]) if agg else 0
    await db.orders.update_one({"_id": order_id}, {"$set": {"total_paid": total, "updated_at": now_utc()}})
    return total
