"""RelayLab OMS backend regression tests (orders, snapshot, payments, shipments, isolation, webhook, auth)."""
import io
import json
import time
import uuid

import requests

from conftest import BASE_URL, RUN, login


def key():
    return uuid.uuid4().hex


def mk_order(s, items, reseller_id=None):
    body = {"items": items, "idempotency_key": key(), "notes": "TEST_"}
    if reseller_id:
        body["reseller_id"] = reseller_id
    return s.post(f"{BASE_URL}/api/orders", json=body)


# --- Auth basics
def test_health_and_me(admin):
    assert requests.get(f"{BASE_URL}/api/health").json()["status"] == "ok"
    me = admin.get(f"{BASE_URL}/api/auth/me").json()
    assert me["role"] == "admin" and "password_hash" not in me


def test_csrf_required(admin):
    s = requests.Session()
    s.cookies.update(admin.cookies)
    r = s.post(f"{BASE_URL}/api/products", json={"name": "TEST_X", "price": 1})
    assert r.status_code == 403


# --- PENGUJIAN 1: price snapshot
def test_price_snapshot(admin, ctx):
    ra = ctx["ra"]["session"]
    p1 = ctx["p1"]
    r = mk_order(ra, [{"product_id": p1["id"], "qty": 10, "expected_price": 110000}])
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["grand_total"] == 1100000 and o["code"].startswith("RL-")
    body = {k: p1[k] for k in ("name", "voltage", "is_active", "notes")}
    body["price"] = 125000
    u = admin.put(f"{BASE_URL}/api/products/{p1['id']}", json=body)
    assert u.status_code == 200
    hist = u.json()["price_history"]
    assert hist[-1]["old_price"] == 110000 and hist[-1]["new_price"] == 125000 and hist[-1]["admin_name"]
    d = ra.get(f"{BASE_URL}/api/orders/{o['id']}").json()["order"]
    assert d["grand_total"] == 1100000 and d["items"][0]["unit_price_snapshot"] == 110000 and d["remaining"] == 1100000
    lst = [x for x in ra.get(f"{BASE_URL}/api/orders?limit=100").json()["items"] if x["id"] == o["id"]][0]
    assert lst["grand_total"] == 1100000
    rek = ra.get(f"{BASE_URL}/api/reports/reseller").json()
    assert [x for x in rek["rows"] if x["id"] == o["id"]][0]["grand_total"] == 1100000
    # old expected price -> 409
    r409 = mk_order(ra, [{"product_id": p1["id"], "qty": 10, "expected_price": 110000}])
    assert r409.status_code == 409 and r409.json()["detail"]["code"] == "PRICE_CHANGED"
    n = mk_order(ra, [{"product_id": p1["id"], "qty": 10, "expected_price": 125000}])
    assert n.status_code == 200 and n.json()["grand_total"] == 1250000
    ctx["order_a"] = o


# --- PENGUJIAN 2/3: min qty
def test_min_qty_regular_rejected(ctx):
    r = mk_order(ctx["ra"]["session"], [{"product_id": ctx["p2"]["id"], "qty": 5}])
    assert r.status_code == 422
    assert r.json()["detail"]["message"] == "Qty minimal per item untuk akun Anda adalah 10 pcs."


def test_min_qty_special_ok(ctx):
    r = mk_order(ctx["rs"]["session"], [{"product_id": ctx["p2"]["id"], "qty": 1}])
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["voltage_snapshot"] == "-" and r.json()["items"][0]["display_name"].endswith(RUN)


def test_duplicate_product_merge_and_idempotency(ctx):
    s = ctx["ra"]["session"]
    k = key()
    body = {"items": [{"product_id": ctx["p2"]["id"], "qty": 10}, {"product_id": ctx["p2"]["id"], "qty": 10}], "idempotency_key": k}
    a = s.post(f"{BASE_URL}/api/orders", json=body)
    b = s.post(f"{BASE_URL}/api/orders", json=body)
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["id"] == b.json()["id"]
    assert len(a.json()["items"]) == 1 and a.json()["items"][0]["qty_order"] == 20


