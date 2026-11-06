"""Iteration 8: cleanup crash safety / journal / integrity (QA stack ONLY). Run serially:
pytest -p no:xdist -n 0 -s test_iter8_qa_crash.py  (restarts QA backend on port 8101 with CLEANUP_TEST_* env)."""
import hashlib
import json
import os
import stat
import subprocess
import time
from datetime import datetime, timezone

import pytest
import requests

from qa_iter8_helpers import (ADMIN2, API, BACKUP, DB, LOCK, RESELLER, RESI, SUPER, add_pending_notifs, add_photo_shipments,
                              cli, diff, execute, fire_async, history, kill9, login, restart_backend, snapshot, wait_lock)

CATS3 = ["orders", "products", "notifications"]


def log_text():
    return open("/tmp/qa/backend.log").read()


@pytest.fixture(scope="module", autouse=True)
def prep():
    restart_backend()
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    s = login(*SUPER)
    if len(list(RESI.glob("*"))) < 3:
        add_photo_shipments(s, 2)
    add_pending_notifs()
    yield
    restart_backend()


# A: unlink failure -> full rollback verified
def test_A_unlink_failure_rollback():
    assert len(list(RESI.glob("*"))) >= 2
    restart_backend(CLEANUP_TEST_FAIL_AFTER="resi_unlink")
    s = login(*SUPER)
    before = snapshot()
    r = execute(s, ["orders"])
    after = snapshot()
    print("A:", r.status_code, r.text[:300])
    assert r.status_code == 500
    assert "dikembalikan otomatis dari backup dan terverifikasi" in r.json()["detail"]
    assert diff(before, after) == []
    h = history(s)[0]
    assert h["result"] == "gagal_dipulihkan" and h.get("verified") is True
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    assert DB.security_logs.count_documents({"result": "berhasil_sebagian_file"}) == 0
    g = subprocess.run("grep -rn berhasil_sebagian_file /app/backend/app /app/backend/server.py", shell=True, capture_output=True, text=True)
    assert g.stdout == "", g.stdout


# B1: kill -9 while deleting (collections gone) -> restored on restart
def test_B1_kill_during_deleting():
    restart_backend(CLEANUP_TEST_DELAY=3)
    s = login(*SUPER)
    before = snapshot()
    fire_async(s, CATS3)
    lock = wait_lock(lambda l: l.get("state") == "deleting" and DB.orders.count_documents({}) == 0
                     and DB.order_payments.count_documents({}) == 0)
    kill9()
    assert DB.orders.count_documents({}) == 0
    restart_backend()
    assert "dipulihkan dari backup" in log_text()
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    after = snapshot()
    assert diff(before, after) == [], diff(before, after)
    assert DB.notification_logs.count_documents({"kind": "TEST_iter8_pending", "status": "pending"}) == 2
    s = login(*SUPER)
    h = history(s)[0]
    assert h["result"] == "dipulihkan_setelah_restart" and h.get("backup") == lock["backup"]
    st = s.get(f"{API}/settings/cleanup/status").json()
    assert st["blocked"] is None and st["journal"] is None
    r = s.put(f"{API}/settings/branding", json=s.get(f"{API}/settings/branding").json())
    print("branding put after recover:", r.status_code)
    assert r.status_code in (200, 422)


# B2: kill -9 after the first resi photo was unlinked -> photo restored on restart (SHA identical)
def test_B2_kill_after_photo_unlink():
    restart_backend(CLEANUP_TEST_DELAY=3)
    s = login(*SUPER)
    before = snapshot()
    n = len(before["files"])
    fire_async(s, CATS3)
    wait_lock(lambda l: l.get("state") == "deleting" and len(list(RESI.glob("*"))) < n, timeout=90)
    kill9()
    assert len(list(RESI.glob("*"))) < n
    restart_backend()
    after = snapshot()
    assert diff(before, after) == [], diff(before, after)
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    assert history(login(*SUPER))[0]["result"] == "dipulihkan_setelah_restart"


