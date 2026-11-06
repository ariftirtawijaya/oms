import io, json, uuid
import requests
from PIL import Image

B = "http://127.0.0.1:8088/order/api"


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{B}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    s.headers["X-CSRF-Token"] = s.cookies.get("csrf_token", path="/order")
    return s


def jpg():
    buf = io.BytesIO(); Image.new("RGB", (40, 30), "orange").save(buf, "JPEG"); return buf.getvalue()


adm = login("superadmin@qa-relaylab.com", "SuperQA#2026")
r = adm.post(f"{B}/users", json={"email": "admin2@qa-relaylab.com", "name": "TEST_Admin Biasa", "role": "admin", "password": "AdminQA#2026", "must_change_password": False})
print("admin2", r.status_code)
pids = []
for i in range(1, 33):
    r = adm.post(f"{B}/products", json={"name": f"TEST_Relay Set {i:02d}", "voltage": "12" if i % 2 else "24", "price": 10000 + i * 500})
    pids.append(r.json()["id"])
r = adm.post(f"{B}/resellers", json={"name": "TEST_Reseller Satu", "wa": "628111000111", "is_special": True,
                                    "login_email": "reseller1@qa-relaylab.com", "login_password": "ResellerQA#2026"})
print("reseller", r.status_code)
res = login("reseller1@qa-relaylab.com", "ResellerQA#2026")
r = res.post(f"{B}/orders", json={"items": [{"product_id": p, "qty": 2} for p in pids], "idempotency_key": uuid.uuid4().hex})
print("orderA", r.status_code, r.json().get("code"))
oa = r.json()
r = res.post(f"{B}/orders", json={"items": [{"product_id": pids[0], "qty": 3}], "idempotency_key": uuid.uuid4().hex})
ob = r.json()
print("orderB", r.status_code, ob.get("code"))
adm.post(f"{B}/orders/{oa['id']}/payments", json={"amount": 100000, "idempotency_key": uuid.uuid4().hex})
adm.post(f"{B}/orders/{oa['id']}/payments", json={"amount": 50000, "idempotency_key": uuid.uuid4().hex})
items = oa["items"][:7]
r = adm.post(f"{B}/orders/{oa['id']}/shipments", data={"courier": "JNE", "tracking_no": "TESTRESI001", "shipped_at": "2026-11-06T10:00:00",
                                                      "items": json.dumps([{"item_id": it["item_id"], "qty": 2} for it in items]),
                                                      "idempotency_key": uuid.uuid4().hex}, files={"photo": ("resi.jpg", jpg(), "image/jpeg")})
print("shipment", r.status_code)
print("ORDER_A", oa["id"], oa["code"])
print("ORDER_B", ob["id"], ob["code"])
