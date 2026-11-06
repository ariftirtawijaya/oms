"""Iteration 6 DESTRUCTIVE cleanup flow (QA stack ONLY, port 27018 DB relaylab_oms_qa). Run serially: -n 0.
Order: audit -> products -> backup-failure -> maintenance 503 -> orders(+pending notif cancel) -> manual restore -> orders again -> resellers."""
import glob
import json
import os
import subprocess
import threading
import time
import uuid

import pytest
import requests

from test_iter6_qa_settings import API, SUPER, ADMIN2, RESELLER, login, counts

BACKUP = "/tmp/qa/backups"
RESI = "/tmp/qa/uploads/resi"


def mongo(js):
    out = subprocess.run(["mongosh", "--quiet", "--port", "27018", "relaylab_oms_qa", "--eval", js], capture_output=True, text=True)
    return out.stdout.strip()


def execute(s, cats, reset=False, pw=SUPER[1]):
    return s.post(f"{API}/settings/cleanup/execute", json={"categories": cats, "reset_order_seq": reset,
                                                            "confirm_text": "HAPUS DATA", "password": pw}, timeout=60)


@pytest.fixture(scope="module")
def sa():
    return login(*SUPER)


# (b) audit only
def test_b_audit_only(sa):
    hist_before = len(sa.get(f"{API}/settings/cleanup/history").json())
    r = execute(sa, ["audit"])
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "berhasil"
    c = counts()
    assert c["audit_logs"] == 0 and c["orders"] >= 3
    h = sa.get(f"{API}/settings/cleanup/history").json()
    assert len(h) == hist_before + 1 and h[0]["categories"] == ["audit"]
    assert sa.get(f"{API}/audit-logs").status_code == 200


# (c) products only
def test_c_products_only_orders_keep_snapshots(sa):
    o = sa.get(f"{API}/orders?page=1&limit=10").json()["items"][0]
    detail_before = sa.get(f"{API}/orders/{o['id']}").json()["order"]
    r = execute(sa, ["products"])
    assert r.status_code == 200, r.text
    c = counts()
    assert c["products"] == 0 and c["resellers"] >= 1 and c["orders"] >= 3
    d = sa.get(f"{API}/orders/{o['id']}")
    assert d.status_code == 200
    it_b, it_a = detail_before["items"][0], d.json()["order"]["items"][0]
    assert it_a["product_name_snapshot"] == it_b["product_name_snapshot"] and it_a["unit_price_snapshot"] == it_b["unit_price_snapshot"]
    rs = login(*RESELLER)
    p = rs.get(f"{API}/products")
    assert p.status_code == 200


# backup failure (chmod 000 is bypassed by root, so BACKUP_DIR is replaced by a plain file instead)
def test_backup_failure_via_file_blocker(sa):
    """Make BACKUP_DIR unusable even for root: replace with a regular file temporarily."""
    before = counts()
    os.rename(BACKUP, BACKUP + ".bak")
    open(BACKUP, "w").close()
    try:
        r = execute(sa, ["orders"])
    finally:
        os.remove(BACKUP)
        os.rename(BACKUP + ".bak", BACKUP)
    assert r.status_code == 500, r.text
    assert "Backup gagal dibuat" in r.json()["detail"]
    after = counts()
    assert after["orders"] == before["orders"] and after["shipments"] == before["shipments"]
    h = sa.get(f"{API}/settings/cleanup/history").json()
    assert h[0]["result"] == "dibatalkan_backup_gagal"
    # lock released & maintenance off
    assert sa.put(f"{API}/settings/branding", data={"app_name": requests.get(f"{API}/branding").json()["app_name"],
                                                     "tagline": requests.get(f"{API}/branding").json()["tagline"]}).status_code == 200