# --- Custom product
def test_custom_item_resolve(admin, ctx):
    s = ctx["ra"]["session"]
    r = mk_order(s, [{"product_id": ctx["p2"]["id"], "qty": 10}, {"custom_name": "TEST_Custom Relay", "qty": 10}])
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["price_pending"] is True and o["grand_total"] == 1000000
    cid = [i for i in o["items"] if i["is_custom"]][0]["item_id"]
    rr = admin.post(f"{BASE_URL}/api/orders/{o['id']}/custom-items/resolve", json={"item_id": cid, "unit_price": 50000, "reason": "TEST"})
    assert rr.status_code == 200, rr.text
    assert rr.json()["grand_total"] == 1500000 and rr.json()["price_pending"] is False
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()["order"]
    assert d["price_adjustments"][-1]["type"] == "penetapan_custom"


# --- PENGUJIAN 4: payments
def test_payments_void_overpay(admin, ctx):
    o = mk_order(admin, [{"product_id": ctx["p2"]["id"], "qty": 50}], ctx["ra"]["reseller"]["id"]).json()
    assert o["grand_total"] == 5000000
    p = admin.post(f"{BASE_URL}/api/orders/{o['id']}/payments", json={"amount": 2000000, "idempotency_key": key()})
    assert p.status_code == 200
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()["order"]
    assert d["remaining"] == 3000000 and d["payment_status"] == "belum_lunas"
    v = admin.post(f"{BASE_URL}/api/orders/{o['id']}/payments/{p.json()['id']}/void", json={"reason": "TEST salah input"})
    assert v.status_code == 200
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert d["order"]["total_paid"] == 0 and d["order"]["payment_status"] == "belum_ada_pembayaran"
    assert d["payments"][0]["is_void"] is True
    admin.post(f"{BASE_URL}/api/orders/{o['id']}/payments", json={"amount": 5500000, "idempotency_key": key()})
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()["order"]
    assert d["payment_status"] == "lebih_bayar" and d["overpaid"] == 500000
    # reseller doesn't see voided payment
    rd = ctx["ra"]["session"].get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert all(not x["is_void"] for x in rd["payments"])


# --- PENGUJIAN 5: shipments + progress + status notif
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def ship(admin, oid, item_id, qty, photo=None):
    files = {"photo": photo} if photo else None
    data = {"courier": "TEST_JNE", "tracking_no": f"TEST{key()[:6]}", "shipped_at": "2026-01-10T10:00", "notes": "",
            "items": json.dumps([{"item_id": item_id, "qty": qty}]), "idempotency_key": key()}
    return admin.post(f"{BASE_URL}/api/orders/{oid}/shipments", data=data, files=files)


