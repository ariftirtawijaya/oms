"""QA-only: prove the first resi file is really deleted (inode changes after auto-restore) with CLEANUP_TEST_FAIL_AFTER=resi_files."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from test_iter7_qa_rollback import RESI, SUPER, execute, login, restart_backend, snapshot, diff  # noqa: E402

restart_backend(CLEANUP_TEST_FAIL_AFTER="resi_files")
before_ino = {p.name: p.stat().st_ctime_ns for p in RESI.glob("*")}
snap = snapshot()
s = login(*SUPER)
r = execute(s, ["orders"])
after_ino = {p.name: p.stat().st_ctime_ns for p in RESI.glob("*")}
print(r.status_code, r.json()["detail"][:120])
print("files with changed inode (deleted+restored):", [n for n in before_ino if before_ino[n] != after_ino.get(n)])
print("diff:", diff(snap, snapshot()))
restart_backend()
print("backend restarted without fault env")
