import asyncio
import hashlib
import json
import logging
import secrets
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Dict, List

from bson import json_util
from bson.json_util import JSONOptions
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app import config
from app.maintenance import STATE
from app.services.storage import resi_path
from app.utils import JKT, now_utc

log = logging.getLogger("relaylab.cleanup")

CATEGORIES = {
    "orders": "Data Order",
    "resellers": "Data Reseller",
    "products": "Data Produk",
    "notifications": "Riwayat Notifikasi WhatsApp",
    "audit": "Log Audit dan Aktivitas",
}
# (koleksi, filter) yang dihapus per kategori. Akun admin/Super Admin tidak pernah tersentuh.
TARGETS = {
    "orders": [("orders", {}), ("order_payments", {}), ("shipments", {})],
    "resellers": [("resellers", {}), ("users", {"role": "reseller", "is_super_admin": {"$ne": True}})],
    "products": [("products", {})],
    "notifications": [("notification_logs", {}), ("announcement_states", {}), ("webhook_events", {})],
    "audit": [("audit_logs", {})],
}
SEQ_FILTER = {"_id": {"$regex": "^order_seq:"}}
PENDING_ORDER_NOTIF = {"order_id": {"$ne": None}, "status": {"$in": ["pending", "sending"]}}
LOCK_ID = "cleanup_lock"
JSON_OPTS = JSONOptions(tz_aware=True)
CONFIRM_TEXT = "HAPUS DATA"


def normalize(categories: List[str]) -> List[str]:
    cats = [c for c in CATEGORIES if c in set(categories or [])]
    if not cats or len(cats) != len(set(categories)):
        raise HTTPException(status_code=422, detail="Pilih minimal satu kategori data yang valid.")
    return cats


async def _resi_files(db) -> List[str]:
    names = await db.shipments.distinct("photo_filename", {"photo_filename": {"$nin": [None, ""]}})
    return [n for n in names if resi_path(n).is_file()]


async def preview(db, categories: List[str], reset_seq: bool) -> dict:
    cats = normalize(categories)
    counts: Dict[str, Dict[str, int]] = {}
    for c in cats:
        counts[c] = {coll: await db[coll].count_documents(f) for coll, f in TARGETS[c]}
    blocking, warnings = [], []
    if "orders" in cats:
        counts["orders"]["resi_files"] = len(await _resi_files(db))
        if "notifications" not in cats:
            n = await db.notification_logs.count_documents(PENDING_ORDER_NOTIF)
            counts["orders"]["notifications_cancelled"] = n
            if n:
                warnings.append(f"{n} notifikasi WhatsApp terkait order yang masih di antrean akan dibatalkan agar tidak terkirim.")
        if reset_seq:
            counts["orders"]["order_seq_counters"] = await db.system_settings.count_documents(SEQ_FILTER)
    elif reset_seq:
        blocking.append("Reset nomor urut order hanya bisa dipilih bersama kategori Data Order.")
    if "resellers" in cats and "orders" not in cats:
        n = await db.orders.count_documents({})
        if n:
            blocking.append(f"Masih ada {n} order milik reseller. Pilih juga kategori Data Order, atau batalkan pilihan Data Reseller.")
    if "products" in cats and "orders" not in cats:
        n = await db.orders.count_documents({"items.product_id": {"$ne": None}})
        if n:
            warnings.append(f"{n} order lama memuat produk ini. Order tetap utuh karena nama, voltase, dan harga sudah tersimpan di order.")
    if "audit" in cats:
        warnings.append("Catatan keamanan pembersihan data tidak ikut terhapus.")
    total = sum(v for c in counts.values() for k, v in c.items() if k not in ("notifications_cancelled", "order_seq_counters"))
    return {"categories": cats, "counts": counts, "blocking": blocking, "warnings": warnings, "total": total}


def _write_jsonl(path: Path, docs: list):
    with path.open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json_util.dumps(d) + "\n")
    path.chmod(0o600)
    with path.open(encoding="utf-8") as f:
        if sum(1 for _ in f) != len(docs):
            raise IOError(f"Verifikasi backup {path.name} gagal.")