def test_shipments_progress_status(admin, ctx):
    o = mk_order(admin, [{"product_id": ctx["p2"]["id"], "qty": 50}], ctx["ra"]["reseller"]["id"]).json()
    iid = o["items"][0]["item_id"]
    # status diproses -> one notif
    admin.patch(f"{BASE_URL}/api/orders/{o['id']}/status", json={"status": "diproses"})
    admin.patch(f"{BASE_URL}/api/orders/{o['id']}/status", json={"status": "diproses"})
    time.sleep(1)
    notifs = admin.get(f"{BASE_URL}/api/notifications").json()
    assert notifs["mode"] == "simulation"
    mine = [n for n in notifs["items"] if n.get("order_id") == o["id"] and n["kind"] == "order_diproses"]
    assert len(mine) == 1 and mine[0]["status"] == "simulated"
    # progress
    assert admin.put(f"{BASE_URL}/api/orders/{o['id']}/progress", json={"items": [{"item_id": iid, "qty_done": 51}]}).status_code == 422
    assert admin.put(f"{BASE_URL}/api/orders/{o['id']}/progress", json={"items": [{"item_id": iid, "qty_done": 20}]}).status_code == 200
    # bad file
    bad = ship(admin, o["id"], iid, 20, ("x.txt", io.BytesIO(b"hello"), "text/plain"))
    assert bad.status_code == 422
    fake = ship(admin, o["id"], iid, 20, ("x.png", io.BytesIO(b"notimage"), "image/png"))
    assert fake.status_code == 422
    s1 = ship(admin, o["id"], iid, 20, ("r.png", io.BytesIO(PNG), "image/png"))
    assert s1.status_code == 200, s1.text
    fn = s1.json()["photo_filename"]
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()["order"]
    assert d["items"][0]["qty_remaining_ship"] == 30 and d["items"][0]["qty_shipped"] == 20
    assert admin.put(f"{BASE_URL}/api/orders/{o['id']}/progress", json={"items": [{"item_id": iid, "qty_done": 10}]}).status_code == 422
    assert ship(admin, o["id"], iid, 31).status_code == 422
    assert ship(admin, o["id"], iid, 30).status_code == 200
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()["order"]
    assert d["status"] == "selesai"
    # file access
    assert ctx["ra"]["session"].get(f"{BASE_URL}/api/files/resi/{fn}").status_code == 200
    assert ctx["rb"]["session"].get(f"{BASE_URL}/api/files/resi/{fn}").status_code == 403
    ctx["ship_order"] = o


# --- Price adjustment isolation
def test_price_adjustment_only_one_order(admin, ctx):
    o1 = mk_order(admin, [{"product_id": ctx["p2"]["id"], "qty": 10}], ctx["ra"]["reseller"]["id"]).json()
    o2 = mk_order(admin, [{"product_id": ctx["p2"]["id"], "qty": 10}], ctx["ra"]["reseller"]["id"]).json()
    r = admin.post(f"{BASE_URL}/api/orders/{o1['id']}/price-adjustments",
                   json={"item_id": o1["items"][0]["item_id"], "new_price": 90000, "reason": "TEST diskon"})
    assert r.status_code == 200 and r.json()["grand_total"] == 900000
    assert admin.get(f"{BASE_URL}/api/orders/{o2['id']}").json()["order"]["grand_total"] == 1000000
    assert admin.get(f"{BASE_URL}/api/orders/{o1['id']}").json()["order"]["price_adjustments"][-1]["reason"] == "TEST diskon"


# --- PENGUJIAN 7: isolation
def test_reseller_isolation(ctx):
    rb = ctx["rb"]["session"]
    oid = ctx["order_a"]["id"]
    assert rb.get(f"{BASE_URL}/api/orders/{oid}").status_code == 403
    assert all(o["reseller_id"] == ctx["rb"]["reseller"]["id"] for o in rb.get(f"{BASE_URL}/api/orders?limit=100").json()["items"])
    assert rb.get(f"{BASE_URL}/api/resellers").status_code == 403
    assert rb.post(f"{BASE_URL}/api/products", json={"name": "TEST_HACK", "price": 1}).status_code == 403
    assert rb.post(f"{BASE_URL}/api/orders/{oid}/payments", json={"amount": 1, "idempotency_key": key()}).status_code == 403
    assert rb.get(f"{BASE_URL}/api/notifications").status_code == 403
    assert rb.get(f"{BASE_URL}/api/reports/admin").status_code == 403
    # reseller cannot create order for another reseller
    r = mk_order(rb, [{"product_id": ctx["p2"]["id"], "qty": 10}], ctx["ra"]["reseller"]["id"])
    assert r.status_code == 200 and r.json()["reseller_id"] == ctx["rb"]["reseller"]["id"]


# --- Webhook
def notif_count(admin, target, kind):
    items = admin.get(f"{BASE_URL}/api/notifications").json()["items"]
    return [n for n in items if n["target"] == target and n["kind"] == kind]


