"""Helper: create TEST_ products and an order (50 pcs + custom) for UI testing of reseller test_ui_9774."""
import uuid
import sys
sys.path.insert(0, "/app/backend/tests")
from conftest import BASE_URL, login  # noqa

s, _ = login("ainkarip@gmail.com", "RelayLab#Admin2026")
for i in range(6):
    s.post(f"{BASE_URL}/api/products", json={"code": f"TEST_PG{i}_9774", "name": f"TEST_Pager Headlamp AOD {i}", "voltage": "24", "price": 50000 + i})
prods = s.get(f"{BASE_URL}/api/products").json()
p = [x for x in prods if x["code"] == "TEST_UI9774"][0]
res = [r for r in s.get(f"{BASE_URL}/api/resellers").json() if r["name"] == "TEST_UI Reseller 9774"][0]
o = s.post(f"{BASE_URL}/api/orders", json={"reseller_id": res["id"], "idempotency_key": uuid.uuid4().hex,
          "items": [{"product_id": p["id"], "qty": 50}, {"custom_name": "TEST_Custom Kabel 2m", "qty": 10}]}).json()
print(o["id"], o["code"], [(i["item_id"], i["is_custom"]) for i in o["items"]])
open("/tmp/resi.png", "wb").write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
open("/tmp/bad.txt", "w").write("not an image")
