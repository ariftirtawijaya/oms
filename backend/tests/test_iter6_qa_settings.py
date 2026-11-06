"""Iteration 6 (QA stack ONLY: http://127.0.0.1:8088/order): branding + cleanup authz/preview (non-destructive).
Never point this at the preview URL - it holds the customer's real data."""
import json
import os
import uuid

import pytest
import requests

QA = os.environ.get("QA_BASE_URL", "http://127.0.0.1:8088/order").rstrip("/")
API = f"{QA}/api"
SUPER = ("superadmin@qa-relaylab.com", "SuperQA#2026")
ADMIN2 = ("admin2@qa-relaylab.com", "AdminQA#2026")
RESELLER = ("reseller1@qa-relaylab.com", "ResellerQA#2026")
T = "/tmp/qa/t"


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    s.headers["X-CSRF-Token"] = s.cookies.get("csrf_token")
    return s


@pytest.fixture(scope="module")
def sa():
    return login(*SUPER)


@pytest.fixture(scope="module")
def a2():
    return login(*ADMIN2)


@pytest.fixture(scope="module")
def rs():
    return login(*RESELLER)


def counts():
    import subprocess
    out = subprocess.run(["mongosh", "--quiet", "--port", "27018", "relaylab_oms_qa", "--eval",
                          "JSON.stringify(Object.fromEntries(['orders','order_payments','shipments','resellers','products','notification_logs','audit_logs','users','system_settings'].map(c=>[c,db[c].countDocuments()])))"],
                         capture_output=True, text=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


# --- Branding (public read)
def test_branding_public_get():
    r = requests.get(f"{API}/branding")
    assert r.status_code == 200
    d = r.json()
    assert {"app_name", "tagline", "logo_file", "favicon_file"} <= set(d)
    if d["logo_file"]:
        f = requests.get(f"{API}/branding/files/{d['logo_file']}")
        assert f.status_code == 200 and f.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_branding_file_traversal_and_missing():
    assert requests.get(f"{API}/branding/files/nope.png").status_code == 404
    assert requests.get(f"{API}/branding/files/..%2F..%2Fbe.env").status_code == 404


# --- Branding authz
def test_branding_write_requires_admin(rs):
    assert requests.put(f"{API}/settings/branding", data={"app_name": "X1"}).status_code in (401, 403)
    assert rs.put(f"{API}/settings/branding", data={"app_name": "HACKED"}).status_code == 403
    assert rs.post(f"{API}/settings/branding/reset").status_code == 403


def test_branding_admin2_can_edit_keeps_files(a2):
    before = requests.get(f"{API}/branding").json()
    r = a2.put(f"{API}/settings/branding", data={"app_name": "TEST_Admin2 Brand", "tagline": before["tagline"]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["app_name"] == "TEST_Admin2 Brand" and d["logo_file"] == before["logo_file"] and d["favicon_file"] == before["favicon_file"]
    assert requests.get(f"{API}/branding").json()["app_name"] == "TEST_Admin2 Brand"
    r = a2.put(f"{API}/settings/branding", data={"app_name": before["app_name"], "tagline": before["tagline"]})
    assert r.status_code == 200 and r.json()["app_name"] == before["app_name"]


# --- Branding validation
@pytest.mark.parametrize("field,fname,src,ctype,expect", [
    ("logo", "fake.png", "fake.png", "image/png", "bukan gambar"),
    ("logo", "big.png", "big.png", "image/png", "maksimal 2 MB"),
    ("favicon", "resi.jpg", "resi.jpg", "image/jpeg", "Format Favicon"),
    ("logo", "doc.txt", "fake.png", "text/plain", "Format Logo"),
])
def test_branding_invalid_files_rejected(sa, field, fname, src, ctype, expect):
    before = requests.get(f"{API}/branding").json()
    with open(f"{T}/{src}", "rb") as fh:
        r = sa.put(f"{API}/settings/branding", data={"app_name": "TEST_Should Not Save"}, files={field: (fname, fh, ctype)})
    assert r.status_code == 422, r.text
    assert expect in r.json()["detail"]
    assert requests.get(f"{API}/branding").json() == before


def test_branding_name_validation(sa):
    assert sa.put(f"{API}/settings/branding", data={"app_name": "X"}).status_code == 422
    assert sa.put(f"{API}/settings/branding", data={"app_name": "OK Name", "tagline": "x" * 81}).status_code == 422


# --- order_seq preserved after branding save
def test_order_seq_continues_after_branding(rs):
    c = counts()
    assert c["system_settings"] >= 2  # branding + order_seq:*
    prods = rs.get(f"{API}/products").json()
    items = prods if isinstance(prods, list) else prods["items"]
    p = items[0]
    r = rs.post(f"{API}/orders", json={"items": [{"product_id": p["id"], "qty": 1, "expected_price": p.get("price")}],
                                         "notes": "TEST_iter6 seq", "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    assert code.startswith("RL-") and int(code.rsplit("-", 1)[1]) >= 3, code


# --- Cleanup authz
@pytest.mark.parametrize("who", ["a2", "rs"])
def test_cleanup_forbidden_for_non_super(who, a2, rs):
    s = {"a2": a2, "rs": rs}[who]
    assert s.post(f"{API}/settings/cleanup/preview", json={"categories": ["audit"]}).status_code == 403
    assert s.post(f"{API}/settings/cleanup/execute", json={"categories": ["audit"], "confirm_text": "HAPUS DATA",
                                                           "password": "x"}).status_code == 403
    assert s.get(f"{API}/settings/cleanup/history").status_code == 403


def test_cleanup_unauthenticated():
    assert requests.get(f"{API}/settings/cleanup/history").status_code == 401


# --- Cleanup preview rules
def test_preview_resellers_only_blocked(sa):
    r = sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["resellers"]})
    assert r.status_code == 200
    d = r.json()
    assert d["blocking"] and "order" in d["blocking"][0].lower()
    assert d["counts"]["resellers"]["users"] >= 1


def test_execute_resellers_only_422_nothing_deleted(sa):
    before = counts()
    r = sa.post(f"{API}/settings/cleanup/execute", json={"categories": ["resellers"], "confirm_text": "HAPUS DATA",
                                                          "password": SUPER[1]})
    assert r.status_code == 422, r.text
    assert counts()["resellers"] == before["resellers"]


def test_preview_reset_seq_without_orders_blocked(sa):
    d = sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["audit"], "reset_order_seq": True}).json()
    assert any("Reset nomor urut" in b for b in d["blocking"])


def test_preview_products_warning_and_orders_counts(sa):
    d = sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["products"]}).json()
    assert not d["blocking"] and any("order lama" in w for w in d["warnings"])
    d = sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["orders"], "reset_order_seq": True}).json()
    o = d["counts"]["orders"]
    assert o["orders"] >= 2 and o["order_payments"] >= 2 and o["shipments"] >= 1 and o["resi_files"] >= 1
    assert o["order_seq_counters"] >= 1
    d = sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["audit"]}).json()
    assert any("keamanan" in w for w in d["warnings"])


def test_preview_invalid_categories(sa):
    assert sa.post(f"{API}/settings/cleanup/preview", json={"categories": []}).status_code == 422
    assert sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["users"]}).status_code == 422
    assert sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["orders", "bogus"]}).status_code == 422


def test_execute_wrong_confirm_and_password(sa):
    before = counts()
    r = sa.post(f"{API}/settings/cleanup/execute", json={"categories": ["audit"], "confirm_text": "hapus data", "password": SUPER[1]})
    assert r.status_code == 422 and "HAPUS DATA" in r.json()["detail"]
    r = sa.post(f"{API}/settings/cleanup/execute", json={"categories": ["audit"], "confirm_text": "HAPUS DATA", "password": "WrongPass#1"})
    assert r.status_code == 403
    after = counts()
    assert after["audit_logs"] >= before["audit_logs"] and after["orders"] == before["orders"]
    h = sa.get(f"{API}/settings/cleanup/history").json()
    assert h and h[0]["result"] == "ditolak_password_salah" and h[0]["categories"] == ["audit"]
    assert "_id" not in h[0] or isinstance(h[0]["_id"], str)
    # super admin session still valid after wrong password
    assert sa.get(f"{API}/auth/me").status_code == 200
