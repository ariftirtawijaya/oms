import asyncio
import hashlib
import json
import logging
import os
import secrets
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from bson import json_util
from bson.json_util import JSONOptions
from fastapi import HTTPException
from pymongo import ReplaceOne
from pymongo.errors import BulkWriteError

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
BATCH = 500
# Status jurnal (system_settings._id=cleanup_lock): backup -> deleting -> done | rolling_back -> needs_manual


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


# ---------- Backup (streaming, SHA-256) ----------

def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_backup(path: Path):
    """Baca JSONL per batch agar RAM tetap kecil."""
    batch = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                batch.append(json_util.loads(line, json_options=JSON_OPTS))
                if len(batch) >= BATCH:
                    yield batch
                    batch = []
    if batch:
        yield batch


async def _dump(db, folder: Path, coll: str, flt: dict) -> tuple:
    path = folder / f"{coll}.jsonl"
    h, ids = hashlib.sha256(), []
    with path.open("wb") as f:
        async for d in db[coll].find(flt).batch_size(BATCH):
            line = (json_util.dumps(d) + "\n").encode("utf-8")
            f.write(line)
            h.update(line)
            ids.append(d["_id"])
        f.flush()
        os.fsync(f.fileno())
    path.chmod(0o600)
    sha = h.hexdigest()
    if file_sha(path) != sha:
        raise IOError(f"Checksum backup {path.name} tidak cocok.")
    i = 0
    for batch in _iter_backup(path):
        for d in batch:
            if i >= len(ids) or d["_id"] != ids[i]:
                raise IOError(f"Isi backup {path.name} tidak cocok dengan database.")
            i += 1
    if i != len(ids):
        raise IOError(f"Jumlah dokumen backup {path.name} tidak cocok.")
    return ids, sha


