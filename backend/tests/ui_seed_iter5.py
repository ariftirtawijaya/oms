"""UI seed for iteration 5: TEST_ resellers, 12 TEST_ products, order with 13 items, 11 payments, shipments."""
import json
import uuid

from conftest import BASE_URL, login

R = uuid.uuid4().hex[:5]
s, r = login("test_admin@relaylab-qa.com", "TestAdmin#2026")
assert r.status_code == 200, r.text
out = {"run": R, "products": []}
LONG = "TEST_Relay Set Biled Headlamp (H11 + HB3) AOD + Biled Foglamp AOD"
for i in range(12):
    name = f"{LONG} V{i} {R}" if i < 3 else f"TEST_Relay Item {i} {R}"
    p = s.post(f"{BASE_URL}/api/products", json={"name": name, "voltage": "12" if i % 2 else "24", "price": 10000 + i * 1000}).json()
    out["products"].append(p["id"])
pw = "TestPass#123"
for k, sp in (("special", True), ("regular", False)):
    email = f"test_ui5_{k}_{R}@example.com"
    wa = "0813" + str(uuid.uuid4().int % 10**8).zfill(8)
    res = s.post(f"{BASE_URL}/api/resellers", json={"name": f"TEST_UI5 {k} {R}", "wa": wa, "is_special": sp,
                                                     "login_email": email, "login_password": pw}).json()
    rs, lr = login(email, pw)
    rs.headers.update({"X-CSRF-Token": rs.cookies.get("csrf_token")})
    cr = rs.post(f"{BASE_URL}/api/auth/change-password", json={"current_password": pw, "new_password": pw + "x"})
    assert cr.status_code == 200, cr.text
    out[k] = {"id": res["id"], "email": email, "password": pw + "x"}
items = [{"product_id": pid, "qty": 10} for pid in out["products"]] + [{"custom_name": "TEST_Custom Relay Panjang Sekali Untuk Uji", "qty": 10}]
o = s.post(f"{BASE_URL}/api/orders", json={"items": items, "idempotency_key": uuid.uuid4().hex, "reseller_id": out["special"]["id"]}).json()
out["order"] = {"id": o["id"], "code": o["code"], "grand_total": o["grand_total"]}
for i in range(11):
    pr = s.post(f"{BASE_URL}/api/orders/{o['id']}/payments", json={"amount": 1000 + i, "idempotency_key": uuid.uuid4().hex})
    assert pr.status_code == 200, pr.text
first = o["items"][0]["item_id"]
for _ in range(11):
    data = {"courier": "TEST_JNE", "tracking_no": f"TEST{uuid.uuid4().hex[:6]}", "shipped_at": "2026-01-10T10:00", "notes": "",
            "items": json.dumps([{"item_id": first, "qty": 0 or 1}]), "idempotency_key": uuid.uuid4().hex}
    sr = s.post(f"{BASE_URL}/api/orders/{o['id']}/shipments", data=data)
    if sr.status_code != 200:
        print("ship fail", sr.status_code, sr.text[:200])
        break
print(json.dumps(out))
