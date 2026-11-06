from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from app import config

client = AsyncIOMotorClient(config.MONGO_URL, tz_aware=True)
db = client[config.DB_NAME]

STR_KEY = {"idempotency_key": {"$type": "string"}}


async def create_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("reseller_id")
    await db.resellers.create_index("wa_normalized")
    await db.resellers.create_index("name")
    try:
        await db.products.drop_index("code_1")
    except Exception:
        pass
    await db.products.create_index([("name", ASCENDING), ("voltage", ASCENDING)])
    await db.orders.create_index("code", unique=True)
    await db.orders.create_index([("reseller_id", ASCENDING), ("created_at", DESCENDING)])
    await db.orders.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    await db.orders.create_index("idempotency_key", unique=True, partialFilterExpression=STR_KEY)
    await db.order_payments.create_index([("order_id", ASCENDING), ("paid_at", ASCENDING)])
    await db.order_payments.create_index("idempotency_key", unique=True, partialFilterExpression=STR_KEY)
    await db.shipments.create_index([("order_id", ASCENDING), ("shipped_at", ASCENDING)])
    await db.shipments.create_index("idempotency_key", unique=True, partialFilterExpression=STR_KEY)
    await db.shipments.create_index("photo_filename")
    await db.notification_logs.create_index([("status", ASCENDING), ("next_attempt_at", ASCENDING)])
    await db.notification_logs.create_index([("created_at", DESCENDING)])
    await db.announcement_states.create_index("sender", unique=True)
    await db.announcement_states.create_index("expires_at", expireAfterSeconds=0)
    await db.audit_logs.create_index([("created_at", DESCENDING)])
    await db.audit_logs.create_index([("entity", ASCENDING), ("entity_id", ASCENDING)])
    await db.login_attempts.create_index("identifier", unique=True)
    await db.webhook_events.create_index("key", unique=True)
    await db.webhook_events.create_index("created_at", expireAfterSeconds=86400)
    await db.security_logs.create_index([("created_at", DESCENDING)])
