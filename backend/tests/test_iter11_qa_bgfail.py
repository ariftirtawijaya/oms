"""Iteration 11: background recovery failure safety (_spawn_recovery wrapper) on QA stack ONLY.
Forces recover_journal to raise OUTSIDE restore_and_verify by making security_logs inserts fail (Mongo validator),
then checks journal -> needs_manual, STATE.blocked -> manual message (not stuck on 'memulihkan'), generic 503.
Run: cd /app/backend/tests && python -m pytest -p no:xdist -o addopts='' -s test_iter11_qa_bgfail.py"""
import time

import requests

from qa_iter8_helpers import (API, DB, LOCK, RESELLER, SUPER, add_pending_notifs, BACKUP, cli, diff, execute, history,
                              login, restart_backend, snapshot, wait_lock)

GENERIC = "Sistem sedang dalam pemeliharaan data. Perubahan data sementara tidak dapat disimpan, silakan coba lagi nanti."
CATS = ["orders", "resellers", "products"]


def _validator(on: bool):
    v = {"$jsonSchema": {"required": ["__iter11_never__"]}} if on else {}
    DB.command({"collMod": "security_logs", "validator": v, "validationLevel": "strict" if on else "off",
                "validationAction": "error"})


def test_bg_recovery_raises_goes_needs_manual():
    restart_backend(CLEANUP_TEST_FAIL_AFTER="cancel:order_payments")
    s, rs = login(*SUPER), login(*RESELLER)
    before = snapshot()
    _validator(True)
    try:
        try:
            r = execute(s, CATS)
            resp = (r.status_code, r.text[:200])
        except requests.RequestException as e:
            resp = ("ERR", str(e)[:120])
        lock = wait_lock(lambda l: l.get("state") == "needs_manual", timeout=30)
    finally:
        _validator(False)
    print("exec:", resp, "lock:", {k: lock.get(k) for k in ("state", "problems", "backup")})
    assert any("pemulihan latar error" in p for p in lock.get("problems", []))
    st = s.get(f"{API}/settings/cleanup/status").json()
    print("status.blocked:", st["blocked"])
    assert st["blocked"]["backup"] == lock["backup"]
    assert "Pulihkan manual" in st["blocked"]["message"] and "memulihkan otomatis" not in st["blocked"]["message"]
    w = rs.put(f"{API}/me/profile", json={"address": "TEST_iter11"})
    print("reseller write:", w.status_code, w.text)
    assert w.status_code == 503 and w.json()["detail"] == GENERIC and lock["backup"] not in w.text
    assert "Pemulihan latar gagal" in open("/tmp/qa/backend.log").read()
    # restore_and_verify itself succeeded before the failing security log -> data already back
    assert diff(before, snapshot()) == [], diff(before, snapshot())[:5]
    # close journal via CLI, restart -> unblocked
    o = cli(BACKUP / lock["backup"])
    print(o.stdout[-400:], o.stderr[-300:])
    assert o.returncode == 0
    assert DB.system_settings.find_one({"_id": LOCK}) is None
    restart_backend()
    s = login(*SUPER)
    assert s.get(f"{API}/settings/cleanup/status").json()["blocked"] is None
    print("history:", [h["result"] for h in history(s)[:3]])
    add_pending_notifs()
    assert s.post(f"{API}/products", json={}).status_code == 422
