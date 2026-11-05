import asyncio
import logging
import mimetypes
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

import httpx
from bson import ObjectId
from pymongo import ReturnDocument

from app import config
from app.utils import fmt_dt, item_display, now_utc, normalize_phone

log = logging.getLogger("notifications")
PHOTO_MARK = "{{FOTO_RESI}}"
BACKOFF_MIN = [1, 5, 15, 60, 180]
SEP = "---------------------------------"


class FonnteError(Exception):
    def __init__(self, message: str, response=None):
        super().__init__(message)
        self.response = response


async def send_fonnte(target: str, message: str, file_path: Optional[Path] = None) -> dict:
    if not config.FONNTE_TOKEN:
        raise FonnteError("FONNTE_TOKEN belum dikonfigurasi.")
    headers = {"Authorization": config.FONNTE_TOKEN}
    data = {"target": target, "message": message, "countryCode": "62"}
    async with httpx.AsyncClient(timeout=60 if file_path else 30) as client:
        if file_path:
            mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            with file_path.open("rb") as fh:
                resp = await client.post(config.FONNTE_API_URL, headers=headers, data=data,
                                         files={"file": (file_path.name, fh, mime)})
        else:
            resp = await client.post(config.FONNTE_API_URL, headers=headers, data=data)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:500]}
    if resp.status_code >= 400 or not body.get("status", False):
        raise FonnteError(f"Fonnte menolak permintaan (HTTP {resp.status_code}): {body.get('reason') or body}", body)
    return body


async def enqueue(db, kind: str, target: str, message: str, order_id=None, file_path: Optional[str] = None):
    target = target if "@g.us" in (target or "") else normalize_phone(target)
    doc = {
        "kind": kind,
        "target": target,
        "message": message,
        "file_path": file_path,
        "order_id": order_id,
        "status": "pending",
        "attempts": 0,
        "last_error": None,
        "responses": [],
        "media_sent": None,
        "next_attempt_at": now_utc(),
        "created_at": now_utc(),
        "sent_at": None,
    }
    if not target:
        doc.update(status="failed", last_error="Nomor tujuan kosong atau tidak valid.")
    res = await db.notification_logs.insert_one(doc)
    if doc["status"] == "pending":
        asyncio.create_task(process_one(db, res.inserted_id))
    return res.inserted_id


def render(message: str, media_ok: bool) -> str:
    return message.replace(PHOTO_MARK, "Foto resi terlampir di atas.\n\n" if media_ok else "")


