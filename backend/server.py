import asyncio
import logging

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app import config
from app.db import client, create_indexes, db
from app.maintenance import STATE as MAINTENANCE
from app.routes import auth, notifications, orders, products, reports, resellers, settings
from app.security import CSRFMiddleware, hash_password
from app.services import cleanup
from app.services.notifications import worker
from app.services.storage import ensure_dirs
from app.utils import now_utc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("relaylab")

app = FastAPI(title="RelayLab OMS API", version="1.0.0")

for r in (auth.router, auth.me_router, products.router, resellers.router, resellers.users_router,
          orders.router, orders.files_router, reports.router, notifications.router, settings.router):
    app.include_router(r)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


AUTH_SAFE = ("/api/auth/login", "/api/auth/logout", "/api/auth/refresh")


class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)
        path = request.url.path
        if path in AUTH_SAFE:
            return await call_next(request)
        blocked = MAINTENANCE["blocked"]
        if blocked:
            return JSONResponse(status_code=503, content={"detail": blocked["message"]})
        if path.startswith("/api/settings/cleanup"):
            return await call_next(request)
        if MAINTENANCE["active"]:
            return JSONResponse(status_code=503, content={"detail": "Sistem sedang melakukan pembersihan data. Coba lagi beberapa saat."})
        # Dihitung agar cleanup menunggu request tulis yang sudah berjalan selesai
        MAINTENANCE["inflight"] += 1
        try:
            return await call_next(request)
        finally:
            MAINTENANCE["inflight"] -= 1


app.add_middleware(MaintenanceMiddleware)
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
    try:
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log.warning("Folder backup %s tidak dapat dibuat: %s", config.BACKUP_DIR, e)
    await create_indexes()
    try:
        await cleanup.recover_journal(db)
    except Exception as e:
        log.exception("Pemeriksaan jurnal pembersihan gagal")
        lock = await db.system_settings.find_one({"_id": cleanup.LOCK_ID}) or {}
        cleanup.block(lock.get("backup"), f"pemeriksaan saat start gagal: {e}")
    await seed_admin()
    app.state.worker = asyncio.create_task(worker(db))


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "worker", None)
    if task:
        task.cancel()
    client.close()
