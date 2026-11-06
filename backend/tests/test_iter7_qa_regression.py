"""Iteration 7 QA-stack API regression (127.0.0.1:8088/order only). Creates TEST_ data on the QA DB (disposable stack)."""
import io
import json
import uuid

import pytest
import requests
from PIL import Image

from test_iter7_qa_rollback import API, SUPER, RESELLER, login

ADMIN2 = ("admin2@qa-relaylab.com", "AdminQA#2026")
K = lambda: uuid.uuid4().hex  # noqa: E731
CTX = {}


@pytest.fixture(scope="module")
def sa():
    return login(*SUPER)


@pytest.fixture(scope="module")
def a2():
    return login(*ADMIN2)


@pytest.fixture(scope="module")
def rs():
    return login(*RESELLER)


# Auth: 3 roles, cookies httpOnly, /me
def test_login_roles(sa, a2, rs):
    assert sa.get(f"{API}/auth/me").json()["role"] == "admin"
    assert a2.get(f"{API}/auth/me").json()["role"] == "admin"
    assert rs.get(f"{API}/auth/me").json()["role"] == "reseller"
    r = requests.post(f"{API}/auth/login", json={"email": SUPER[0], "password": SUPER[1]})
    sc = r.headers.get("set-cookie", "")
    assert "access_token" in sc and "HttpOnly" in sc


def test_wrong_password_401():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN2[0], "password": "wrong-pass"})
    assert r.status_code in (400, 401)


# Products CRUD
def test_product_create_update(sa, rs):
    r = sa.post(f"{API}/products", json={"name": f"TEST_Iter7 {K()[:4]}", "voltage": "12", "price": 15000})
    assert r.status_code in (200, 201), r.text
    p = r.json()
    CTX["product"] = p
    u = sa.put(f"{API}/products/{p['id']}", json={"name": p["name"], "voltage": "24", "price": 17000})
    assert u.status_code == 200 and u.json()["price"] == 17000
    assert sa.get(f"{API}/products/{p['id']}").json()["voltage"] == "24"
    assert rs.post(f"{API}/products", json={"name": "TEST_x", "price": 1}).status_code == 403


def test_resellers_list(sa, rs):
    r = sa.get(f"{API}/resellers")
    assert r.status_code == 200
    assert rs.get(f"{API}/resellers").status_code == 403


# Order -> payment -> progress -> shipment(photo) -> view
def test_order_flow(sa, rs):
    p = CTX["product"]
    r = rs.post(f"{API}/orders", json={"items": [{"product_id": p["id"], "qty": 3}], "idempotency_key": K(), "notes": "TEST_iter7"})
    assert r.status_code in (200, 201), r.text
    o = r.json()
    oid = o["id"]
    assert o["grand_total"] == 51000
    pay = sa.post(f"{API}/orders/{oid}/payments", json={"amount": 20000, "idempotency_key": K(), "notes": "TEST_"})
    assert pay.status_code in (200, 201), pay.text
    d = sa.get(f"{API}/orders/{oid}").json()
    assert d["order"]["total_paid"] == 20000
    item = d["order"]["items"][0]
    pr = sa.put(f"{API}/orders/{oid}/progress", json={"items": [{"item_id": item["item_id"], "qty_done": 2}]})
    assert pr.status_code == 200, pr.text
    b = io.BytesIO(); Image.new("RGB", (30, 30), "blue").save(b, "JPEG")
    sh = sa.post(f"{API}/orders/{oid}/shipments", data={"courier": "JNE", "tracking_no": "TEST_" + K()[:6],
                 "shipped_at": "2026-11-07T12:00", "items": json.dumps([{"item_id": item["item_id"], "qty": 2}]),
                 "idempotency_key": K()}, files={"photo": ("a.jpg", b.getvalue(), "image/jpeg")})
    assert sh.status_code == 200, sh.text
    fn = sh.json()["photo_filename"]
    assert rs.get(f"{API}/files/resi/{fn}").status_code == 200
    rd = rs.get(f"{API}/orders/{oid}").json()["order"]["items"][0]
    assert rd["qty_shipped"] == 2 and rd["qty_done"] == 2
    over = sa.post(f"{API}/orders/{oid}/shipments", data={"courier": "JNE", "tracking_no": "TEST_x1", "shipped_at": "2026-11-07T12:00",
                   "items": json.dumps([{"item_id": item["item_id"], "qty": 5}]), "idempotency_key": K()})
    assert over.status_code == 422
    CTX["order"] = oid


def test_reports_dashboards(sa, rs):
    assert sa.get(f"{API}/dashboard").status_code == 200
    assert rs.get(f"{API}/dashboard").status_code == 200
    assert rs.get(f"{API}/reports/reseller").status_code == 200
    r = sa.get(f"{API}/reports/admin", params={"date_from": "2026-11-01", "date_to": "2026-11-30"})
    assert r.status_code == 200, r.text


def test_notifications_simulated(sa, rs):
    r = sa.get(f"{API}/notifications")
    assert r.status_code == 200
    data = r.json()
    items = data["items"] if isinstance(data, dict) else data
    assert any(n.get("status") == "simulated" for n in items)
    assert rs.get(f"{API}/notifications").status_code == 403


def test_cleanup_authz(a2, rs, sa):
    body = {"categories": ["orders"], "reset_order_seq": False}
    assert a2.post(f"{API}/settings/cleanup/preview", json=body).status_code == 403
    assert rs.post(f"{API}/settings/cleanup/preview", json=body).status_code == 403
    pv = sa.post(f"{API}/settings/cleanup/preview", json=body)
    assert pv.status_code == 200 and pv.json()["counts"]["orders"]["orders"] >= 3
