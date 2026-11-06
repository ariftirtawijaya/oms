"""Iteration 9 UI helper: `python qa_iter9_block.py block` -> D1-style blocked state; `unblock <folder>` -> CLI + restart."""
import sys

from qa_iter8_helpers import BACKUP, DB, LOCK, SUPER, add_pending_notifs, cli, fire_async, kill9, login, restart_backend, wait_lock

if sys.argv[1] == "block":
    add_pending_notifs()
    restart_backend(CLEANUP_TEST_DELAY=3)
    fire_async(login(*SUPER), ["orders", "products", "notifications"])
    lock = wait_lock(lambda l: l.get("state") == "deleting" and DB.orders.count_documents({}) == 0)
    kill9()
    restart_backend(CLEANUP_TEST_FAIL_RESTORE=1)
    print("BLOCKED", lock["backup"], DB.system_settings.find_one({"_id": LOCK})["state"])
else:
    out = cli(BACKUP / sys.argv[2])
    print(out.stdout, out.stderr, out.returncode)
    restart_backend()
    DB.notification_logs.update_many({"kind": "TEST_iter8_pending"}, {"$set": {"status": "pending"}, "$unset": {"last_error": ""}})
    print("LOCK", DB.system_settings.find_one({"_id": LOCK}))
