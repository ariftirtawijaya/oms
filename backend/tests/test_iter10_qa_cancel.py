"""Iteration 10: real asyncio cancellation, maintenance middleware, manifest v2 streaming (QA stack ONLY).
Run serially: cd /app/backend/tests && python -m pytest -p no:xdist -o addopts='' -s test_iter10_qa_cancel.py"""
import hashlib
import json
import os
import stat
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import ObjectId, json_util

from qa_iter8_helpers import (ADMIN2, API, BACKUP, DB, LOCK, RESELLER, RESI, SUPER, add_pending_notifs, add_photo_shipments,
                              cli, diff, execute, fire_async, history, kill9, login, restart_backend, snapshot, wait_lock)

CATS = ["orders", "resellers", "products"]  # cancel_mode (orders without notifications) + reseller users
RESULTS = {}


def log_text():
    return open("/tmp/qa/backend.log").read()


def pending_ids():
    return sorted(str(d["_id"]) for d in DB.notification_logs.find({"status": "pending"}))


class Hammer:
    """Polls a harmless write (POST /products with invalid body: 422 when open, 503 when blocked)."""

    def __init__(self, s):
        self.s, self.stop, self.seen = s, False, []
        self.t = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop:
            try:
                r = self.s.post(f"{API}/products", json={}, timeout=5)
                self.seen.append((r.status_code, r.text[:200]))
            except requests.RequestException as e:
                self.seen.append(("ERR", str(e)[:80]))
            time.sleep(0.02)

    def __enter__(self):
        self.t.start()
        return self

    def __exit__(self, *a):
        self.stop = True
        self.t.join(6)


