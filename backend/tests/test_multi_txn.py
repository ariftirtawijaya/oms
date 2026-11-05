"""Multi-payment, multi-shipment and idempotency (double-submit) tests for RelayLab OMS."""
import json
import threading
import uuid

from conftest import BASE_URL


def key():
    return uuid.uuid4().hex


def mk_order(s, items, reseller_id=None, k=None):
    body = {"items": items, "idempotency_key": k or key(), "notes": "TEST_multi"}
    if reseller_id:
        body["reseller_id"] = reseller_id
    return s.post(f"{BASE_URL}/api/orders", json=body)


def new_product(admin, ctx, price=50000):
    code = f"TEST_MT_{ctx['run']}_{key()[:4]}"
    r = admin.post(f"{BASE_URL}/api/products", json={"code": code, "name": f"TEST_Multi {code}", "voltage": "12", "price": price})
    assert r.status_code == 200, r.text
    return r.json()


def ship(admin, oid, item_id, qty, k=None):
    data = {"courier": "TEST_JNE", "tracking_no": f"TEST{key()[:6]}", "shipped_at": "2026-01-10T10:00", "notes": "",
            "items": json.dumps([{"item_id": item_id, "qty": qty}]), "idempotency_key": k or key()}
    return admin.post(f"{BASE_URL}/api/orders/{oid}/shipments", data=data)


# --- Multi payment: 3 different amounts + same amount twice with different keys
def test_multi_payments(admin, ctx):
    p = new_product(admin, ctx)
    o = mk_order(admin, [{"product_id": p["id"], "qty": 100}], ctx["ra"]["reseller"]["id"]).json()
    assert o["grand_total"] == 5000000
    for amt in (1000000, 1500000):
        r = admin.post(f"{BASE_URL}/api/orders/{o['id']}/payments", json={"amount": amt, "idempotency_key": key()})
        assert r.status_code == 200, r.text
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert d["order"]["total_paid"] == 2500000 and d["order"]["remaining"] == 2500000
    # same amount twice, different keys -> 2 legit payments
    for _ in range(2):
        r = admin.post(f"{BASE_URL}/api/orders/{o['id']}/payments", json={"amount": 1250000, "idempotency_key": key()})
        assert r.status_code == 200
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert len(d["payments"]) == 4
    assert d["order"]["total_paid"] == 5000000 and d["order"]["remaining"] == 0
    assert d["order"]["payment_status"] == "lunas"
    rd = ctx["ra"]["session"].get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert len(rd["payments"]) == 4


# --- Multi shipment 30/40/30 -> auto selesai
def test_multi_shipments(admin, ctx):
    p = new_product(admin, ctx)
    o = mk_order(admin, [{"product_id": p["id"], "qty": 100}], ctx["ra"]["reseller"]["id"]).json()
    iid = o["items"][0]["item_id"]
    for q, rem in ((30, 70), (40, 30), (30, 0)):
        r = ship(admin, o["id"], iid, q)
        assert r.status_code == 200, r.text
        d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()
        assert d["order"]["items"][0]["qty_remaining_ship"] == rem
    assert d["order"]["status"] == "selesai" and len(d["shipments"]) == 3
    assert [s["items"][0]["qty"] for s in d["shipments"]] == [30, 40, 30]
    assert ship(admin, o["id"], iid, 1).status_code == 422
    rd = ctx["ra"]["session"].get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert len(rd["shipments"]) == 3


# --- Double submit: same key sequential and concurrent
def test_payment_same_key_dedup(admin, ctx):
    p = new_product(admin, ctx)
    o = mk_order(admin, [{"product_id": p["id"], "qty": 10}], ctx["ra"]["reseller"]["id"]).json()
    k = key()
    a = admin.post(f"{BASE_URL}/api/orders/{o['id']}/payments", json={"amount": 100000, "idempotency_key": k})
    b = admin.post(f"{BASE_URL}/api/orders/{o['id']}/payments", json={"amount": 100000, "idempotency_key": k})
    assert a.status_code == 200 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    # concurrent
    k2 = key()
    res = []
    def go():
        res.append(admin.post(f"{BASE_URL}/api/orders/{o['id']}/payments", json={"amount": 200000, "idempotency_key": k2}))
    ts = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert all(r.status_code == 200 for r in res), [r.text for r in res]
    assert len({r.json()["id"] for r in res}) == 1
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert len(d["payments"]) == 2 and d["order"]["total_paid"] == 300000
    # cross-order key reuse -> 409
    o2 = mk_order(admin, [{"product_id": p["id"], "qty": 10}], ctx["ra"]["reseller"]["id"]).json()
    c = admin.post(f"{BASE_URL}/api/orders/{o2['id']}/payments", json={"amount": 100000, "idempotency_key": k})
    assert c.status_code == 409
    assert admin.get(f"{BASE_URL}/api/orders/{o2['id']}").json()["order"]["total_paid"] == 0


