"""Iteration 7 helpers for the isolated QA stack ONLY (http://127.0.0.1:8088/order, mongod 27018)."""
import json
import sys
import uuid

import requests

QA = "http://127.0.0.1:8088/order"
API = f"{QA}/api"
SUPER = ("superadmin@qa-relaylab.com", "SuperQA#2026")


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    s.headers["X-CSRF-Token"] = s.cookies.get("csrf_token")
    return s


def find_order(s, code):
    items = s.get(f"{API}/orders?page=1&limit=100&q={code}").json()["items"]
    return next(o for o in items if o["code"] == code)


def ship_full(code, n, mark_done=True):
    """Fully ship the first n unfinished items of order `code`."""
    s = login(*SUPER)
    o = find_order(s, code)
    d = s.get(f"{API}/orders/{o['id']}").json()["order"]
    todo = [i for i in d["items"] if i["qty_shipped"] < i["qty_order"]][:n]
    payload = [{"item_id": i["item_id"], "qty": i["qty_order"] - i["qty_shipped"]} for i in todo]
    r = s.post(f"{API}/orders/{o['id']}/shipments", data={
        "courier": "JNE", "tracking_no": "TEST_" + uuid.uuid4().hex[:8], "shipped_at": "2026-11-07T10:00",
        "notes": "TEST_iter7", "items": json.dumps(payload), "idempotency_key": uuid.uuid4().hex})
    return r.status_code, r.text[:300]


if __name__ == "__main__":
    print(ship_full(sys.argv[1], int(sys.argv[2])))