async def _backup(db, cats: List[str], reset_seq: bool, folder: Path) -> tuple:
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    (folder / "files" / "resi").mkdir(mode=0o700, parents=True)
    targets = [t for c in cats for t in TARGETS[c]]
    cancel_mode = "orders" in cats and "notifications" not in cats
    if cancel_mode:
        targets.append(("notification_logs", PENDING_ORDER_NOTIF))
    if "orders" in cats and reset_seq:
        targets.append(("system_settings", SEQ_FILTER))
    ids_by_coll: Dict[str, list] = {}
    colls: Dict[str, dict] = {}
    for coll, flt in targets:
        ids, sha = await _dump(db, folder, coll, flt)
        ids_by_coll[coll] = ids
        colls[coll] = {"count": len(ids), "sha256": sha}
    files = await _resi_files(db) if "orders" in cats else []
    file_hashes = {}
    for name in files:
        src, dst = resi_path(name), folder / "files" / "resi" / name
        shutil.copy2(src, dst)
        dst.chmod(0o600)
        sha = file_sha(src)
        if file_sha(dst) != sha:
            raise IOError(f"Checksum backup foto {name} tidak cocok.")
        file_hashes[name] = sha
    manifest = {"created_at": now_utc().isoformat(), "categories": cats, "reset_order_seq": reset_seq,
                "collections": colls, "files": file_hashes, "complete": True}
    mpath = folder / "manifest.json"
    with mpath.open("w") as f:
        json.dump(manifest, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    mpath.chmod(0o600)
    cancel_ids = ids_by_coll.pop("notification_logs") if cancel_mode else []
    return ids_by_coll, cancel_ids, files


def verify_backup_integrity(folder: Path) -> List[str]:
    """Cek manifest + SHA-256 seluruh file backup sebelum dipakai untuk pemulihan."""
    mpath = folder / "manifest.json"
    if not mpath.is_file():
        return [f"manifest backup {folder.name} tidak ditemukan"]
    m = json.loads(mpath.read_text())
    if not m.get("complete"):
        return [f"backup {folder.name} tidak lengkap"]
    problems = []
    for coll, info in m["collections"].items():
        p = folder / f"{coll}.jsonl"
        if not p.is_file() or file_sha(p) != info["sha256"]:
            problems.append(f"checksum {coll}.jsonl tidak cocok")
    for name, sha in m["files"].items():
        p = folder / "files" / "resi" / name
        if not p.is_file() or file_sha(p) != sha:
            problems.append(f"checksum foto {name} tidak cocok")
    return problems


# ---------- Restore & verifikasi ----------

def _manifest(folder: Path) -> dict:
    return json.loads((folder / "manifest.json").read_text())


async def restore_backup(db, folder: Path, cancel_pending: bool = True) -> dict:
    """Upsert per _id dari backup. Manual (cancel_pending=True): antrean WA lama tidak diaktifkan lagi."""
    if config.CLEANUP_TEST_FAIL_RESTORE:
        raise RuntimeError("Simulasi kegagalan pemulihan (khusus pengujian).")
    restored, conflicts = {}, []
    m = _manifest(folder)
    for coll in m["collections"]:
        path, n = folder / f"{coll}.jsonl", 0
        for batch in _iter_backup(path):
            ops = []
            for doc in batch:
                if cancel_pending and coll == "notification_logs" and doc.get("status") in ("pending", "sending"):
                    doc.update(status="cancelled", last_error="Dibatalkan saat pemulihan backup agar tidak terkirim ulang.")
                ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
            try:
                await db[coll].bulk_write(ops, ordered=False)
                n += len(ops)
            except BulkWriteError as e:
                errs = e.details.get("writeErrors", [])
                n += len(ops) - len(errs)
                conflicts.extend(f"{coll}: {str(x.get('errmsg'))[:150]}" for x in errs[:20])
        restored[coll] = n
    files = 0
    for name in m["files"]:
        src, dst = folder / "files" / "resi" / name, resi_path(name)
        if not dst.is_file() or file_sha(dst) != file_sha(src):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        files += 1
    restored["resi_files"] = files
    if conflicts:
        restored["conflicts"] = conflicts
    return restored


async def verify_against_backup(db, folder: Path, manual: bool = False) -> List[str]:
    """Setiap dokumen di backup harus ada & identik di database; setiap foto harus sama checksum-nya."""
    problems = []
    m = _manifest(folder)
    for coll in m["collections"]:
        path, missing, changed = folder / f"{coll}.jsonl", 0, 0
        for batch in _iter_backup(path):
            found = {d["_id"]: d for d in await db[coll].find({"_id": {"$in": [d["_id"] for d in batch]}}).to_list(None)}
            for d in batch:
                cur = found.get(d["_id"])
                if cur is None:
                    missing += 1
                    continue
                if manual and coll == "notification_logs" and d.get("status") in ("pending", "sending"):
                    d = {**d, "status": cur.get("status"), "last_error": cur.get("last_error")}
                changed += cur != d
        if missing:
            problems.append(f"{coll}: {missing} dokumen tidak kembali")
        if changed:
            problems.append(f"{coll}: {changed} dokumen berbeda dari backup")
    for name, sha in m["files"].items():
        p = resi_path(name)
        if not p.is_file() or file_sha(p) != sha:
            problems.append(f"foto resi {name} tidak kembali utuh")
    return problems


async def restore_and_verify(db, folder: Path, manual: bool = False) -> tuple:
    integrity = verify_backup_integrity(folder)
    if integrity:
        return None, integrity
    try:
        restored = await restore_backup(db, folder, cancel_pending=manual)
        return restored, await verify_against_backup(db, folder, manual=manual)
    except Exception as e:
        return None, [f"pemulihan error: {e}"]


# ---------- Jurnal & eksekusi ----------

def block(backup: Optional[str], reason: str):
    STATE["blocked"] = {
        "backup": backup,
        "message": (f"Pembersihan data terputus dan pemulihan otomatis tidak terverifikasi ({reason}). "
                    f"Semua perubahan data diblokir. Pulihkan manual dari backup {backup or '-'} sesuai panduan, "
                    f"lalu restart backend."),
    }


async def _set_state(db, state: str, **fields):
    await db.system_settings.update_one({"_id": LOCK_ID}, {"$set": {"state": state, "updated_at": now_utc(), **fields}})


async def _acquire_lock(db, user: dict, cats: List[str]):
    try:
        await db.system_settings.insert_one({"_id": LOCK_ID, "state": "backup", "started_at": now_utc(), "updated_at": now_utc(),
                                             "by": user["_id"], "by_name": user.get("name"), "by_email": user.get("email"),
                                             "categories": cats, "backup": None})
    except Exception:
        lock = await db.system_settings.find_one({"_id": LOCK_ID}) or {}
        if lock.get("state") == "needs_manual":
            raise HTTPException(status_code=409, detail=f"Pembersihan sebelumnya belum dipulihkan (backup {lock.get('backup')}). Pulihkan manual terlebih dahulu.")
        raise HTTPException(status_code=409, detail="Pembersihan data lain sedang berjalan. Coba lagi beberapa saat.")


async def _security_log(db, actor: dict, ip: str, **data):
    await db.security_logs.insert_one({"action": "pembersihan_data", "actor_id": actor.get("_id") or actor.get("by"),
                                       "actor_name": actor.get("name") or actor.get("by_name"),
                                       "actor_email": actor.get("email") or actor.get("by_email"),
                                       "ip": ip, "created_at": now_utc(), **data})


async def _test_point(point: str):
    if config.CLEANUP_TEST_DELAY:
        await asyncio.sleep(config.CLEANUP_TEST_DELAY)
    if config.CLEANUP_TEST_FAIL_AFTER == point:
        raise RuntimeError(f"Simulasi kegagalan setelah {point} (khusus pengujian).")


async def _delete(db, cats: List[str], reset_seq: bool, ids_by_coll: Dict[str, list], cancel_ids: list, files: List[str]) -> dict:
    deleted: Dict[str, int] = {}
    for c in cats:
        for coll, _ in TARGETS[c]:
            if coll in deleted:
                continue
            ids, n = ids_by_coll.get(coll, []), 0
            for i in range(0, len(ids), 1000):
                n += (await db[coll].delete_many({"_id": {"$in": ids[i:i + 1000]}})).deleted_count
            deleted[coll] = n
            await _test_point(coll)
    if cancel_ids:
        res = await db.notification_logs.update_many(
            {"_id": {"$in": cancel_ids}, "status": {"$in": ["pending", "sending"]}},
            {"$set": {"status": "cancelled", "last_error": "Dibatalkan karena data order dibersihkan."}})
        deleted["notifications_cancelled"] = res.modified_count
    if "orders" in cats and reset_seq:
        deleted["order_seq_counters"] = (await db.system_settings.delete_many(SEQ_FILTER)).deleted_count
    for i, name in enumerate(files):
        if config.CLEANUP_TEST_FAIL_AFTER == "resi_unlink" and i == min(1, len(files) - 1):
            raise OSError(f"Simulasi gagal menghapus foto {name} (khusus pengujian).")
        try:
            resi_path(name).unlink(missing_ok=True)
        except OSError as e:
            raise OSError(f"Foto resi {name} gagal dihapus: {e}")
        if i == 0:
            await _test_point("resi_files")
    if "orders" in cats:
        deleted["resi_files"] = len(files)
    return deleted


async def execute(db, user: dict, ip: str, cats: List[str], reset_seq: bool) -> dict:
    pv = await preview(db, cats, reset_seq)
    if pv["blocking"]:
        raise HTTPException(status_code=422, detail=" ".join(pv["blocking"]))
    cats = pv["categories"]
    await _acquire_lock(db, user, cats)
    STATE["active"] = True
    stamp = now_utc().astimezone(JKT).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    folder = config.BACKUP_DIR / f"cleanup-{stamp}"
    release = True
    try:
        await asyncio.sleep(1)
        await _set_state(db, "backup", backup=folder.name)
        try:
            ids_by_coll, cancel_ids, files = await _backup(db, cats, reset_seq, folder)
        except Exception as e:
            log.exception("Backup pembersihan gagal")
            await _security_log(db, user, ip, categories=cats, counts=pv["counts"], result="dibatalkan_backup_gagal", error=str(e)[:500])
            raise HTTPException(status_code=500, detail="Backup gagal dibuat atau gagal diverifikasi, sehingga tidak ada data yang dihapus. Periksa izin folder backup di server.")
        await _set_state(db, "deleting")
        try:
            deleted = await _delete(db, cats, reset_seq, ids_by_coll, cancel_ids, files)
        except Exception as e:
            log.exception("Pembersihan gagal, memulihkan dari backup")
            await _set_state(db, "rolling_back", error=str(e)[:500])
            restored, problems = await restore_and_verify(db, folder)
            if problems:
                release = False
                await _set_state(db, "needs_manual", problems=problems[:20])
                block(folder.name, "; ".join(problems[:3]))
                await _security_log(db, user, ip, categories=cats, counts=pv["counts"], backup=folder.name,
                                    result="gagal_pemulihan_otomatis", error=str(e)[:500], restored=restored, problems=problems[:20])
                raise HTTPException(status_code=500, detail=(
                    f"Pembersihan gagal dan pemulihan otomatis TIDAK terverifikasi ({'; '.join(problems[:3])}). "
                    f"Backup {folder.name} tetap disimpan. Perubahan data diblokir sampai dipulihkan manual sesuai panduan."))
            await _security_log(db, user, ip, categories=cats, counts=pv["counts"], backup=folder.name,
                                result="gagal_dipulihkan", error=str(e)[:500], restored=restored, verified=True)
            raise HTTPException(status_code=500, detail=(
                f"Pembersihan gagal ({str(e)[:120].rstrip('.')}). Data dan foto resi sudah dikembalikan otomatis dari backup dan "
                f"terverifikasi. Tidak ada data yang berubah. Backup: {folder.name}."))
        await _set_state(db, "done", deleted=deleted)
        await _security_log(db, user, ip, categories=cats, counts=pv["counts"], deleted=deleted, backup=folder.name,
                            reset_order_seq=reset_seq, result="berhasil")
        return {"result": "berhasil", "categories": cats, "deleted": deleted, "backup": folder.name}
    finally:
        STATE["active"] = False
        if release:
            await db.system_settings.delete_one({"_id": LOCK_ID})


async def recover_on_startup(db):
    """Dipanggil saat backend start: tangani cleanup yang terputus (mis. container mati mendadak)."""
    lock = await db.system_settings.find_one({"_id": LOCK_ID})
    if not lock:
        return
    state, backup = lock.get("state"), lock.get("backup")
    log.warning("Ditemukan jurnal pembersihan belum tuntas: state=%s backup=%s", state, backup)
    if state == "backup":
        partial = config.BACKUP_DIR / backup if backup else None
        if partial and partial.is_dir():
            partial.rename(partial.with_name(f"INCOMPLETE-{backup}"))
        await _security_log(db, lock, "sistem", categories=lock.get("categories"), backup=backup,
                            result="dibatalkan_terputus_saat_backup")
        await db.system_settings.delete_one({"_id": LOCK_ID})
        return
    if state == "done":
        await _security_log(db, lock, "sistem", categories=lock.get("categories"), backup=backup, deleted=lock.get("deleted"),
                            result="selesai_dicatat_saat_restart")
        await db.system_settings.delete_one({"_id": LOCK_ID})
        return
    if not backup:
        problems = ["identitas backup tidak tercatat"]
        restored = None
    else:
        restored, problems = await restore_and_verify(db, config.BACKUP_DIR / backup)
    if problems:
        await _set_state(db, "needs_manual", problems=problems[:20])
        block(backup, "; ".join(problems[:3]))
        if state != "needs_manual":
            await _security_log(db, lock, "sistem", categories=lock.get("categories"), backup=backup,
                                result="gagal_pemulihan_otomatis", problems=problems[:20])
        log.error("Pemulihan otomatis setelah restart gagal: %s", problems)
        return
    await _security_log(db, lock, "sistem", categories=lock.get("categories"), backup=backup, restored=restored,
                        result="dipulihkan_setelah_restart", verified=True)
    await db.system_settings.delete_one({"_id": LOCK_ID})
    log.warning("Pembersihan terputus berhasil dipulihkan dari backup %s", backup)
