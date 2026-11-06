"""Iteration 5 revision tests: product without code, orders server-side pagination, reseller special hiding."""
import json
import uuid

from conftest import BASE_URL, RUN

LONG = "TEST_Relay Set Biled Headlamp (H11 + HB3) AOD + Biled Foglamp AOD"


def key():
    return uuid.uuid4().hex


# --- Products: no code
def test_product_create_without_code_and_price_history(admin):
    r = admin.post(f"{BASE_URL}/api/products", json={"name": f"{LONG} {RUN}", "voltage": "12", "price": 150000, "notes": ""})
    assert r.status_code == 200, r.text
    p = r.json()
    assert isinstance(p["id"], str) and p["name"] == f"{LONG} {RUN}" and p["voltage"] == "12"
    g = admin.get(f"{BASE_URL}/api/products/{p['id']}")
    assert g.status_code == 200 and g.json()["price"] == 150000
    u = admin.put(f"{BASE_URL}/api/products/{p['id']}", json={"name": p["name"], "voltage": "12", "price": 160000, "is_active": True, "notes": ""})
    assert u.status_code == 200, u.text
    assert u.json()["price_history"][-1]["old_price"] == 150000 and u.json()["price_history"][-1]["new_price"] == 160000


def test_product_validation(admin):
    assert admin.post(f"{BASE_URL}/api/products", json={"name": "TEST_Bad V", "voltage": "6", "price": 1}).status_code == 422
    assert admin.post(f"{BASE_URL}/api/products", json={"voltage": "12", "price": 1}).status_code == 422
    assert admin.post(f"{BASE_URL}/api/products", json={"name": "TEST_NoPrice", "voltage": "12"}).status_code == 422


def test_legacy_products_list_ok(admin):
    r = admin.get(f"{BASE_URL}/api/products")
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert len(items) > 0 and all("id" in x and "name" in x for x in items)


# --- Orders server-side pagination
def test_orders_pagination_shape_and_clamp(admin):
    r = admin.get(f"{BASE_URL}/api/orders?page=1&limit=10")
    assert r.status_code == 200
    d = r.json()
    assert set(["items", "total", "page", "limit", "pages"]) <= set(d)
    assert d["limit"] == 10 and len(d["items"]) <= 10 and d["pages"] == max((d["total"] + 9) // 10, 1)
    big = admin.get(f"{BASE_URL}/api/orders?page=9999&limit=10").json()
    assert big["page"] == big["pages"] and len(big["items"]) > 0
    neg = admin.get(f"{BASE_URL}/api/orders?page=-3&limit=7").json()
    assert neg["page"] == 1 and neg["limit"] == 10
    p2 = admin.get(f"{BASE_URL}/api/orders?page=2&limit=10").json()
    if d["total"] > 10:
        assert not ({x["id"] for x in d["items"]} & {x["id"] for x in p2["items"]})


def test_orders_filters_and_sort(admin, ctx):
    rs = ctx["rs"]["session"]
    o = rs.post(f"{BASE_URL}/api/orders", json={"items": [{"product_id": ctx["p2"]["id"], "qty": 3}], "idempotency_key": key()}).json()
    code = o["code"]
    q = admin.get(f"{BASE_URL}/api/orders", params={"q": code.split("-")[-1] + " " + code.split("-")[1]}).json()
    assert any(x["id"] == o["id"] for x in q["items"])
    q2 = admin.get(f"{BASE_URL}/api/orders", params={"q": code}).json()
    assert q2["total"] == 1 and q2["items"][0]["code"] == code
    st = admin.get(f"{BASE_URL}/api/orders", params={"status": "selesai", "limit": 100}).json()
    assert all(x["status"] == "selesai" for x in st["items"])
    pay = admin.get(f"{BASE_URL}/api/orders", params={"payment_status": "belum_ada_pembayaran", "limit": 100}).json()
    assert all(x["total_paid"] <= 0 for x in pay["items"])
    assert any(x["id"] == o["id"] for x in admin.get(f"{BASE_URL}/api/orders", params={"payment_status": "belum_ada_pembayaran", "q": code}).json()["items"])
    df = admin.get(f"{BASE_URL}/api/orders", params={"date_from": "2020-01-01", "date_to": "2020-01-02"}).json()
    assert df["total"] == 0 and df["page"] == 1 and df["pages"] == 1
    asc = admin.get(f"{BASE_URL}/api/orders", params={"sort": "grand_total", "order": "asc", "limit": 50}).json()["items"]
    vals = [x["grand_total"] for x in asc]
    assert vals == sorted(vals)
    desc = admin.get(f"{BASE_URL}/api/orders", params={"sort": "created_at", "order": "desc", "limit": 50}).json()["items"]
    ts = [x["created_at"] for x in desc]
    assert ts == sorted(ts, reverse=True)
    ctx["special_order"] = o


# --- Reseller special hiding
def test_reseller_me_profile_no_is_special(ctx):
    for k, mq in (("rs", 1), ("ra", 10)):
        s = ctx[k]["session"]
        me = s.get(f"{BASE_URL}/api/auth/me").json()
        assert me["reseller"]["min_qty"] == mq and "is_special" not in me["reseller"], me
        prof = s.get(f"{BASE_URL}/api/me/profile")
        assert prof.status_code == 200
        body = json.dumps(prof.json())
        assert "is_special" not in body and str(mq) in body
        assert "is_special" not in json.dumps(s.get(f"{BASE_URL}/api/orders").json())


def test_reseller_order_detail_hides_special_admin_sees(admin, ctx):
    o = ctx.get("special_order") or ctx["rs"]["session"].post(
        f"{BASE_URL}/api/orders", json={"items": [{"product_id": ctx["p2"]["id"], "qty": 1}], "idempotency_key": key()}).json()
    rd = ctx["rs"]["session"].get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert "is_special" not in json.dumps(rd)
    ad = admin.get(f"{BASE_URL}/api/orders/{o['id']}").json()
    assert ad["order"]["reseller_snapshot"]["is_special"] is True
    res = admin.get(f"{BASE_URL}/api/resellers").json()
    items = res if isinstance(res, list) else res.get("items", [])
    assert any(x.get("is_special") for x in items)
