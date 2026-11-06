"""Pulihkan backup pembersihan data: python -m app.restore_cleanup /data/backups/cleanup-YYYYMMDD-HHMMSS-xxxxxx"""
import asyncio
import sys
from pathlib import Path

from app.db import db
from app.services.cleanup import LOCK_ID, _security_log, restore_and_verify, verify_backup_integrity


async def main(folder: Path):
    integrity = verify_backup_integrity(folder)
    print("Integritas backup (SHA-256):", "OK" if not integrity else integrity)
    if integrity:
        sys.exit("Backup rusak atau tidak lengkap; pemulihan dibatalkan.")
    restored, problems = await restore_and_verify(db, folder, manual=True)
    print("Hasil pemulihan:", restored)
    if problems:
        print("Masalah verifikasi:", problems)
        sys.exit("PEMULIHAN BELUM LENGKAP. Backup tetap disimpan; periksa pesan di atas.")
    print("Verifikasi: semua dokumen identik dengan backup dan semua foto resi cocok (SHA-256).")
    lock = await db.system_settings.find_one({"_id": LOCK_ID})
    if lock and lock.get("backup") == folder.name:
        await _security_log(db, lock, "cli", categories=lock.get("categories"), backup=folder.name, restored=restored,
                            result="dipulihkan_manual", verified=True)
        await db.system_settings.delete_one({"_id": LOCK_ID})
        print("Jurnal pembersihan yang terputus sudah ditutup. Jalankan: sudo docker compose restart backend")
    print("Pemulihan selesai dan terverifikasi.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python -m app.restore_cleanup <folder-backup>")
    asyncio.run(main(Path(sys.argv[1])))
