"""Put QA stack into needs_manual (block) or unblock via CLI. Usage: python qa_iter8_block.py block|unblock"""
import sys

from qa_iter8_helpers import BACKUP, DB, LOCK, SUPER, cli, fire_async, kill9, login, restart_backend, wait_lock

if sys.argv[1] == "block":
    restart_backend(CLEANUP_TEST_DELAY=3)
    fire_async(login(*SUPER), ["orders", "products", "notifications"])
    lock = wait_lock(lambda l: l.get("state") == "deleting" and DB.orders.count_documents({}) == 0)
    kill9()
    restart_backend(CLEANUP_TEST_FAIL_RESTORE=1)
    print("BLOCKED", lock["backup"], DB.system_settings.find_one({"_id": LOCK})["state"])
else:
    lock = DB.system_settings.find_one({"_id": LOCK})
    out = cli(BACKUP / lock["backup"])
    print(out.stdout, out.stderr)
    restart_backend()
    print("LOCK", DB.system_settings.find_one({"_id": LOCK}))
