import hashlib
import json
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from app import config
from app.db import db
from app.security import require_admin
from app.services import notifications as notif
from app.utils import audit, fmt_dt, item_display, normalize_phone, now_utc, ser, to_oid

router = APIRouter(prefix="/api", tags=["notifications"])
STATE_TTL_MIN = 10
CEK_HELP = ("ℹ️ *Cara Cek Order*\n\nKetik: /cekorder KODE_ORDER\nContoh: /cekorder RL-050126-0001\n\n"
            "Kode order dapat dilihat di dashboard reseller RelayLab.")


@router.get("/notifications")
async def list_notifications(status: Optional[str] = None, user: dict = Depends(require_admin)):
    flt = {"status": status} if status else {}
    docs = await db.notification_logs.find(flt).sort("created_at", -1).to_list(500)
    return {"mode": config.WHATSAPP_MODE, "token_configured": bool(config.FONNTE_TOKEN), "items": ser(docs)}


@router.post("/notifications/{notif_id}/retry")
async def retry_notification(notif_id: str, user: dict = Depends(require_admin)):
    oid = to_oid(notif_id, "Notifikasi")
    res = await db.notification_logs.update_one({"_id": oid, "status": {"$in": ["failed", "pending"]}},
                                                {"$set": {"status": "pending", "attempts": 0, "next_attempt_at": now_utc()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=422, detail="Hanya notifikasi gagal atau menunggu yang dapat dikirim ulang.")
    await notif.process_one(db, oid)
    return ser(await db.notification_logs.find_one({"_id": oid}))


@router.get("/audit-logs")
async def audit_logs(entity: Optional[str] = None, entity_id: Optional[str] = None, user: dict = Depends(require_admin)):
    flt: dict = {}
    if entity:
        flt["entity"] = entity
    if entity_id:
        flt["entity_id"] = entity_id
    return ser(await db.audit_logs.find(flt).sort("created_at", -1).to_list(500))


def is_admin_wa(sender: str) -> bool:
    return sender in {normalize_phone(w) for w in config.FONNTE_ADMIN_WA}


async def cekorder_reply(sender: str, code: str) -> str:
    reseller = await db.resellers.find_one({"wa_normalized": sender})
    order = await db.orders.find_one({"code": code.upper()}) if reseller else None
    if not reseller or not order or order["reseller_id"] != reseller["_id"]:
        return f"Order *{code.upper()}* tidak ditemukan untuk nomor WhatsApp ini.\n\nPastikan kode order benar dan anda mengirim dari nomor yang terdaftar."
    status = {"menunggu_konfirmasi": "Menunggu Konfirmasi", "diproses": "Diproses", "selesai": "Selesai"}[order["status"]]
    done = [i for i in order["items"] if i["qty_shipped"] >= i["qty_order"]]
    pending = [i for i in order["items"] if i["qty_shipped"] < i["qty_order"]]
    lines = [f"📄 *Detail Order {order['code']}*", "", f"Tanggal Order: {fmt_dt(order['created_at'])}", f"Status: {status}", ""]
    lines.append("✅ *Produk yang sudah dikirim:*")
    lines += [f"- {item_display(i['product_name_snapshot'], i.get('voltage_snapshot'))} ({i['qty_order']} pcs)" for i in done] or ["- Belum ada"]
    lines += ["", "⏳ *Produk yang belum selesai / dalam proses:*"]
    for i in pending:
        lines.append(f"- {item_display(i['product_name_snapshot'], i.get('voltage_snapshot'))}")
        lines.append(f"  {i['qty_done']}/{i['qty_order']} pcs selesai produksi, {i['qty_shipped']} pcs terkirim")
    if not pending:
        lines.append("- Tidak ada")
    shipments = await db.shipments.find({"order_id": order["_id"]}).sort("shipped_at", 1).to_list(100)
    lines += ["", "🚚 *Riwayat Pengiriman:*"]
    for s in shipments:
        lines += [f"- {fmt_dt(s['shipped_at'])}", f"  {s['courier']}", f"  Resi: {s['tracking_no']}"]
    if not shipments:
        lines.append("- Belum ada pengiriman")
    lines += ["", "Terima kasih sudah order di RelayLab 🙏"]
    return "\n".join(lines)


async def parse_payload(request: Request) -> dict:
    try:
        ctype = request.headers.get("content-type", "")
        if "application/json" in ctype:
            return await request.json()
        form = await request.form()
        return dict(form)
    except Exception:
        return {}


@router.api_route("/webhooks/fonnte", methods=["GET", "POST"])
async def fonnte_webhook(request: Request):
    if config.FONNTE_WEBHOOK_SECRET and request.query_params.get("secret") != config.FONNTE_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    if request.method == "GET":
        return {"status": True}
    data = await parse_payload(request)
    raw_sender = str(data.get("sender") or "")
    message = str(data.get("message") or data.get("text") or "").strip()
    if not raw_sender or not message or "@g.us" in raw_sender or data.get("member") or data.get("isgroup") in (True, "true"):
        return {"status": True}
    sender = normalize_phone(raw_sender)
    key = str(data.get("id") or data.get("inboxid") or "") or hashlib.sha256(
        f"{sender}|{message}|{data.get('timestamp') or now_utc().strftime('%Y%m%d%H%M%S')[:-1]}".encode()).hexdigest()
    try:
        await db.webhook_events.insert_one({"key": key, "sender": sender, "created_at": now_utc()})
    except DuplicateKeyError:
        return {"status": True, "duplicate": True}

    lower = message.lower()
    now = now_utc()
    if lower.startswith("/cekorder"):
        parts = message.split()
        reply = CEK_HELP if len(parts) < 2 else await cekorder_reply(sender, parts[1].strip())
        await notif.enqueue(db, "balasan_cekorder", sender, reply)
        return {"status": True}
    if not is_admin_wa(sender):
        return {"status": True}
    if lower == "/pengumuman":
        await db.announcement_states.update_one({"sender": sender}, {"$set": {
            "sender": sender, "state": "waiting_announcement", "created_at": now,
            "expires_at": now + timedelta(minutes=STATE_TTL_MIN)}}, upsert=True)
        await notif.enqueue(db, "balasan_pengumuman", sender,
                            f"Silahkan isi pesan pengumuman\n\nKetik /batal untuk membatalkan. Batas waktu {STATE_TTL_MIN} menit.")
        return {"status": True}
    if lower == "/batal":
        st = await db.announcement_states.find_one_and_delete({"sender": sender})
        if st:
            await notif.enqueue(db, "balasan_pengumuman", sender, "Pengumuman dibatalkan.")
        return {"status": True}
    st = await db.announcement_states.find_one_and_delete({"sender": sender, "state": "waiting_announcement", "expires_at": {"$gt": now}})
    if st:
        if not config.FONNTE_GROUP_ID:
            await notif.enqueue(db, "balasan_pengumuman", sender, "Gagal: ID grup WhatsApp (FONNTE_GROUP_ID) belum dikonfigurasi.")
            return {"status": True}
        digest = hashlib.sha256(message.encode()).hexdigest()
        recent = await db.notification_logs.find_one({"kind": "pengumuman", "digest": digest,
                                                      "created_at": {"$gt": now - timedelta(minutes=5)}})
        if recent:
            await notif.enqueue(db, "balasan_pengumuman", sender, "Pengumuman yang sama baru saja dikirim, tidak dikirim ulang.")
            return {"status": True}
        nid = await notif.enqueue(db, "pengumuman", config.FONNTE_GROUP_ID, message)
        await db.notification_logs.update_one({"_id": nid}, {"$set": {"digest": digest, "sender": sender}})
        await audit(db, None, "pengumuman_grup", "notification_logs", nid, {"sender": sender, "message": message[:500]})
        await notif.enqueue(db, "balasan_pengumuman", sender, "✅ Pengumuman sudah dimasukkan ke antrean pengiriman ke grup.")
    return {"status": True}


__all__ = ["router", "json"]
