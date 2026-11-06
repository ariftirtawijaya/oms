"""Pulihkan backup pembersihan data: python -m app.restore_cleanup /data/backups/cleanup-YYYYMMDD-HHMMSS-xxxxxx"""
import asyncio
import sys
from pathlib import Path

from bson import json_util

from app.db import db
from app.services.cleanup import JSON_OPTS, file_sha, restore_backup
from app.services.storage import resi_path


async def main(folder: Path):
    if not (folder / "manifest.json").is_file():
        sys.exit(f"Folder backup tidak valid: {folder}")
    print("Hasil pemulihan:", await restore_backup(db, folder))
    problems = []
    for path in sorted(folder.glob("*.jsonl")):
        docs = [json_util.loads(line, json_options=JSON_OPTS) for line in path.open(encoding="utf-8") if line.strip()]
        found = {d["_id"]: d for d in await db[path.stem].find({"_id": {"$in": [d["_id"] for d in docs]}}).to_list(None)}
        same = 0
        for d in docs:
            cur = found.get(d["_id"])
            if cur is not None and path.stem == "notification_logs" and d.get("status") in ("pending", "sending"):
                d = {**d, "status": cur.get("status"), "last_error": cur.get("last_error")}
            same += cur == d
        print(f"Verifikasi {path.stem}: {len(found)}/{len(docs)} dokumen ada, {same}/{len(docs)} isinya identik")
        if same != len(docs):
            problems.append(path.stem)
    bad = [p.name for p in (folder / "files" / "resi").glob("*")
           if not resi_path(p.name).is_file() or file_sha(resi_path(p.name)) != file_sha(p)]
    print(f"Verifikasi foto resi: {len(bad)} file belum kembali utuh")
    if problems or bad:
        sys.exit("PEMULIHAN BELUM LENGKAP. Backup tetap disimpan; periksa pesan di atas.")
    print("Pemulihan selesai dan terverifikasi.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python -m app.restore_cleanup <folder-backup>")
    asyncio.run(main(Path(sys.argv[1])))
