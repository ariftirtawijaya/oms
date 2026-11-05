"""Seed TEST_ data for iteration-2 UI testing: products, regular+special reseller logins, 100pcs order."""
import json
import sys
import uuid
sys.path.insert(0, "/app/backend/tests")
from conftest import BASE_URL, login  # noqa

R = uuid.uuid4().hex[:4]
s, _ = login("ainkarip@gmail.com", "RelayLab#Admin2026")
out = {"run": R}
prods = {}
for k, price in [("A", 50000), ("B", 110000)] + [(f"G{i}", 60000 + i) for i in range(12)]:
    r = s.post(f"{BASE_URL}/api/products", json={"code": f"TEST_{k}_{R}", "name": f"TEST_Relay {k} {R}", "voltage": "12", "price": price})
    prods[k] = r.json()
out["products"] = {k: v["id"] for k, v in prods.items()}
for key, special in [("reg", False), ("spc", True)]:
    email = f"test_ui{key}_{R}@example.com"
    wa = "0813" + str(uuid.uuid4().int % 10**8).zfill(8)
    res = s.post(f"{BASE_URL}/api/resellers", json={"name": f"TEST_UI {key} {R}", "wa": wa, "is_special": special,
                                                     "login_email": email, "login_password": "TestPass#123"}).json()
    rs, _ = login(email, "TestPass#123")
    rs.post(f"{BASE_URL}/api/auth/change-password", json={"current_password": "TestPass#123", "new_password": "TestPass#1234"})
    out[key] = {"email": email, "password": "TestPass#1234", "reseller_id": res["id"]}
o = s.post(f"{BASE_URL}/api/orders", json={"reseller_id": out["reg"]["reseller_id"], "idempotency_key": uuid.uuid4().hex,
          "items": [{"product_id": prods["A"]["id"], "qty": 100}]}).json()
out["order100"] = {"id": o["id"], "code": o["code"], "total": o["grand_total"]}
o2 = s.post(f"{BASE_URL}/api/orders", json={"reseller_id": out["reg"]["reseller_id"], "idempotency_key": uuid.uuid4().hex,
           "items": [{"product_id": prods["B"]["id"], "qty": 10}]}).json()
out["order_snap"] = {"id": o2["id"], "code": o2["code"]}
json.dump(out, open("/tmp/ui_seed.json", "w"), indent=1)
open("/tmp/resi.png", "wb").write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
print(json.dumps(out, indent=1))