def test_webhook(admin, ctx):
    wa = "62" + ctx["ra"]["wa"][1:]
    code = ctx["order_a"]["code"]
    W = f"{BASE_URL}/api/webhooks/fonnte"
    before = len(notif_count(admin, wa, "balasan_cekorder"))
    requests.post(W, json={"sender": wa, "message": f"/cekorder {code}", "id": key()})
    time.sleep(1)
    rep = notif_count(admin, wa, "balasan_cekorder")
    assert len(rep) == before + 1 and f"Detail Order {code}" in rep[0]["message"]
    other = "6289900000" + RUN[:3].encode().hex()[:2]
    requests.post(W, json={"sender": other, "message": f"/cekorder {code}", "id": key()})
    time.sleep(1)
    rep = notif_count(admin, other, "balasan_cekorder")
    assert rep and "tidak ditemukan" in rep[0]["message"] and "Detail" not in rep[0]["message"]
    total_before = len(admin.get(f"{BASE_URL}/api/notifications").json()["items"])
    requests.post(W, json={"sender": wa, "message": "halo", "id": key()})
    requests.post(W, json={"sender": wa, "message": "/pengumuman", "id": key()})
    time.sleep(1)
    assert len(admin.get(f"{BASE_URL}/api/notifications").json()["items"]) == total_before
    adm = "6281200000000"
    requests.post(W, json={"sender": adm, "message": "/pengumuman", "id": key()})
    requests.post(W, json={"sender": adm, "message": "TEST_ pengumuman", "id": key()})
    time.sleep(1)
    rep = notif_count(admin, adm, "balasan_pengumuman")
    assert any("Silahkan isi" in n["message"] for n in rep[:2]) and "belum dikonfigurasi" in rep[0]["message"]
    requests.post(W, json={"sender": adm, "message": "/pengumuman", "id": key()})
    requests.post(W, json={"sender": adm, "message": "/batal", "id": key()})
    time.sleep(1)
    assert notif_count(admin, adm, "balasan_pengumuman")[0]["message"] == "Pengumuman dibatalkan."


# --- Reports
def test_reports(admin):
    r = admin.get(f"{BASE_URL}/api/reports/admin").json()
    assert "per_reseller" in r and "cashflow" in r and "cashflow_total" in r
    d = admin.get(f"{BASE_URL}/api/dashboard").json()
    assert len(d["chart"]) == 30 and "by_status" in d
    assert admin.get(f"{BASE_URL}/api/reports/reseller?date_from=2026-02-01&date_to=2026-01-01").status_code == 422


# --- Users: deactivate & brute force
def test_user_deactivate_and_lockout(admin, ctx):
    email = f"test_user_{RUN}@example.com"
    u = admin.post(f"{BASE_URL}/api/users", json={"email": email, "name": "TEST_User", "role": "reseller",
                                                   "reseller_id": ctx["rb"]["reseller"]["id"], "password": "TestPass#123"})
    assert u.status_code == 200, u.text
    uid = u.json()["id"]
    s, r = login(email, "TestPass#123")
    assert r.status_code == 200
    assert admin.patch(f"{BASE_URL}/api/users/{uid}", json={"is_active": False}).status_code == 200
    assert s.get(f"{BASE_URL}/api/auth/me").status_code == 401
    _, r = login(email, "TestPass#123")
    assert r.status_code == 403
    admin.patch(f"{BASE_URL}/api/users/{uid}", json={"is_active": True})
    codes = [login(email, "wrong-pass")[1].status_code for _ in range(5)]
    assert codes == [401] * 5
    _, r = login(email, "TestPass#123")
    assert r.status_code == 429 and "dikunci" in r.json()["detail"]
    assert admin.post(f"{BASE_URL}/api/users/{uid}/reset-password", json={"new_password": "TestPass#456"}).status_code == 200
    _, r = login(email, "TestPass#456")
    assert r.status_code == 200 and r.json()["must_change_password"] is True
