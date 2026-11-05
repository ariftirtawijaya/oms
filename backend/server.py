import asyncio
import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app import config
from app.db import client, create_indexes, db
from app.routes import auth, notifications, orders, products, reports, resellers
from app.security import CSRFMiddleware, hash_password
from app.services.notifications import worker
from app.services.storage import ensure_dirs
from app.utils import now_utc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("relaylab")

app = FastAPI(title="RelayLab OMS API", version="1.0.0")

for r in (auth.router, auth.me_router, products.router, resellers.router, resellers.users_router,
          orders.router, orders.files_router, reports.router, notifications.router):
    app.include_router(r)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


app.add_middleware(CSRFMiddleware)
if config.CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])


async def seed_admin():
    if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
        if not await db.users.find_one({"role": "admin"}):
            log.warning("ADMIN_EMAIL/ADMIN_PASSWORD belum diatur; Super Admin awal tidak dibuat.")
        return
    if await db.users.find_one({"email": config.ADMIN_EMAIL}):
        return
    await db.users.insert_one({
        "email": config.ADMIN_EMAIL, "name": config.ADMIN_NAME, "role": "admin", "reseller_id": None,
        "password_hash": hash_password(config.ADMIN_PASSWORD), "is_active": True, "is_super_admin": True,
        "must_change_password": False, "token_version": 0, "created_at": now_utc(),
    })
    log.info("Super Admin awal dibuat: %s", config.ADMIN_EMAIL)


@app.on_event("startup")
async def startup():
    ensure_dirs()
    await create_indexes()
    await seed_admin()
    app.state.worker = asyncio.create_task(worker(db))


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "worker", None)
    if task:
        task.cancel()
    client.close()
