import json
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pymongo.errors import DuplicateKeyError

from app.db import db
from app.schemas import (NotesIn, OrderCreateIn, PaymentIn, PaymentVoidIn, PriceAdjustIn, ProgressIn,
                         ResolveCustomIn, StatusIn)
from app.security import get_current_user, require_admin
from app.services import notifications as notif
from app.services.orders import (STATUS_LABELS, build_items, enrich, get_order_for, next_order_code,
                                 recalc_paid, recompute_items, update_versioned)
from app.services.storage import resi_path, save_receipt
from app.utils import JKT, audit, jkt_range_to_utc, now_utc, rupiah, ser, to_oid

router = APIRouter(prefix="/api/orders", tags=["orders"])
files_router = APIRouter(prefix="/api/files", tags=["files"])


def out(order: dict) -> dict:
    return enrich(ser(order))


@router.get("")
async def list_orders(status: Optional[str] = None, reseller_id: Optional[str] = None, q: Optional[str] = None,
                      date_from: Optional[date] = None, date_to: Optional[date] = None,
                      user: dict = Depends(get_current_user)):
    flt: dict = {}
    if user["role"] != "admin":
        flt["reseller_id"] = user["reseller_id"]
    elif reseller_id:
        flt["reseller_id"] = to_oid(reseller_id, "Reseller")
    if status:
        flt["status"] = status
    rng = jkt_range_to_utc(date_from, date_to)
    if rng:
        flt["created_at"] = rng
    if q:
        import re
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"code": rx}, {"reseller_snapshot.name": rx}]
    docs = await db.orders.find(flt, {"status_history": 0, "price_adjustments": 0, "idempotency_key": 0}).sort("created_at", -1).to_list(5000)
    return [out(d) for d in docs]


@router.post("")
async def create_order(body: OrderCreateIn, user: dict = Depends(get_current_user)):
    is_admin = user["role"] == "admin"
    if is_admin:
        if not body.reseller_id:
            raise HTTPException(status_code=422, detail="Pilih reseller terlebih dahulu.")
        rid = to_oid(body.reseller_id, "Reseller")
    else:
        if not user.get("reseller_id"):
            raise HTTPException(status_code=403, detail="Akun Anda belum terhubung dengan data reseller.")
        rid = user["reseller_id"]
    existing = await db.orders.find_one({"idempotency_key": body.idempotency_key})
    if existing:
        if existing["created_by"] != user["_id"]:
            raise HTTPException(status_code=409, detail="Permintaan duplikat terdeteksi.")
        return out(existing)
    reseller = await db.resellers.find_one({"_id": rid})
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller tidak ditemukan.")
    items = await build_items(db, body.items, bool(reseller.get("is_special")), check_prices=not is_admin)
    now = now_utc()
    totals = recompute_items(items)
    doc = {
        "code": await next_order_code(db),
        "reseller_id": rid,
        "reseller_snapshot": {"name": reseller["name"], "wa": reseller["wa"], "is_special": bool(reseller.get("is_special"))},
        **totals,
        "total_paid": 0,
        "status": "menunggu_konfirmasi",
        "reseller_notes": body.notes.strip(),
        "internal_notes": "",
        "price_adjustments": [],
        "status_history": [{"status": "menunggu_konfirmasi", "at": now, "by": user["_id"], "by_name": user.get("name")}],
        "created_by": user["_id"],
        "created_by_role": user["role"],
        "idempotency_key": body.idempotency_key,
        "version": 0,
        "created_at": now,
        "updated_at": now,
    }
    try:
        res = await db.orders.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.orders.find_one({"idempotency_key": body.idempotency_key})
        if existing:
            return out(existing)
        raise HTTPException(status_code=409, detail="Gagal membuat kode order unik. Silakan coba lagi.")
    doc["_id"] = res.inserted_id
    await audit(db, user, "buat_order", "orders", res.inserted_id, {"code": doc["code"], "grand_total": doc["grand_total"]})
    await notif.enqueue(db, "order_baru_reseller", reseller["wa"], notif.msg_order_reseller(doc), res.inserted_id)
    await notif.notify_admins(db, "order_baru_admin", notif.msg_order_admin(doc), res.inserted_id)
    return out(doc)


