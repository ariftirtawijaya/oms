import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import HTTPException

JKT = ZoneInfo("Asia/Jakarta")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JKT).strftime("%d-%m-%Y %H:%M")


def rupiah(n: Optional[int]) -> str:
    if n is None:
        return "Menunggu Penentuan Admin"
    sign = "-" if n < 0 else ""
    return f"{sign}Rp{abs(int(n)):,}".replace(",", ".")


def voltage_label(v: Optional[str]) -> str:
    v = (v or "").strip()
    if not v or v == "-":
        return ""
    return v if v.upper().endswith("V") else f"{v}V"


def item_display(name: str, voltage: Optional[str]) -> str:
    vl = voltage_label(voltage)
    return f"{name} {vl}".strip()


def normalize_phone(raw: Optional[str]) -> str:
    if not raw:
        return ""
    s = str(raw).split("@")[0]
    digits = re.sub(r"\D", "", s)
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    return digits


def to_oid(value: Any, label: str = "Data") -> ObjectId:
    try:
        return ObjectId(str(value))
    except Exception:
        raise HTTPException(status_code=404, detail=f"{label} tidak ditemukan.")


def jkt_range_to_utc(date_from: Optional[date], date_to: Optional[date]) -> dict:
    q: dict = {}
    if date_from:
        q["$gte"] = datetime.combine(date_from, time.min, tzinfo=JKT).astimezone(timezone.utc)
    if date_to:
        q["$lt"] = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=JKT).astimezone(timezone.utc)
    return q


def ser(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, list):
        return [ser(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in ("password_hash", "token_version"):
                continue
            out["id" if k == "_id" else k] = ser(v)
        return out
    return value


async def audit(db, actor: Optional[dict], action: str, entity: str, entity_id: Any, data: Optional[dict] = None):
    await db.audit_logs.insert_one({
        "actor_id": actor["_id"] if actor else None,
        "actor_name": actor.get("name") if actor else "Sistem",
        "action": action,
        "entity": entity,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "data": data or {},
        "created_at": now_utc(),
    })