async def _backup(db, cats: List[str], reset_seq: bool, stamp: str) -> tuple:
    folder = config.BACKUP_DIR / f"cleanup-{stamp}"
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    (folder / "files" / "resi").mkdir(mode=0o700, parents=True)
    plan: Dict[str, list] = {}

    async def add(coll: str, flt: dict):
        docs = await db[coll].find(flt).to_list(None)
        plan.setdefault(coll, []).extend(docs)

    for c in cats:
        for coll, flt in TARGETS[c]:
            await add(coll, flt)
    cancel_ids = []
    if "orders" in cats and "notifications" not in cats:
        docs = await db.notification_logs.find(PENDING_ORDER_NOTIF).to_list(None)
        cancel_ids = [d["_id"] for d in docs]
        plan.setdefault("notification_logs", []).extend(docs)
    if "orders" in cats and reset_seq:
        await add("system_settings", SEQ_FILTER)
    files = await _resi_files(db) if "orders" in cats else []
    for coll, docs in plan.items():
        _write_jsonl(folder / f"{coll}.jsonl", docs)
    for name in files:
        src, dst = resi_path(name), folder / "files" / "resi" / name
        shutil.copy2(src, dst)
        if dst.stat().st_size != src.stat().st_size:
            raise IOError(f"Verifikasi backup file {name} gagal.")
    manifest = {"created_at": now_utc().isoformat(), "categories": cats, "reset_order_seq": reset_seq,
                "collections": {k: len(v) for k, v in plan.items()}, "resi_files": len(files)}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (folder / "manifest.json").chmod(0o600)
    return folder, plan, cancel_ids, files


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def restore_backup(db, folder: Path, cancel_pending: bool = True) -> dict:
    """Kembalikan dokumen & file dari folder backup (upsert per _id). Manual: antrean WA lama tidak diaktifkan lagi."""
    if config.CLEANUP_TEST_FAIL_RESTORE:
        raise RuntimeError("Simulasi kegagalan pemulihan (khusus pengujian).")
    restored, conflicts = {}, []
    for path in sorted(folder.glob("*.jsonl")):
        coll = path.stem
        n = 0
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                doc = json_util.loads(line, json_options=JSON_OPTS)
                if cancel_pending and coll == "notification_logs" and doc.get("status") in ("pending", "sending"):
                    doc.update(status="cancelled", last_error="Dibatalkan saat pemulihan backup agar tidak terkirim ulang.")
                try:
                    await db[coll].replace_one({"_id": doc["_id"]}, doc, upsert=True)
                    n += 1
                except DuplicateKeyError as e:
                    conflicts.append(f"{coll} {doc['_id']}: {str(e)[:150]}")
        restored[coll] = n
    files = 0
    for src in (folder / "files" / "resi").glob("*"):
        dst = resi_path(src.name)
        if not dst.is_file() or file_sha(dst) != file_sha(src):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        files += 1
    restored["resi_files"] = files
    if conflicts:
        restored["conflicts"] = conflicts
    return restored


async def verify_restore(db, plan: Dict[str, list], files: List[str], folder: Path) -> List[str]:
    """Bandingkan isi database & file setelah pemulihan dengan data asli sebelum penghapusan."""
    problems = []
    for coll, docs in plan.items():
        ids = [d["_id"] for d in docs]
        found = {d["_id"]: d for d in await db[coll].find({"_id": {"$in": ids}}).to_list(None)}
        missing = [i for i in ids if i not in found]
        changed = [d["_id"] for d in docs if d["_id"] in found and found[d["_id"]] != d]
        if missing:
            problems.append(f"{coll}: {len(missing)} dokumen tidak kembali")
        if changed:
            problems.append(f"{coll}: {len(changed)} dokumen berbeda dari aslinya")
    for name in files:
        p, b = resi_path(name), folder / "files" / "resi" / name
        if not p.is_file() or file_sha(p) != file_sha(b):
            problems.append(f"foto resi {name} tidak kembali utuh")
    return problems


async def _acquire_lock(db, user: dict):
    stale = now_utc() - timedelta(minutes=30)
    await db.system_settings.delete_one({"_id": LOCK_ID, "started_at": {"$lt": stale}})
    try:
        await db.system_settings.insert_one({"_id": LOCK_ID, "started_at": now_utc(), "by": user["_id"]})
    except Exception:
        raise HTTPException(status_code=409, detail="Pembersihan data lain sedang berjalan. Coba lagi beberapa saat.")


async def _security_log(db, user: dict, ip: str, **data):
    await db.security_logs.insert_one({"action": "pembersihan_data", "actor_id": user["_id"], "actor_name": user.get("name"),
                                       "actor_email": user.get("email"), "ip": ip, "created_at": now_utc(), **data})