@router.get("/{order_id}")
async def get_order(order_id: str, user: dict = Depends(get_current_user)):
    order = await get_order_for(db, order_id, user)
    payments = await db.order_payments.find({"order_id": order["_id"]}).sort("paid_at", 1).to_list(1000)
    shipments = await db.shipments.find({"order_id": order["_id"]}).sort("shipped_at", 1).to_list(1000)
    data = out(order)
    if user["role"] != "admin":
        data.pop("internal_notes", None)
        data.pop("idempotency_key", None)
        payments = [p for p in payments if not p.get("is_void")]
        for p in payments:
            p.pop("recorded_by", None)
    return {"order": data, "payments": ser(payments), "shipments": ser(shipments)}


@router.patch("/{order_id}/status")
async def update_status(order_id: str, body: StatusIn, user: dict = Depends(require_admin)):
    order = await get_order_for(db, order_id, user)
    if order["status"] == body.status:
        return out(order)
    entry = {"status": body.status, "from": order["status"], "at": now_utc(), "by": user["_id"], "by_name": user.get("name")}
    await update_versioned(db, order, {"status": body.status}, {"status_history": entry})
    await audit(db, user, "ubah_status_order", "orders", order["_id"],
                {"code": order["code"], "from": order["status"], "to": body.status})
    if body.status == "diproses":
        await notif.enqueue(db, "order_diproses", order["reseller_snapshot"]["wa"], notif.msg_order_processed(order), order["_id"])
    return out(await db.orders.find_one({"_id": order["_id"]}))


@router.put("/{order_id}/progress")
async def update_progress(order_id: str, body: ProgressIn, user: dict = Depends(require_admin)):
    order = await get_order_for(db, order_id, user)
    items = order["items"]
    by_id = {i["item_id"]: i for i in items}
    changes = []
    for p in body.items:
        it = by_id.get(p.item_id)
        if not it:
            raise HTTPException(status_code=422, detail="Item order tidak ditemukan.")
        if p.qty_done > it["qty_order"]:
            raise HTTPException(status_code=422, detail=f"Qty selesai {it['product_name_snapshot']} tidak boleh melebihi qty order ({it['qty_order']}).")
        if p.qty_done < it["qty_shipped"]:
            raise HTTPException(status_code=422, detail=f"Qty selesai {it['product_name_snapshot']} tidak boleh kurang dari qty yang sudah dikirim ({it['qty_shipped']}).")
        if p.qty_done != it["qty_done"]:
            changes.append({"item_id": it["item_id"], "name": it["product_name_snapshot"], "old": it["qty_done"], "new": p.qty_done})
            it["qty_done"] = p.qty_done
    if changes:
        await update_versioned(db, order, {"items": items})
        await audit(db, user, "ubah_progress_produksi", "orders", order["_id"], {"code": order["code"], "changes": changes})
    return out(await db.orders.find_one({"_id": order["_id"]}))


@router.put("/{order_id}/notes")
async def update_notes(order_id: str, body: NotesIn, user: dict = Depends(require_admin)):
    order = await get_order_for(db, order_id, user)
    await db.orders.update_one({"_id": order["_id"]}, {"$set": {"internal_notes": body.internal_notes, "updated_at": now_utc()}})
    return out(await db.orders.find_one({"_id": order["_id"]}))


@router.post("/{order_id}/payments")
async def add_payment(order_id: str, body: PaymentIn, user: dict = Depends(require_admin)):
    order = await get_order_for(db, order_id, user)
    dup = await db.order_payments.find_one({"idempotency_key": body.idempotency_key})
    if dup:
        if dup["order_id"] != order["_id"]:
            raise HTTPException(status_code=409, detail="Permintaan duplikat terdeteksi.")
        return ser(dup)
    paid_at = body.paid_at or now_utc()
    if paid_at.tzinfo is None:
        paid_at = paid_at.replace(tzinfo=JKT).astimezone(timezone.utc)
    doc = {"order_id": order["_id"], "order_code": order["code"], "reseller_id": order["reseller_id"],
           "amount": body.amount, "paid_at": paid_at, "notes": body.notes.strip(),
           "recorded_by": user["_id"], "recorded_by_name": user.get("name"), "is_void": False,
           "idempotency_key": body.idempotency_key, "created_at": now_utc()}
    try:
        res = await db.order_payments.insert_one(doc)
    except DuplicateKeyError:
        return ser(await db.order_payments.find_one({"idempotency_key": body.idempotency_key}))
    total = await recalc_paid(db, order["_id"])
    await audit(db, user, "tambah_pembayaran", "orders", order["_id"],
                {"code": order["code"], "payment_id": str(res.inserted_id), "amount": body.amount, "total_paid": total})
    doc["_id"] = res.inserted_id
    return ser(doc)


