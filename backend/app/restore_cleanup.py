"""Pulihkan backup pembersihan data: python -m app.restore_cleanup /data/backups/cleanup-YYYYMMDD-HHMMSS-xxxxxx"""
import asyncio
import sys
from pathlib import Path

from bson import json_util

from app.db import db
from app.services.cleanup import restore_backup
from app.services.storage import resi_path


async def main(folder: Path):
    if not (folder / "manifest.json").is_file():
        sys.exit(f"Folder backup tidak valid: {folder}")
    print("Hasil pemulihan:", await restore_backup(db, folder))
    problems = []
    for path in sorted(folder.glob("*.jsonl")):
        ids = [json_util.loads(line)["_id"] for line in path.open(encoding="utf-8") if line.strip()]
        present = await db[path.stem].count_documents({"_id": {"$in": ids}})
        print(f"Verifikasi {path.stem}: {present}/{len(ids)} dokumen ada")
        if present != len(ids):
            problems.append(path.stem)
    missing = [p.name for p in (folder / "files" / "resi").glob("*") if not resi_path(p.name).is_file()]
    print(f"Verifikasi foto resi: {len(missing)} file belum kembali")
    if problems or missing:
        sys.exit("PEMULIHAN BELUM LENGKAP. Backup tetap disimpan; periksa pesan di atas.")
    print("Pemulihan selesai dan terverifikasi.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python -m app.restore_cleanup <folder-backup>")
    asyncio.run(main(Path(sys.argv[1])))