async def execute(db, user: dict, ip: str, cats: List[str], reset_seq: bool) -> dict:
    pv = await preview(db, cats, reset_seq)
    if pv["blocking"]:
        raise HTTPException(status_code=422, detail=" ".join(pv["blocking"]))
    cats = pv["categories"]
    await _acquire_lock(db, user)
    STATE["active"] = True
    stamp = now_utc().astimezone(JKT).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    folder = None
    try:
        await asyncio.sleep(1)
        try:
            folder, plan, cancel_ids, files = await _backup(db, cats, reset_seq, stamp)
        except Exception as e:
            log.exception("Backup pembersihan gagal")
            await _security_log(db, user, ip, categories=cats, counts=pv["counts"], result="dibatalkan_backup_gagal", error=str(e)[:500])
            raise HTTPException(status_code=500, detail="Backup gagal dibuat, sehingga tidak ada data yang dihapus. Periksa izin folder backup di server.")
        deleted: Dict[str, int] = {}
        file_errors = 0
        fail_after = config.CLEANUP_TEST_FAIL_AFTER

        def fault(point: str):
            if fail_after == point:
                raise RuntimeError(f"Simulasi kegagalan setelah {point} (khusus pengujian).")
        try:
            for c in cats:
                for coll, _ in TARGETS[c]:
                    ids = [d["_id"] for d in plan.get(coll, []) if coll != "notification_logs" or d["_id"] not in cancel_ids]
                    if coll in deleted:
                        continue
                    res = await db[coll].delete_many({"_id": {"$in": ids}}) if ids else None
                    deleted[coll] = res.deleted_count if res else 0
                    fault(coll)
            if cancel_ids:
                res = await db.notification_logs.update_many(
                    {"_id": {"$in": cancel_ids}, "status": {"$in": ["pending", "sending"]}},
                    {"$set": {"status": "cancelled", "last_error": "Dibatalkan karena data order dibersihkan."}})
                deleted["notifications_cancelled"] = res.modified_count
            if "orders" in cats and reset_seq:
                deleted["order_seq_counters"] = (await db.system_settings.delete_many(SEQ_FILTER)).deleted_count
            for i, name in enumerate(files):
                try:
                    resi_path(name).unlink(missing_ok=True)
                except OSError:
                    file_errors += 1
                if i == 0:
                    fault("resi_files")
        except Exception as e:
            log.exception("Pembersihan gagal, memulihkan dari backup")
            try:
                restored = await restore_backup(db, folder, cancel_pending=False)
                problems = await verify_restore(db, plan, files, folder)
            except Exception as re:
                restored, problems = None, [f"pemulihan error: {re}"]
            if problems:
                await _security_log(db, user, ip, categories=cats, counts=pv["counts"], backup=str(folder), deleted=deleted,
                                    result="gagal_pemulihan_otomatis", error=str(e)[:500], restored=restored, problems=problems[:20])
                raise HTTPException(status_code=500, detail=(
                    f"Pembersihan gagal dan pemulihan otomatis TIDAK terverifikasi ({'; '.join(problems[:3])}). "
                    f"Backup {folder.name} tetap disimpan. Jangan input data baru dan pulihkan manual sesuai panduan."))
            total = sum(len(v) for v in plan.values())
            await _security_log(db, user, ip, categories=cats, counts=pv["counts"], backup=str(folder), deleted=deleted,
                                result="gagal_dipulihkan", error=str(e)[:500], restored=restored, verified=True)
            raise HTTPException(status_code=500, detail=(
                f"Pembersihan gagal di tengah proses. Data sudah dikembalikan otomatis dari backup dan terverifikasi "
                f"({total} dokumen, {len(files)} foto resi). Tidak ada data yang berubah. Backup: {folder.name}."))
        deleted["resi_files"] = len(files) - file_errors
        result = "berhasil" if not file_errors else "berhasil_sebagian_file"
        await _security_log(db, user, ip, categories=cats, counts=pv["counts"], deleted=deleted, backup=str(folder),
                            reset_order_seq=reset_seq, result=result)
        return {"result": result, "categories": cats, "deleted": deleted, "backup": folder.name, "file_errors": file_errors}
    finally:
        STATE["active"] = False
        await db.system_settings.delete_one({"_id": LOCK_ID})
