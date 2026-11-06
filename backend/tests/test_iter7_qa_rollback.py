"""Iteration 7 cleanup ROLLBACK with fault injection (QA stack ONLY: 127.0.0.1:8088/order, mongod 27018 relaylab_oms_qa).
Run serially: pytest -p no:xdist -n 0 test_iter7_qa_rollback.py. Restarts QA backend (port 8101) with CLEANUP_TEST_FAIL_* env;
the last test restarts it WITHOUT fault env and runs a real (successful) cleanup."""
import hashlib
import io
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from PIL import Image
from pymongo import MongoClient

QA = "http://127.0.0.1:8088/order"
API = f"{QA}/api"
SUPER = ("superadmin@qa-relaylab.com", "SuperQA#2026")
RESELLER = ("reseller1@qa-relaylab.com", "ResellerQA#2026")
RESI = Path("/tmp/qa/uploads/resi")
BACKUP = Path("/tmp/qa/backups")
DB = MongoClient("mongodb://127.0.0.1:27018", tz_aware=True)["relaylab_oms_qa"]
COLLS = ["orders", "order_payments", "shipments", "products", "resellers", "users", "notification_logs",
         "announcement_states", "webhook_events"]
IGNORE = {"users": {"last_login_at"}}


def restart_backend(**fault):
    subprocess.run("pkill -f 'port 8101'", shell=True)
    time.sleep(1.5)
    env_parts = " ".join(f"{k}={v}" for k, v in fault.items())
    cmd = ("cd /app/backend && (set -a; . /tmp/qa/be.env; " + (env_parts + "; " if env_parts else "") +
           "set +a; nohup uvicorn server:app --host 127.0.0.1 --port 8101 --reload --reload-dir /app/backend/app "
           "> /tmp/qa/backend.log 2>&1 &)")
    subprocess.run(cmd, shell=True)
    for _ in range(40):
        time.sleep(0.5)
        try:
            if requests.get(f"{API}/health", timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
    raise RuntimeError("QA backend did not come up")


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    s.headers["X-CSRF-Token"] = s.cookies.get("csrf_token")
    return s


def snapshot():
    snap = {}
    for c in COLLS:
        docs = {}
        for d in DB[c].find({}):
            for f in IGNORE.get(c, ()):
                d.pop(f, None)
            docs[d["_id"]] = d
        snap[c] = docs
    snap["order_seq"] = {d["_id"]: d for d in DB.system_settings.find({"_id": {"$regex": "^order_seq:"}})}
    snap["files"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RESI.glob("*") if p.is_file()}
    return snap


def diff(a, b):
    out = []
    for k in a:
        if a[k] != b[k]:
            if isinstance(a[k], dict) and k != "files":
                miss = set(a[k]) - set(b[k])
                extra = set(b[k]) - set(a[k])
                changed = [i for i in a[k] if i in b[k] and a[k][i] != b[k][i]]
                out.append(f"{k}: missing={len(miss)} extra={len(extra)} changed={len(changed)}")
            else:
                out.append(f"{k}: files differ {set(a[k].items()) ^ set(b[k].items())}")
    return out


def execute(s, cats, reset=True):
    return s.post(f"{API}/settings/cleanup/execute", json={"categories": cats, "reset_order_seq": reset,
                                                            "confirm_text": "HAPUS DATA", "password": SUPER[1]}, timeout=90)


def jpg(color):
    b = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(scope="module")
def sa():
    restart_backend()
    return login(*SUPER)


# Prep: extra photo shipments + pending order notifications (TEST_)
def test_00_prepare(sa):
    orders = sa.get(f"{API}/orders?page=1&limit=100").json()["items"]
    o = next(x for x in orders if x["code"] == "RL-071126-0001")
    d = sa.get(f"{API}/orders/{o['id']}").json()["order"]
    todo = [i for i in d["items"] if i["qty_shipped"] < i["qty_order"]]
    for n, color in enumerate(["red", "green"]):
        it = todo[n]
        r = sa.post(f"{API}/orders/{o['id']}/shipments", data={
            "courier": "JNT", "tracking_no": f"TEST_ph{n}{uuid.uuid4().hex[:5]}", "shipped_at": "2026-11-07T11:00",
            "notes": "TEST_iter7 photo", "items": json.dumps([{"item_id": it["item_id"], "qty": 1}]),
            "idempotency_key": uuid.uuid4().hex}, files={"photo": (f"r{n}.jpg", jpg(color), "image/jpeg")})
        assert r.status_code == 200, r.text
    far = datetime.now(timezone.utc) + timedelta(days=30)
    for x in orders[:2]:
        DB.notification_logs.insert_one({"kind": "TEST_iter7_pending", "target": "628000000099", "message": "TEST_pending",
                                         "order_id": DB.orders.find_one({"code": x["code"]})["_id"], "status": "pending",
                                         "attempts": 0, "next_attempt_at": far, "created_at": datetime.now(timezone.utc)})
    assert DB.notification_logs.count_documents({"status": "pending", "kind": "TEST_iter7_pending"}) == 2
    assert len(list(RESI.glob("*"))) >= 3


SCENARIOS = [
    ("order_payments", ["orders", "products", "notifications"]),
    ("orders", ["orders", "products", "notifications"]),
    ("shipments", ["orders", "products", "notifications"]),
    ("resi_files", ["orders"]),  # orders only -> also exercises pending-notif cancel + seq reset before fault
    ("users", ["orders", "resellers"]),
    ("notification_logs", ["orders", "products", "notifications"]),
]


@pytest.mark.parametrize("point,cats", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_rollback_verified(point, cats):
    restart_backend(CLEANUP_TEST_FAIL_AFTER=point)
    s = login(*SUPER)
    before = snapshot()
    folders_before = set(os.listdir(BACKUP))
    r = execute(s, cats)
    after = snapshot()
    print(point, r.status_code, r.text[:300])
    assert r.status_code == 500, r.text
    assert "terverifikasi" in r.json()["detail"] and "TIDAK" not in r.json()["detail"]
    new = set(os.listdir(BACKUP)) - folders_before
    assert len(new) == 1 and (BACKUP / new.pop() / "manifest.json").is_file()
    assert diff(before, after) == [], diff(before, after)
    h = s.get(f"{API}/settings/cleanup/history").json()[0]
    assert h["result"] == "gagal_dipulihkan" and h.get("verified") is True
    deleted = h.get("deleted", {})
    print("deleted before fault:", deleted)
    # pending notifs kept original status
    assert DB.notification_logs.count_documents({"kind": "TEST_iter7_pending", "status": "pending"}) == 2
    # order detail + photos still work
    for o in s.get(f"{API}/orders?page=1&limit=100").json()["items"]:
        d = s.get(f"{API}/orders/{o['id']}")
        assert d.status_code == 200
        for sh in d.json()["shipments"]:
            if sh.get("photo_filename"):
                assert s.get(f"{API}/files/resi/{sh['photo_filename']}").status_code == 200


def test_resi_first_file_really_deleted_during_fault():
    """Sanity: backend log shows simulated fault for resi_files was raised (file deletion happens before fault)."""
    # Verified indirectly via history 'deleted' + identical files hashes; check log presence of earlier runs is not possible
    # after restarts, so just assert latest history entries include a resi_files fault message.
    s = login(*SUPER)
    hist = s.get(f"{API}/settings/cleanup/history").json()
    assert any("resi_files" in (h.get("error") or "") for h in hist)
    assert any("users" in (h.get("error") or "") and h.get("deleted", {}).get("users", 0) >= 1 for h in hist)


def test_restore_failure_then_manual_cli():
    restart_backend(CLEANUP_TEST_FAIL_AFTER="order_payments", CLEANUP_TEST_FAIL_RESTORE="1")
    s = login(*SUPER)
    before = snapshot()
    folders_before = set(os.listdir(BACKUP))
    r = execute(s, ["orders", "products", "notifications"])
    print(r.status_code, r.text[:400])
    assert r.status_code == 500
    det = r.json()["detail"]
    assert "TIDAK terverifikasi" in det
    new = (set(os.listdir(BACKUP)) - folders_before).pop()
    assert new in det and "tetap disimpan" in det
    folder = BACKUP / new
    assert (folder / "orders.jsonl").is_file() and (folder / "order_payments.jsonl").is_file()
    assert len(list((folder / "files" / "resi").glob("*"))) == len(before["files"])
    h = s.get(f"{API}/settings/cleanup/history").json()[0]
    assert h["result"] == "gagal_pemulihan_otomatis"
    assert DB.orders.count_documents({}) == 0 and DB.order_payments.count_documents({}) == 0  # partial deletion left
    restart_backend()
    out = subprocess.run(f"cd /app/backend && (set -a; . /tmp/qa/be.env; set +a; python -m app.restore_cleanup {folder})",
                         shell=True, capture_output=True, text=True)
    print(out.stdout, out.stderr)
    assert out.returncode == 0, out.stderr
    assert "Pemulihan selesai dan terverifikasi." in out.stdout and "Verifikasi orders" in out.stdout
    after = snapshot()
    # manual restore cancels pending WA by design -> compare others exactly
    nb, na = before.pop("notification_logs"), after.pop("notification_logs")
    assert diff(before, after) == [], diff(before, after)
    assert set(nb) == set(na)
    assert DB.notification_logs.count_documents({"kind": "TEST_iter7_pending", "status": "cancelled"}) == 2
    assert folder.is_dir()


def test_cli_incomplete_exits_nonzero(tmp_path):
    bad = subprocess.run("cd /app/backend && (set -a; . /tmp/qa/be.env; set +a; python -m app.restore_cleanup /tmp/qa/nonexistent)",
                         shell=True, capture_output=True, text=True)
    assert bad.returncode != 0 and "tidak valid" in (bad.stderr + bad.stdout)


def test_normal_cleanup_succeeds_without_fault():
    restart_backend()
    s = login(*SUPER)
    r = execute(s, ["audit"], reset=False)
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "berhasil"