# C1: real kill during backup phase (1s window with state=backup)
def test_C1_kill_during_backup():
    restart_backend()
    s = login(*SUPER)
    before = snapshot()
    fire_async(s, ["orders"])
    wait_lock(lambda l: l.get("state") == "backup", timeout=10)
    kill9()
    restart_backend()
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    assert diff(before, snapshot()) == []
    assert history(login(*SUPER))[0]["result"] == "dibatalkan_terputus_saat_backup"


@pytest.mark.parametrize("state,expected", [("backup", "dibatalkan_terputus_saat_backup"), ("done", "selesai_dicatat_saat_restart")])
def test_C2_manual_journal(state, expected):
    before = snapshot()
    DB.system_settings.insert_one({"_id": LOCK, "state": state, "backup": None, "categories": ["orders"],
                                   "by_name": "TEST_journal", "started_at": datetime.now(timezone.utc)})
    restart_backend()
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    assert diff(before, snapshot()) == []
    assert history(login(*SUPER))[0]["result"] == expected


def _kill_in_deleting():
    restart_backend(CLEANUP_TEST_DELAY=3)
    s = login(*SUPER)
    before = snapshot()
    fire_async(s, CATS3)
    lock = wait_lock(lambda l: l.get("state") == "deleting" and DB.orders.count_documents({}) == 0)
    kill9()
    return before, BACKUP / lock["backup"]


def _assert_blocked(folder):
    s = login(*SUPER)  # login still works
    st = s.get(f"{API}/settings/cleanup/status").json()
    assert st["blocked"] and st["blocked"]["backup"] == folder.name, st
    assert st["journal"]["state"] == "needs_manual"
    assert DB.system_settings.find_one({"_id": LOCK})["state"] == "needs_manual"
    r = s.post(f"{API}/products", json={"name": "TEST_blocked", "voltage": "12", "price": 1000})
    assert r.status_code == 503 and folder.name not in r.text and "pemeliharaan data" in r.json()["detail"], r.text  # iter11 generic
    r = s.post(f"{API}/orders/x/payments", json={"amount": 1, "idempotency_key": "k"})
    assert r.status_code == 503
    r = s.put(f"{API}/settings/branding", json={})
    assert r.status_code == 503
    r = execute(s, ["audit"], reset=False)
    assert r.status_code in (409, 503), r.text
    assert s.get(f"{API}/products").status_code == 200
    assert s.get(f"{API}/orders?page=1&limit=10").status_code == 200
    rs = login(*RESELLER)
    assert rs.get(f"{API}/orders?page=1&limit=10").status_code == 200
    assert rs.post(f"{API}/orders", json={"items": [], "idempotency_key": "x"}).status_code == 503
    a2 = login(*ADMIN2)
    assert a2.get(f"{API}/settings/cleanup/status").json()["blocked"]
    assert rs.get(f"{API}/settings/cleanup/status").status_code == 403
    return s


# D1: restore fails after restart -> needs_manual -> CLI -> restart unblocks
def test_D1_unrecoverable_then_cli():
    before, folder = _kill_in_deleting()
    restart_backend(CLEANUP_TEST_FAIL_RESTORE=1)
    _assert_blocked(folder)
    # WA worker paused: due pending notif must stay pending
    nid = DB.notification_logs.insert_one({"kind": "TEST_iter8_due", "target": "628000000098", "message": "TEST_due",
                                           "order_id": None, "status": "pending", "attempts": 0,
                                           "next_attempt_at": datetime.now(timezone.utc),
                                           "created_at": datetime.now(timezone.utc)}).inserted_id
    time.sleep(12)
    assert DB.notification_logs.find_one({"_id": nid})["status"] == "pending"
    DB.notification_logs.delete_one({"_id": nid})
    out = cli(folder)
    print(out.stdout, out.stderr)
    assert out.returncode == 0, out.stderr
    assert "Integritas backup (SHA-256): OK" in out.stdout and "Pemulihan selesai dan terverifikasi." in out.stdout
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    restart_backend()
    s = login(*SUPER)
    assert s.get(f"{API}/settings/cleanup/status").json()["blocked"] is None
    assert any(h["result"] == "dipulihkan_manual" for h in history(s)[:3])
    after = snapshot()
    assert diff(before, after, skip=("notification_logs",)) == [], diff(before, after)
    assert set(before["notification_logs"]) == set(after["notification_logs"])
    assert DB.notification_logs.count_documents({"kind": "TEST_iter8_pending", "status": "cancelled"}) == 2
    # reset pending for later scenarios
    DB.notification_logs.update_many({"kind": "TEST_iter8_pending"}, {"$set": {"status": "pending"}, "$unset": {"last_error": ""}})
    r = s.post(f"{API}/products", json={"name": "TEST_iter8_after_unblock", "voltage": "12", "price": 1000})
    assert r.status_code in (200, 201), r.text
    DB.products.delete_one({"name": "TEST_iter8_after_unblock"})


