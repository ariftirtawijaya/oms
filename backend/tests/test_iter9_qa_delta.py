"""Iteration 9: delta verification of cleanup hardening (QA stack ONLY, run serially):
python -m pytest -p no:xdist -o addopts='' -s test_iter9_qa_delta.py"""
import json
import shutil
import time
from datetime import datetime, timezone

import pytest
from bson import json_util

from qa_iter8_helpers import (API, BACKUP, DB, LOCK, SUPER, add_pending_notifs, diff, execute, fire_async, history, kill9,
                              login, restart_backend, snapshot, wait_lock)

CATS3 = ["orders", "products", "notifications"]


@pytest.fixture(scope="module", autouse=True)
def prep():
    restart_backend()
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    add_pending_notifs()
    yield
    DB.system_settings.delete_one({"_id": LOCK, "by_name": "TEST_iter9"})
    restart_backend()


# Delta 1: unlisted .jsonl files dropped into a backup folder are ignored by restore (manifest-driven)
def test_unlisted_jsonl_not_restored():
    restart_backend(CLEANUP_TEST_DELAY=3)
    s = login(*SUPER)
    before = snapshot()
    fire_async(s, CATS3)
    lock = wait_lock(lambda l: l.get("state") == "deleting" and DB.orders.count_documents({}) == 0)
    kill9()
    folder = BACKUP / lock["backup"]
    rogue_user = {"_id": "TEST_iter9_rogue_user", "email": "rogue@x.test", "role": "admin", "is_super_admin": True}
    (folder / "TEST_iter9_rogue.jsonl").write_text(json_util.dumps({"_id": "TEST_iter9_rogue", "x": 1}) + "\n")
    (folder / "users.jsonl").write_text(json_util.dumps(rogue_user) + "\n")  # users not part of CATS3 manifest
    man = json.loads((folder / "manifest.json").read_text())
    assert "users" not in man["collections"] and "TEST_iter9_rogue" not in man["collections"]
    restart_backend()
    try:
        assert DB.system_settings.find_one({"_id": LOCK}) is None
        assert DB["TEST_iter9_rogue"].count_documents({}) == 0
        assert DB.users.find_one({"_id": "TEST_iter9_rogue_user"}) is None
        assert diff(before, snapshot()) == []
        h = history(login(*SUPER))[0]
        assert h["result"] == "dipulihkan_setelah_restart"
    finally:
        DB["TEST_iter9_rogue"].drop()
        DB.users.delete_one({"_id": "TEST_iter9_rogue_user"})


# Delta 2: partial backup folder renamed INCOMPLETE-* on restart with journal state=backup
def test_partial_backup_renamed_incomplete():
    name = "cleanup-test-partial"
    for p in (BACKUP / name, BACKUP / f"INCOMPLETE-{name}"):
        shutil.rmtree(p, ignore_errors=True)
    (BACKUP / name / "files" / "resi").mkdir(parents=True)
    (BACKUP / name / "orders.jsonl").write_text("{}\n")
    DB.system_settings.insert_one({"_id": LOCK, "state": "backup", "backup": name, "categories": ["orders"],
                                   "by_name": "TEST_iter9", "started_at": datetime.now(timezone.utc)})
    restart_backend()
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    assert not (BACKUP / name).exists()
    assert (BACKUP / f"INCOMPLETE-{name}" / "orders.jsonl").is_file()
    h = history(login(*SUPER))[0]
    assert h["result"] == "dibatalkan_terputus_saat_backup" and h["backup"] == name
    shutil.rmtree(BACKUP / f"INCOMPLETE-{name}", ignore_errors=True)


# Delta 3: history shows folder names only; audit-only cleanup has no resi_files
def test_history_folder_names_and_audit_only():
    restart_backend()
    s = login(*SUPER)
    r = execute(s, ["audit"], reset=False)
    assert r.status_code == 200, r.text
    assert "resi_files" not in r.json()["deleted"], r.json()
    assert "/" not in r.json()["backup"]
    hist = history(s)
    assert "resi_files" not in (hist[0].get("deleted") or {})
    for h in hist:
        if h.get("backup"):
            assert "/" not in h["backup"], h["backup"]
    raw = list(DB.security_logs.find({"backup": {"$regex": "/"}}))
    print("security_logs with path in backup:", len(raw))


# Delta 4: rollback error detail has no double punctuation
def test_error_detail_punctuation():
    restart_backend(CLEANUP_TEST_FAIL_AFTER="orders")
    s = login(*SUPER)
    before = snapshot()
    r = execute(s, ["orders"])
    print("detail:", r.json()["detail"])
    assert r.status_code == 500
    d = r.json()["detail"]
    assert ".)" not in d and ".." not in d and ". ." not in d
    assert diff(before, snapshot()) == []
    restart_backend()