@router.post("/{order_id}/payments/{payment_id}/void")
async def void_payment(order_id: str, payment_id: str, body: PaymentVoidIn, user: dict = Depends(require_admin)):
    order = await get_order_for(db, order_id, user)
    pid = to_oid(payment_id, "Pembayaran")
    res = await db.order_payments.update_one({"_id": pid, "order_id": order["_id"], "is_void": False}, {"$set": {
        "is_void": True, "void_reason": body.reason.strip(), "voided_by": user["_id"],
        "voided_by_name": user.get("name"), "voided_at": now_utc()}})
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan atau sudah dibatalkan.")
    p = await db.order_payments.find_one({"_id": pid})
    total = await recalc_paid(db, order["_id"])
    await audit(db, user, "batalkan_pembayaran", "orders", order["_id"],
                {"code": order["code"], "payment_id": payment_id, "amount": p["amount"], "reason": body.reason, "total_paid": total})
    return {"ok": True}


@router.post("/{order_id}/price-adjustments")
async def price_adjustment(order_id: str, body: PriceAdjustIn, user: dict = Depends(require_admin)):
    order = await get_order_for(db, order_id, user)
    items = order["items"]
    it = next((i for i in items if i["item_id"] == body.item_id), None)
    if not it:
        raise HTTPException(status_code=422, detail="Item order tidak ditemukan.")
    if it.get("unit_price_snapshot") is None:
        raise HTTPException(status_code=422, detail="Harga item custom belum ditetapkan. Gunakan fitur Tetapkan Harga Custom.")
    old_price = int(it["unit_price_snapshot"])
    if old_price == body.new_price:
        raise HTTPException(status_code=422, detail="Harga baru sama dengan harga transaksi saat ini.")
    it["unit_price_snapshot"] = body.new_price
    totals = recompute_items(items)
    entry = {"type": "penyesuaian_harga", "item_id": it["item_id"], "product_name": it["product_name_snapshot"],
             "old_price": old_price, "new_price": body.new_price, "reason": body.reason.strip(),
             "old_grand_total": order["grand_total"], "new_grand_total": totals["grand_total"],
             "admin_id": user["_id"], "admin_name": user.get("name"), "at": now_utc()}
    await update_versioned(db, order, totals, {"price_adjustments": entry})
    await audit(db, user, "penyesuaian_harga_order", "orders", order["_id"], {"code": order["code"], **{k: v for k, v in entry.items() if k not in ("admin_id", "at")}})
    return out(await db.orders.find_one({"_id": order["_id"]}))


@router.post("/{order_id}/custom-items/resolve")
async def resolve_custom(order_id: str, body: ResolveCustomIn, user: dict = Depends(require_admin)):
    order = await get_order_for(db, order_id, user)
    items = order["items"]
    it = next((i for i in items if i["item_id"] == body.item_id), None)
    if not it or not it.get("is_custom"):
        raise HTTPException(status_code=422, detail="Item custom tidak ditemukan.")
    old = {"name": it["product_name_snapshot"], "price": it.get("unit_price_snapshot")}
    if body.product_id:
        p = await db.products.find_one({"_id": to_oid(body.product_id, "Produk")})
        if not p:
            raise HTTPException(status_code=404, detail="Produk tidak ditemukan.")
        it.update(product_id=p["_id"], product_code_snapshot=p["code"], product_name_snapshot=p["name"],
                  voltage_snapshot=p.get("voltage", "-"))
    it["unit_price_snapshot"] = body.unit_price
    it["price_status"] = "confirmed"
    totals = recompute_items(items)
    entry = {"type": "penetapan_custom", "item_id": it["item_id"], "product_name": it["product_name_snapshot"],
             "custom_name": it.get("custom_name"), "old_product_name": old["name"], "old_price": old["price"],
             "new_price": body.unit_price, "reason": body.reason.strip(), "old_grand_total": order["grand_total"],
             "new_grand_total": totals["grand_total"], "admin_id": user["_id"], "admin_name": user.get("name"), "at": now_utc()}
    await update_versioned(db, order, totals, {"price_adjustments": entry})
    await audit(db, user, "penetapan_harga_custom", "orders", order["_id"],
                {"code": order["code"], "item": it.get("custom_name"), "mapped_to": it["product_name_snapshot"], "price": body.unit_price})
    return out(await db.orders.find_one({"_id": order["_id"]}))