def test_shipment_same_key_dedup(admin, ctx):
    p = new_product(admin, ctx)
    o = mk_order(admin, [{"product_id": p["id"], "qty": 100}], ctx["ra"]["reseller"]["id"]).json()
    iid = o["items"][0]["item_id"]
    k = key()
    a = ship(admin, o["id"], iid, 30, k)
    b = ship(admin, o["id"], iid, 30, k)
    assert a.status_code == 200 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    # concurrent same key
    k2 = key()
    res = []
    def go():
        res.append(ship(admin, o["id"], iid, 20, k2))
    ts = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    codes = [r.status_code for r in res]
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert len(d["shipments"]) == 2, codes
    assert d["order"]["items"][0]["qty_shipped"] == 50, codes
    assert all(c == 200 for c in codes), [r.text for r in res]
    # concurrent DIFFERENT keys: both legit, must both persist or one fail cleanly (no orphan shipment)
    res2 = []
    def go2(q):
        res2.append(ship(admin, o["id"], iid, q))
    ts = [threading.Thread(target=go2, args=(q,)) for q in (10, 15)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    d = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()
    shipped_sum = sum(s["items"][0]["qty"] for s in d["shipments"])
    assert shipped_sum == d["order"]["items"][0]["qty_shipped"], ([r.status_code for r in res2], [r.text[:120] for r in res2])
    o2 = mk_order(admin, [{"product_id": p["id"], "qty": 10}], ctx["ra"]["reseller"]["id"]).json()
    c = ship(admin, o2["id"], o2["items"][0]["item_id"], 5, k)
    assert c.status_code == 409
    assert admin.get(f"{BASE_URL}/api/orders/{o2['id']}").json()["order"]["items"][0]["qty_shipped"] == 0


def test_order_same_key_dedup(admin, ctx):
    p = new_product(admin, ctx)
    s = ctx["ra"]["session"]
    k = key()
    a = mk_order(s, [{"product_id": p["id"], "qty": 10, "expected_price": 50000}], k=k)
    b = mk_order(s, [{"product_id": p["id"], "qty": 10, "expected_price": 50000}], k=k)
    assert a.status_code == 200 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    k2 = key()
    res = []
    def go():
        res.append(mk_order(s, [{"product_id": p["id"], "qty": 10, "expected_price": 50000}], k=k2))
    ts = [threading.Thread(target=go) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert all(r.status_code == 200 for r in res), [r.text for r in res]
    assert len({r.json()["id"] for r in res}) == 1
    # other user reusing key -> 409
    r = mk_order(ctx["rb"]["session"], [{"product_id": p["id"], "qty": 10}], k=k)
    assert r.status_code == 409


# --- Super admin protection
def test_super_admin_protection(admin, ctx):
    users = admin.get(f"{BASE_URL}/api/users").json()
    sa = [u for u in users if u.get("is_super_admin")]
    assert sa, "no super admin flagged"
    email = f"test_adm2_{ctx['run']}@example.com"
    u = admin.post(f"{BASE_URL}/api/users", json={"email": email, "name": "TEST_Admin2", "role": "admin", "password": "TestPass#123"})
    assert u.status_code == 200, u.text
    from conftest import login
    s2, r = login(email, "TestPass#123")
    assert r.status_code == 200
    s2.post(f"{BASE_URL}/api/auth/change-password", json={"current_password": "TestPass#123", "new_password": "TestPass#1234"})
    s2.headers.update({"X-CSRF-Token": s2.cookies.get("csrf_token")})
    x = s2.patch(f"{BASE_URL}/api/users/{sa[0]['id']}", json={"is_active": False})
    assert x.status_code == 403, x.text
    y = s2.post(f"{BASE_URL}/api/users/{sa[0]['id']}/reset-password", json={"new_password": "Hacked#12345"})
    assert y.status_code == 403
    admin.patch(f"{BASE_URL}/api/users/{u.json()['id']}", json={"is_active": False})
