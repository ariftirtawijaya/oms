"""Pulihkan backup pembersihan data: python -m app.restore_cleanup /data/backups/cleanup-YYYYMMDD-HHMMSS-xxxxxx"""
import asyncio
import sys
from pathlib import Path

from app.db import db
from app.services.cleanup import restore_backup


async def main(folder: Path):
    if not (folder / "manifest.json").is_file():
        sys.exit(f"Folder backup tidak valid: {folder}")
    print(await restore_backup(db, folder))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python -m app.restore_cleanup <folder-backup>")
    asyncio.run(main(Path(sys.argv[1])))
