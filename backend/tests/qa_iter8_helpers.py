"""Iteration 8 helpers — isolated QA stack ONLY (127.0.0.1:8088/order, mongod 27018 relaylab_oms_qa)."""
import hashlib
import io
import json
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image
from pymongo import MongoClient

QA = "http://127.0.0.1:8088/order"
API = f"{QA}/api"
SUPER = ("superadmin@qa-relaylab.com", "SuperQA#2026")
ADMIN2 = ("admin2@qa-relaylab.com", "AdminQA#2026")
RESELLER = ("reseller1@qa-relaylab.com", "ResellerQA#2026")
RESI = Path("/tmp/qa/uploads/resi")
BACKUP = Path("/tmp/qa/backups")
DB = MongoClient("mongodb://127.0.0.1:27018", tz_aware=True)["relaylab_oms_qa"]
COLLS = ["orders", "order_payments", "shipments", "products", "resellers", "users", "notification_logs",
         "announcement_states", "webhook_events", "audit_logs"]
IGNORE = {"users": {"last_login_at"}}
LOCK = "cleanup_lock"


def restart_backend(**env):
    subprocess.run("pkill -9 -f 'port 8101'", shell=True)
    time.sleep(1.5)
    parts = "".join(f"{k}={v}; " for k, v in env.items())
    subprocess.run("cd /app/backend && (set -a; . /tmp/qa/be.env; " + parts +
                   "set +a; nohup uvicorn server:app --host 127.0.0.1 --port 8101 > /tmp/qa/backend.log 2>&1 &)", shell=True)
    for _ in range(60):
        time.sleep(0.5)
        try:
            if requests.get(f"{API}/health", timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
    raise RuntimeError("QA backend did not come up")


def kill9():
    subprocess.run("pkill -9 -f 'port 8101'", shell=True)
    time.sleep(1)


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
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


def diff(a, b, skip=()):
    out = []
    for k in a:
        if k in skip:
            continue
        if a[k] != b[k]:
            miss = set(a[k]) - set(b[k])
            extra = set(b[k]) - set(a[k])
            changed = [i for i in a[k] if i in b[k] and a[k][i] != b[k][i]]
            out.append(f"{k}: missing={len(miss)} extra={len(extra)} changed={len(changed)}")
    return out


def exec_body(cats, reset=True):
    return {"categories": cats, "reset_order_seq": reset, "confirm_text": "HAPUS DATA", "password": SUPER[1]}


def execute(s, cats, reset=True):
    return s.post(f"{API}/settings/cleanup/execute", json=exec_body(cats, reset), timeout=120)


def fire_async(s, cats, reset=True):
    res = {}

    def run():
        try:
            res["r"] = execute(s, cats, reset)
        except Exception as e:  # connection drop expected on kill -9
            res["err"] = str(e)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, res


def wait_lock(pred, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        lock = DB.system_settings.find_one({"_id": LOCK})
        if lock and pred(lock):
            return lock
        time.sleep(0.05)
    raise AssertionError("lock condition not reached")


def jpg(color):
    b = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(b, "JPEG")
    return b.getvalue()


def add_photo_shipments(s, n=2):
    orders = s.get(f"{API}/orders?page=1&limit=100").json()["items"]
    for o in orders:
        d = s.get(f"{API}/orders/{o['id']}").json()["order"]
        todo = [i for i in d["items"] if i["qty_shipped"] < i["qty_order"]]
        for i, it in enumerate(todo[:n]):
            r = s.post(f"{API}/orders/{o['id']}/shipments", data={
                "courier": "JNT", "tracking_no": f"TEST_i8{uuid.uuid4().hex[:6]}", "shipped_at": "2026-11-07T11:00",
                "notes": "TEST_iter8 photo", "items": json.dumps([{"item_id": it["item_id"], "qty": 1}]),
                "idempotency_key": uuid.uuid4().hex}, files={"photo": (f"r{i}.jpg", jpg(["red", "green", "blue"][i % 3]), "image/jpeg")})
            assert r.status_code == 200, r.text
        if todo:
            return


def add_pending_notifs():
    far = datetime.now(timezone.utc) + timedelta(days=30)
    if DB.notification_logs.count_documents({"kind": "TEST_iter8_pending"}):
        return
    for o in DB.orders.find({}).limit(2):
        DB.notification_logs.insert_one({"kind": "TEST_iter8_pending", "target": "628000000099", "message": "TEST_pending",
                                         "order_id": o["_id"], "status": "pending", "attempts": 0,
                                         "next_attempt_at": far, "created_at": datetime.now(timezone.utc)})


def history(s):
    return s.get(f"{API}/settings/cleanup/history").json()


def cli(folder):
    return subprocess.run(f"cd /app/backend && (set -a; . /tmp/qa/be.env; set +a; python -m app.restore_cleanup {folder})",
                          shell=True, capture_output=True, text=True, timeout=120)