async def process_one(db, notif_id: ObjectId):
    now = now_utc()
    doc = await db.notification_logs.find_one_and_update(
        {"_id": notif_id, "status": "pending", "next_attempt_at": {"$lte": now}},
        {"$set": {"status": "sending", "locked_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        return
    if config.WHATSAPP_MODE != "live":
        await db.notification_logs.update_one({"_id": notif_id}, {"$set": {
            "status": "simulated", "sent_at": now_utc(), "rendered_message": render(doc["message"], bool(doc.get("file_path"))),
            "media_sent": bool(doc.get("file_path")) or None,
            "last_error": None,
        }, "$push": {"responses": {"at": now_utc(), "info": "Mode simulasi: pesan tidak dikirim ke Fonnte."}}})
        return
    responses, media_ok = [], None
    try:
        fp = Path(doc["file_path"]) if doc.get("file_path") else None
        if fp and fp.is_file():
            try:
                body = await send_fonnte(doc["target"], render(doc["message"], True), fp)
                media_ok = True
                responses.append({"at": now_utc(), "body": body, "media": True})
            except FonnteError as e:
                responses.append({"at": now_utc(), "error": str(e), "media": True})
                media_ok = False
        if media_ok is not True:
            body = await send_fonnte(doc["target"], render(doc["message"], False))
            responses.append({"at": now_utc(), "body": body, "media": False})
        await db.notification_logs.update_one({"_id": notif_id}, {"$set": {
            "status": "sent", "sent_at": now_utc(), "media_sent": media_ok, "last_error": None,
            "rendered_message": render(doc["message"], bool(media_ok)),
        }, "$inc": {"attempts": 1}, "$push": {"responses": {"$each": responses}}})
    except Exception as e:
        attempts = doc.get("attempts", 0) + 1
        final = attempts >= config.NOTIF_MAX_ATTEMPTS
        delay = BACKOFF_MIN[min(attempts - 1, len(BACKOFF_MIN) - 1)]
        responses.append({"at": now_utc(), "error": str(e)})
        await db.notification_logs.update_one({"_id": notif_id}, {"$set": {
            "status": "failed" if final else "pending",
            "last_error": str(e)[:1000],
            "next_attempt_at": now_utc() + timedelta(minutes=delay),
        }, "$inc": {"attempts": 1}, "$push": {"responses": {"$each": responses}}})
        log.warning("Notifikasi %s gagal: %s", notif_id, e)


async def worker(db):
    while True:
        try:
            stale = now_utc() - timedelta(minutes=5)
            await db.notification_logs.update_many({"status": "sending", "locked_at": {"$lt": stale}},
                                                   {"$set": {"status": "pending"}})
            cursor = db.notification_logs.find({"status": "pending", "next_attempt_at": {"$lte": now_utc()}}, {"_id": 1}).limit(20)
            async for d in cursor:
                await process_one(db, d["_id"])
        except Exception as e:
            log.error("Worker notifikasi error: %s", e)
        await asyncio.sleep(15)


def _item_lines(items: List[dict], qty_key: str = "qty_order") -> str:
    return "\n".join(f"- {item_display(i['product_name_snapshot'], i.get('voltage_snapshot'))} ({i[qty_key]} pcs)" for i in items)


def msg_order_reseller(order: dict) -> str:
    return (f"🛒 *Order Berhasil Dibuat!*\n{SEP}\nKode Order: *{order['code']}*\nTanggal: {fmt_dt(order['created_at'])}\n\n"
            f"*Daftar Item:*\n{_item_lines(order['items'])}\n\nStatus: Menunggu Konfirmasi Admin\n\n"
            f"Terima kasih sudah order di RelayLab! 🙏")


def msg_order_admin(order: dict) -> str:
    r = order["reseller_snapshot"]
    return (f"📢 *Order Baru Masuk!*\n{SEP}\nKode Order: *{order['code']}*\nReseller: {r['name']}\nWA: {r['wa']}\n\n"
            f"*Daftar Item:*\n{_item_lines(order['items'])}\n\nSegera review order ini di dashboard admin.")


def msg_order_processed(order: dict) -> str:
    return (f"📦 *Order Kamu Sedang Diproses!*\n{SEP}\nKode Order: *{order['code']}*\nTanggal: {fmt_dt(now_utc())}\n\n"
            f"Halo {order['reseller_snapshot']['name']}, Order kamu sudah diproses dan sedang dikerjakan tim produksi RelayLab 🙏")


def msg_shipment(sh: dict) -> str:
    lines = "\n".join(f"- {item_display(i['product_name_snapshot'], i.get('voltage_snapshot'))} ({i['qty']} pcs)" for i in sh["items"])
    return (f"🚚 *Pengiriman Pesanan RelayLab*\n{SEP}\nPesanan kamu sudah dikirim!\n\n*Kode Order:* {sh['order_code']}\n"
            f"*Ekspedisi:* {sh['courier']}\n*No Resi:* {sh['tracking_no']}\n*Tanggal:* {fmt_dt(sh['shipped_at'])}\n"
            f"*Catatan:* {sh.get('notes') or '-'}\n\n*Produk yang dikirim:*\n{lines}\n\n{PHOTO_MARK}Terima kasih sudah order 🙏")


async def notify_admins(db, kind: str, message: str, order_id=None):
    for wa in config.FONNTE_ADMIN_WA:
        await enqueue(db, kind, wa, message, order_id)