# D2: tampered backup -> blocked; CLI refuses; restoring original file -> restart recovers
def test_D2_tampered_backup():
    before, folder = _kill_in_deleting()
    target = folder / "orders.jsonl"
    original = target.read_bytes()
    target.write_bytes(original + b"\n")
    restart_backend()
    _assert_blocked(folder)
    out = cli(folder)
    print(out.stdout, out.stderr)
    assert out.returncode != 0 and "Backup rusak atau tidak lengkap" in (out.stdout + out.stderr)
    restart_backend()
    _assert_blocked(folder)
    target.write_bytes(original)
    restart_backend()
    s = login(*SUPER)
    assert s.get(f"{API}/settings/cleanup/status").json()["blocked"] is None
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    assert diff(before, snapshot()) == []
    assert history(s)[0]["result"] == "dipulihkan_setelah_restart"


# E: manifest + checksums + permissions
def test_E_manifest_integrity():
    folders = sorted(BACKUP.glob("cleanup-*"), key=lambda p: p.stat().st_mtime)
    checked = 0
    for f in folders[-4:]:
        m = f / "manifest.json"
        if not m.is_file():
            continue
        man = json.loads(m.read_text())
        assert man["complete"] is True
        for coll, info in man["collections"].items():
            p = f / f"{coll}.jsonl"
            assert hashlib.sha256(p.read_bytes()).hexdigest() == info["sha256"]
            assert sum(1 for line in p.open() if line.strip()) == info["count"]
            assert stat.S_IMODE(p.stat().st_mode) == 0o600
        # manifest v2 (iter10): files = {count, sha256 of files.jsonl}; files.jsonl lines {name, sha256}
        assert man["version"] == 2
        fl = f / "files.jsonl"
        if man["files"]["count"]:
            assert hashlib.sha256(fl.read_bytes()).hexdigest() == man["files"]["sha256"]
            assert stat.S_IMODE(fl.stat().st_mode) == 0o600
            lines = [json.loads(x) for x in fl.open() if x.strip()]
            assert len(lines) == man["files"]["count"]
            for d in lines:
                p = f / "files" / "resi" / d["name"]
                assert hashlib.sha256(p.read_bytes()).hexdigest() == d["sha256"]
                assert stat.S_IMODE(p.stat().st_mode) == 0o600
        assert stat.S_IMODE(f.stat().st_mode) == 0o700
        assert stat.S_IMODE(m.stat().st_mode) == 0o600
        checked += 1
    assert checked >= 1


# F: normal cleanup + authz
def test_F_normal_cleanup_and_authz():
    restart_backend()
    s = login(*SUPER)
    body = {"categories": ["orders"], "reset_order_seq": False}
    assert login(*ADMIN2).post(f"{API}/settings/cleanup/preview", json=body).status_code == 403
    assert login(*RESELLER).post(f"{API}/settings/cleanup/preview", json=body).status_code == 403
    assert login(*ADMIN2).post(f"{API}/settings/cleanup/execute", json={**body, "confirm_text": "HAPUS DATA", "password": "x"}).status_code == 403
    pv = s.post(f"{API}/settings/cleanup/preview", json={"categories": ["resellers"], "reset_order_seq": False}).json()
    assert pv["blocking"]
    r = execute(s, ["audit"], reset=False)
    assert r.status_code == 200 and r.json()["result"] == "berhasil", r.text
    assert DB.system_settings.find_one({"_id": LOCK}) is None