# (d) orders only (+ pending notif cancel) and 503 during cleanup
def test_d_orders_only_with_maintenance_and_notif_cancel(sa):
    mongo('const o=db.orders.findOne(); db.notification_logs.insertOne({order_id:o._id, status:"pending", type:"TEST_iter6", target:"628000000009", message:"TEST_iter6 pending", attempts:0, created_at:new Date(), next_attempt_at:new Date(Date.now()+3600000)})')
    pv = sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["orders"]}).json()
    assert pv["counts"]["orders"]["notifications_cancelled"] >= 1 and any("dibatalkan" in w for w in pv["warnings"])
    resi_before = set(os.listdir(RESI))
    assert resi_before
    a2 = login(*ADMIN2)
    codes = {}

    def probe():
        time.sleep(0.4)
        codes["w"] = a2.put(f"{API}/settings/branding", data={"app_name": "TEST_During Cleanup"}).status_code
        codes["r"] = a2.get(f"{API}/orders?page=1&limit=10").status_code

    t = threading.Thread(target=probe)
    t.start()
    r = execute(sa, ["orders"])
    t.join()
    assert r.status_code == 200, r.text
    assert codes["w"] == 503, codes
    assert codes["r"] == 200
    res = r.json()
    assert res["deleted"]["orders"] >= 3 and res["deleted"]["notifications_cancelled"] >= 1
    c = counts()
    assert c["orders"] == 0 and c["order_payments"] == 0 and c["shipments"] == 0 and c["resellers"] >= 1
    assert "pending" not in mongo('db.notification_logs.distinct("status")')
    assert '"cancelled"' in mongo('JSON.stringify(db.notification_logs.distinct("status"))')
    assert not (resi_before & set(os.listdir(RESI)))
    folder = os.path.join(BACKUP, res["backup"])
    for f in ("orders.jsonl", "order_payments.jsonl", "shipments.jsonl", "manifest.json"):
        assert os.path.isfile(os.path.join(folder, f)), f
    assert set(os.listdir(os.path.join(folder, "files", "resi"))) == resi_before
    # seq counter kept (reset not chosen)
    assert "order_seq:" in mongo('JSON.stringify(db.system_settings.find().toArray())')
    for ep in ("dashboard", "reports/admin"):
        assert sa.get(f"{API}/{ep}").status_code == 200, ep
    lst = sa.get(f"{API}/orders?page=1&limit=10").json()
    assert lst["total"] == 0 and lst["items"] == []
    rs = login(*RESELLER)
    assert rs.get(f"{API}/dashboard").status_code == 200
    assert rs.get(f"{API}/reports/reseller").status_code == 200
    pytest.backup_folder = folder


# manual restore CLI
def test_manual_restore_cli(sa):
    folder = getattr(pytest, "backup_folder", None) or sorted(glob.glob(f"{BACKUP}/cleanup-*"))[-1]
    env = dict(os.environ)
    for line in open("/tmp/qa/be.env"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            env[k] = v.strip('"')
    p = subprocess.run(["python", "-m", "app.restore_cleanup", folder], cwd="/app/backend", env=env, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    c = counts()
    assert c["orders"] >= 3 and c["shipments"] >= 1 and c["order_payments"] >= 2
    assert set(os.listdir(os.path.join(folder, "files", "resi"))) <= set(os.listdir(RESI))
    o = sa.get(f"{API}/orders?page=1&limit=10").json()
    assert o["total"] >= 3


# multi-category orders+notifications+audit with reset seq
def test_multi_orders_notifications_audit_reset_seq(sa):
    r = execute(sa, ["orders", "notifications", "audit"], reset=True)
    assert r.status_code == 200, r.text
    d = r.json()["deleted"]
    assert d["order_seq_counters"] >= 1 and "notifications_cancelled" not in d
    c = counts()
    assert c["orders"] == 0 and c["notification_logs"] == 0 and c["audit_logs"] <= 1
    assert "order_seq:" not in mongo('JSON.stringify(db.system_settings.find().toArray())')
    assert '"branding"' in mongo('JSON.stringify(db.system_settings.find().toArray())')


# (e) resellers allowed now
def test_e_resellers_only_now_allowed(sa):
    pv = sa.post(f"{API}/settings/cleanup/preview", json={"categories": ["resellers"]}).json()
    assert not pv["blocking"]
    r = execute(sa, ["resellers"])
    assert r.status_code == 200, r.text
    c = counts()
    assert c["resellers"] == 0
    rl = requests.post(f"{API}/auth/login", json={"email": RESELLER[0], "password": RESELLER[1]})
    assert rl.status_code == 401
    for who in (SUPER, ADMIN2):
        assert requests.post(f"{API}/auth/login", json={"email": who[0], "password": who[1]}).status_code == 200
    assert sa.get(f"{API}/auth/me").status_code == 200