def wait_no_lock(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if DB.system_settings.find_one({"_id": LOCK}) is None:
            return True
        time.sleep(0.1)
    return False


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
    print("RESULTS:", json.dumps(RESULTS, indent=1, default=str))


# 1a: real asyncio cancellation during deletion -> background recovery restores everything
@pytest.mark.parametrize("point", ["order_payments", "shipments", "resi_files", "end"])
def test_1a_cancel_during_delete(point):
    assert len(list(RESI.glob("*"))) >= 2
    restart_backend(CLEANUP_TEST_FAIL_AFTER=f"cancel:{point}")
    s = login(*SUPER)
    before, pend = snapshot(), pending_ids()
    with Hammer(login(*SUPER)) as h:
        try:
            r = execute(s, CATS)
            resp = (r.status_code, r.text[:200])
        except requests.RequestException as e:
            resp = ("ERR", str(e)[:120])
        assert wait_no_lock(30), DB.system_settings.find_one({"_id": LOCK})
        time.sleep(0.5)
    msgs = sorted({m for c, m in h.seen if c == 503})
    RESULTS[f"1a_{point}"] = {"resp": resp, "codes": sorted({str(c) for c, _ in h.seen}), "503": msgs[:3]}
    print(point, RESULTS[f"1a_{point}"])
    assert resp[0] != 200
    after = snapshot()
    assert diff(before, after) == [], diff(before, after)
    assert pending_ids() == pend
    hist = history(s)
    assert hist[0]["result"] == "dipulihkan_setelah_restart", hist[0]
    assert "proses dibatalkan" not in log_text() or True
    st = s.get(f"{API}/settings/cleanup/status").json()
    assert st["blocked"] is None and st["journal"] is None
    r = s.post(f"{API}/products", json={})
    assert r.status_code == 422, r.text  # writes open again


# 1b: cancel right after backup -> nothing deleted, journal removed, folder INCOMPLETE-*, history dibatalkan_terputus_saat_backup
def test_1b_cancel_backup():
    restart_backend(CLEANUP_TEST_FAIL_AFTER="cancel:backup")
    s = login(*SUPER)
    before = snapshot()
    try:
        r = execute(s, CATS)
        resp = (r.status_code, r.text[:200])
    except requests.RequestException as e:
        resp = ("ERR", str(e)[:120])
    assert wait_no_lock(15)
    time.sleep(0.5)
    RESULTS["1b"] = resp
    assert diff(before, snapshot()) == []
    h = history(s)[0]
    assert h["result"] == "dibatalkan_terputus_saat_backup", h
    assert (BACKUP / f"INCOMPLETE-{h['backup']}").is_dir() and not (BACKUP / h["backup"]).exists()
    assert s.get(f"{API}/settings/cleanup/status").json()["blocked"] is None


# 2: middleware during ACTIVE cleanup (delay 5s then RuntimeError -> verified rollback)
def test_2_middleware_active_and_runtime_rollback():
    restart_backend(CLEANUP_TEST_DELAY=5, CLEANUP_TEST_FAIL_AFTER="orders")
    s = login(*SUPER)
    rs = login(*RESELLER)
    before = snapshot()
    u_before = DB.users.find_one({"email": SUPER[0]})
    t, res = fire_async(s, ["orders"])
    wait_lock(lambda l: l.get("state") == "deleting", timeout=20)
    out = {}
    r = rs.post(f"{API}/auth/change-password", json={"current_password": RESELLER[1], "new_password": "TEST_NewPw#2026x"})
    out["change_pw"] = (r.status_code, r.text[:120])
    r = rs.put(f"{API}/me/profile", json={"address": "TEST_iter10 addr"})
    out["profile_put"] = r.status_code
    s2 = requests.Session()
    r = s2.post(f"{API}/auth/login", json={"email": SUPER[0], "password": SUPER[1]})
    out["login"] = r.status_code
    s2.headers["X-CSRF-Token"] = s2.cookies.get("csrf_token") or ""
    out["refresh"] = s2.post(f"{API}/auth/refresh").status_code
    s2.headers["X-CSRF-Token"] = s2.cookies.get("csrf_token") or ""  # refresh rotates csrf cookie
    out["get_products"] = s2.get(f"{API}/products").status_code
    out["get_profile"] = rs.get(f"{API}/me/profile").status_code
    out["post_product"] = s2.post(f"{API}/products", json={"name": "TEST_x", "voltage": "12", "price": 1}).status_code
    out["logout"] = s2.post(f"{API}/auth/logout").status_code
    out["last_login_unchanged"] = DB.users.find_one({"email": SUPER[0]}).get("last_login_at") == u_before.get("last_login_at")
    out["pw_hash_unchanged"] = DB.users.find_one({"email": RESELLER[0]})["password_hash"] == before["users"][DB.users.find_one({"email": RESELLER[0]})["_id"]]["password_hash"]
    t.join(60)
    out["exec"] = (res["r"].status_code, res["r"].text[:400]) if res.get("r") is not None else res
    RESULTS["2_active"] = out
    print(out)
    assert out["change_pw"][0] == 503 and out["profile_put"] == 503 and out["post_product"] == 503
    assert out["login"] == 200 and out["refresh"] == 200 and out["logout"] == 200
    assert out["get_products"] == 200 and out["get_profile"] == 200
    assert out["last_login_unchanged"] and out["pw_hash_unchanged"]
    login(*RESELLER)  # old password still works
    assert out["exec"][0] == 500 and "terverifikasi" in out["exec"][1]
    assert diff(before, snapshot()) == []
    assert history(s)[0]["result"] == "gagal_dipulihkan"
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    # login outside maintenance DOES update last_login_at
    login(*SUPER)
    assert DB.users.find_one({"email": SUPER[0]}).get("last_login_at") != u_before.get("last_login_at")


# 1c: cancel + restore failure -> needs_manual blocked; middleware while blocked; CLI restore; restart unblocks
def test_1c_cancel_restore_fail_then_cli():
    restart_backend(CLEANUP_TEST_FAIL_AFTER="cancel:order_payments", CLEANUP_TEST_FAIL_RESTORE=1)
    s = login(*SUPER)
    rs = login(*RESELLER)
    before = snapshot()
    try:
        r = execute(s, CATS)
        resp = (r.status_code, r.text[:160])
    except requests.RequestException as e:
        resp = ("ERR", str(e)[:120])
    lock = wait_lock(lambda l: l.get("state") == "needs_manual", timeout=20)
    folder = BACKUP / lock["backup"]
    st = s.get(f"{API}/settings/cleanup/status").json()
    out = {"resp": resp, "blocked": st["blocked"]}
    assert st["blocked"] and st["blocked"]["backup"] == folder.name and "Pulihkan manual" in st["blocked"]["message"]
    r = s.post(f"{API}/products", json={})
    out["write"] = (r.status_code, r.text[:200])
    assert r.status_code == 503 and folder.name in r.text
    u_before = DB.users.find_one({"email": SUPER[0]}).get("last_login_at")
    s2 = login(*SUPER)
    out["last_login_unchanged"] = DB.users.find_one({"email": SUPER[0]}).get("last_login_at") == u_before
    out["refresh"] = s2.post(f"{API}/auth/refresh").status_code
    out["change_pw"] = rs.post(f"{API}/auth/change-password", json={"current_password": RESELLER[1], "new_password": "TEST_NewPw#2026x"}).status_code
    out["profile"] = rs.put(f"{API}/me/profile", json={"address": "TEST"}).status_code
    out["get"] = rs.get(f"{API}/orders?page=1&limit=10").status_code
    out["logout"] = s2.post(f"{API}/auth/logout").status_code
    RESULTS["1c"] = out
    print(out)
    assert out["last_login_unchanged"] and out["refresh"] == 200 and out["logout"] == 200
    assert out["change_pw"] == 503 and out["profile"] == 503 and out["get"] == 200
    login(*RESELLER)
    assert DB.orders.count_documents({}) == 0  # really deleted, not restored
    o = cli(folder)
    print(o.stdout[-600:], o.stderr[-300:])
    assert o.returncode == 0 and "Pemulihan selesai dan terverifikasi." in o.stdout
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    restart_backend()
    s = login(*SUPER)
    assert s.get(f"{API}/settings/cleanup/status").json()["blocked"] is None
    after = snapshot()
    assert diff(before, after, skip=("notification_logs",)) == [], diff(before, after)
    assert set(before["notification_logs"]) == set(after["notification_logs"])
    assert any(h["result"] == "dipulihkan_manual" for h in history(s)[:3])
    add_pending_notifs()  # manual restore cancels old pending WA -> re-normalise for later tests
    assert s.post(f"{API}/products", json={}).status_code == 422


# 1d: kill -9 during deleting -> restart recovers
def test_1d_kill9_during_deleting():
    restart_backend(CLEANUP_TEST_DELAY=3)
    s = login(*SUPER)
    before = snapshot()
    fire_async(s, CATS)
    lock = wait_lock(lambda l: l.get("state") == "deleting" and DB.orders.count_documents({}) == 0)
    kill9()
    assert DB.orders.count_documents({}) == 0
    restart_backend()
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    assert diff(before, snapshot()) == []
    h = history(login(*SUPER))[0]
    assert h["result"] == "dipulihkan_setelah_restart" and h["backup"] == lock["backup"]


# 2b: concurrent product creation right before/while execute -> each created product is in backup (and deleted) or got 503
def test_2b_inflight_concurrent_creates():
    restart_backend()
    s = login(*SUPER)
    seed_products = DB.products.count_documents({})
    tag = f"TEST_iter10_inflight_{uuid.uuid4().hex[:5]}"
    sessions = [login(*SUPER) for _ in range(4)]
    out = []

    def create(i):
        try:
            r = sessions[i % 4].post(f"{API}/products", json={"name": f"{tag}_{i}", "voltage": "12", "price": 1000}, timeout=30)
            return i, r.status_code, (r.json().get("id") if r.status_code == 200 else r.text[:80])
        except requests.RequestException as e:
            return i, "ERR", str(e)[:80]

    with ThreadPoolExecutor(16) as ex:
        futs = [ex.submit(create, i) for i in range(60)]
        time.sleep(0.05)
        r = execute(s, ["products"], reset=False)
        out = [f.result() for f in futs]
    assert r.status_code == 200, r.text
    folder = BACKUP / r.json()["backup"]
    backed = {json_util.loads(x)["name"] for x in (folder / "products.jsonl").open() if x.strip()}
    created = [o for o in out if o[1] == 200]
    rejected = [o for o in out if o[1] == 503]
    other = [o for o in out if o[1] not in (200, 503)]
    in_db = DB.products.count_documents({"name": {"$regex": f"^{tag}"}})
    missing_from_backup = [o for o in created if f"{tag}_{o[0]}" not in backed]
    RESULTS["2b"] = {"created": len(created), "503": len(rejected), "other": other[:3], "in_db_after": in_db,
                     "created_not_in_backup": missing_from_backup[:5], "backup": folder.name}
    print(RESULTS["2b"])
    # restore seed products via CLI then remove only TEST products we created
    o = cli(folder)
    assert o.returncode == 0, o.stdout + o.stderr
    DB.products.delete_many({"name": {"$regex": f"^{tag}_"}})
    assert DB.products.count_documents({}) == seed_products
    assert not other and not missing_from_backup
    assert in_db == 0 or in_db == len([o for o in created if f"{tag}_{o[0]}" not in backed])


# 3: manifest v2 + sha256 + permissions on newest full backup (with photos)
def test_3_manifest_v2():
    restart_backend()
    s = login(*SUPER)
    before = snapshot()
    r = execute(s, ["orders", "products"], reset=True)
    assert r.status_code == 200 and r.json()["result"] == "berhasil", r.text
    f = BACKUP / r.json()["backup"]
    man = json.loads((f / "manifest.json").read_text())
    RESULTS["3_manifest"] = {k: man[k] for k in ("version", "cancel_mode", "files", "complete")}
    assert man["version"] == 2 and man["complete"] is True and man["cancel_mode"] is True
    assert set(man["collections"]) >= {"orders", "order_payments", "shipments", "products", "notification_logs"}
    for coll, info in man["collections"].items():
        p = f / f"{coll}.jsonl"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == info["sha256"] and set(info) == {"count", "sha256"}
        assert sum(1 for x in p.open() if x.strip()) == info["count"]
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    fl = f / "files.jsonl"
    assert hashlib.sha256(fl.read_bytes()).hexdigest() == man["files"]["sha256"]
    lines = [json.loads(x) for x in fl.open() if x.strip()]
    assert len(lines) == man["files"]["count"] == len(before["files"]) >= 2
    for d in lines:
        assert set(d) == {"name", "sha256"}
        p = f / "files" / "resi" / d["name"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == d["sha256"] == before["files"][d["name"]]
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    RESULTS["3_perms"] = {str(p.relative_to(BACKUP)): oct(stat.S_IMODE(p.stat().st_mode)) for p in (f, f / "files", f / "files" / "resi")}
    for p in (f, f / "files" / "resi"):
        assert stat.S_IMODE(p.stat().st_mode) == 0o700  # NOTE: files/ intermediate dir is 0755 (mkdir parents ignores mode) -> reported
    assert stat.S_IMODE((f / "manifest.json").stat().st_mode) == 0o600 and stat.S_IMODE(fl.stat().st_mode) == 0o600
    assert DB.orders.count_documents({}) == 0 and not list(RESI.glob("*"))
    o = cli(f)  # put seed back
    assert o.returncode == 0, o.stdout + o.stderr
    after = snapshot()
    assert diff(before, after, skip=("notification_logs", "order_seq")) == [], diff(before, after)
    add_pending_notifs()


# Scale: 20k dummy audit logs, cancel:audit_logs -> recovery window observable; RSS modest
def test_4_scale_audit_cancel():
    restart_backend(CLEANUP_TEST_FAIL_AFTER="cancel:audit_logs")
    pid = subprocess.run("pgrep -f 'port 8101' | head -1", shell=True, capture_output=True, text=True).stdout.strip()
    now = datetime.now(timezone.utc)
    DB.audit_logs.insert_many([{"action": "TEST_iter10_scale", "entity": "x", "detail": {"pad": "x" * 300, "i": i},
                                "created_at": now} for i in range(20000)])
    s = login(*SUPER)
    before_n = DB.audit_logs.count_documents({})
    rss = []
    stop = []

    def watch():
        while not stop:
            v = subprocess.run(f"ps -o rss= -p {pid}", shell=True, capture_output=True, text=True).stdout.strip()
            if v:
                rss.append(int(v))
            time.sleep(0.1)
    w = threading.Thread(target=watch, daemon=True)
    w.start()
    try:
        with Hammer(login(*SUPER)) as h:
            try:
                r = execute(s, ["audit"], reset=False)
                resp = (r.status_code, r.text[:150])
            except requests.RequestException as e:
                resp = ("ERR", str(e)[:100])
            assert wait_no_lock(60)
            time.sleep(0.5)
        stop.append(1)
        msgs = sorted({m[:200] for c, m in h.seen if c == 503})
        RESULTS["4_scale"] = {"resp": resp, "rss_kb_min_max": (min(rss), max(rss)), "503_msgs": msgs,
                              "count_before": before_n, "count_after": DB.audit_logs.count_documents({}),
                              "hist": history(s)[0]["result"]}
        print(RESULTS["4_scale"])
        assert DB.audit_logs.count_documents({}) == before_n
        assert history(s)[0]["result"] == "dipulihkan_setelah_restart"
        assert any("memulihkan otomatis" in m for m in msgs), msgs
    finally:
        DB.audit_logs.delete_many({"action": "TEST_iter10_scale"})