@router.post("/{order_id}/shipments")
async def create_shipment(order_id: str, courier: str = Form(..., min_length=2), tracking_no: str = Form(..., min_length=2),
                          shipped_at: str = Form(...), notes: str = Form(""), items: str = Form(...),
                          idempotency_key: str = Form(..., min_length=8), photo: Optional[UploadFile] = File(None),
                          user: dict = Depends(require_admin)):
    order = await get_order_for(db, order_id, user)
    dup = await db.shipments.find_one({"idempotency_key": idempotency_key})
    if dup:
        if dup["order_id"] != order["_id"]:
            raise HTTPException(status_code=409, detail="Permintaan duplikat terdeteksi.")
        return ser(dup)
    try:
        req = {str(i["item_id"]): int(i["qty"]) for i in json.loads(items)}
        dt = datetime.fromisoformat(shipped_at)
    except Exception:
        raise HTTPException(status_code=422, detail="Data pengiriman tidak valid.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JKT)
    dt = dt.astimezone(timezone.utc)
    order_items = order["items"]
    ship_items = []
    for it in order_items:
        q = req.get(it["item_id"], 0)
        if q < 0:
            raise HTTPException(status_code=422, detail="Qty kirim tidak boleh negatif.")
        if q == 0:
            continue
        remaining = it["qty_order"] - it["qty_shipped"]
        if q > remaining:
            raise HTTPException(status_code=422, detail=f"Qty kirim {it['product_name_snapshot']} melebihi sisa kirim ({remaining} pcs).")
        it["qty_shipped"] += q
        it["qty_done"] = max(it["qty_done"], it["qty_shipped"])
        ship_items.append({"item_id": it["item_id"], "product_name_snapshot": it["product_name_snapshot"],
                           "voltage_snapshot": it.get("voltage_snapshot"), "qty": q})
    if not ship_items:
        raise HTTPException(status_code=422, detail="Isi minimal satu qty produk yang dikirim.")
    if any(k not in {i["item_id"] for i in order_items} for k in req):
        raise HTTPException(status_code=422, detail="Item order tidak ditemukan.")
    photo_name = await save_receipt(photo) if photo and photo.filename else None
    all_shipped = all(i["qty_shipped"] >= i["qty_order"] for i in order_items)
    set_fields = {"items": order_items}
    push = None
    if all_shipped and order["status"] != "selesai":
        set_fields["status"] = "selesai"
        push = {"status_history": {"status": "selesai", "from": order["status"], "at": now_utc(), "by": user["_id"],
                                   "by_name": user.get("name"), "auto": True}}
    doc = {"order_id": order["_id"], "order_code": order["code"], "reseller_id": order["reseller_id"],
           "courier": courier.strip(), "tracking_no": tracking_no.strip(), "shipped_at": dt, "notes": notes.strip(),
           "photo_filename": photo_name, "items": ship_items, "created_by": user["_id"],
           "created_by_name": user.get("name"), "idempotency_key": idempotency_key, "created_at": now_utc()}
    try:
        res = await db.shipments.insert_one(doc)
    except DuplicateKeyError:
        if photo_name:
            resi_path(photo_name).unlink(missing_ok=True)
        return ser(await db.shipments.find_one({"idempotency_key": idempotency_key}))
    try:
        await update_versioned(db, order, set_fields, push)
    except HTTPException:
        await db.shipments.delete_one({"_id": res.inserted_id})
        if photo_name:
            resi_path(photo_name).unlink(missing_ok=True)
        raise
    doc["_id"] = res.inserted_id
    await audit(db, user, "buat_pengiriman", "orders", order["_id"],
                {"code": order["code"], "shipment_id": str(res.inserted_id), "items": [{"name": i["product_name_snapshot"], "qty": i["qty"]} for i in ship_items]})
    await notif.enqueue(db, "pengiriman", order["reseller_snapshot"]["wa"], notif.msg_shipment(doc), order["_id"],
                        str(resi_path(photo_name)) if photo_name else None)
    return ser(doc)


@files_router.get("/resi/{filename}")
async def get_resi(filename: str, user: dict = Depends(get_current_user)):
    sh = await db.shipments.find_one({"photo_filename": filename})
    if not sh:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    if user["role"] != "admin" and sh["reseller_id"] != user.get("reseller_id"):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke file ini.")
    path = resi_path(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File tidak ditemukan di penyimpanan.")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


__all__ = ["router", "files_router", "STATUS_LABELS", "rupiah"]
