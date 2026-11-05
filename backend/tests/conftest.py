import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "ainkarip@gmail.com"
ADMIN_PASSWORD = "RelayLab#Admin2026"
RUN = uuid.uuid4().hex[:6]


def login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return s, r
    s.headers.update({"X-CSRF-Token": s.cookies.get("csrf_token")})
    return s, r


def refresh_csrf(s):
    s.headers.update({"X-CSRF-Token": s.cookies.get("csrf_token")})


@pytest.fixture(scope="session")
def admin():
    s, r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="session")
def ctx(admin):
    """Create TEST_ products and resellers (regular A, regular B, special) with logins."""
    c = {"run": RUN}
    for key, code, name, volt, price in [
        ("p1", f"TEST_P1_{RUN}", f"TEST_Foglamp Std {RUN}", "12", 110000),
        ("p2", f"TEST_P2_{RUN}", f"TEST_Relay Dash {RUN}", "-", 100000),
    ]:
        r = admin.post(f"{BASE_URL}/api/products", json={"code": code, "name": name, "voltage": volt, "price": price})
        assert r.status_code == 200, r.text
        c[key] = r.json()
    pw = "TestPass#123"
    for key, special, wa in [("ra", False, f"0812{RUN[:4].encode().hex()[:7]}"), ("rb", False, "081299990001"), ("rs", True, "081299990002")]:
        email = f"test_{key}_{RUN}@example.com"
        wa_num = "0812" + str(int(uuid.uuid4().int % 10**8)).zfill(8)
        r = admin.post(f"{BASE_URL}/api/resellers", json={"name": f"TEST_Reseller {key} {RUN}", "wa": wa_num,
                                                            "is_special": special, "login_email": email, "login_password": pw})
        assert r.status_code == 200, r.text
        res = r.json()
        s, lr = login(email, pw)
        assert lr.status_code == 200, lr.text
        assert lr.json().get("must_change_password") is True
        cr = s.post(f"{BASE_URL}/api/auth/change-password", json={"current_password": pw, "new_password": pw + "x"})
        assert cr.status_code == 200, cr.text
        refresh_csrf(s)
        c[key] = {"reseller": res, "session": s, "email": email, "wa": wa_num}
    return c
