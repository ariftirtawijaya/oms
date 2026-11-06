from collections import OrderedDict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.db import db
from app.security import get_current_user, require_admin
from app.services.orders import enrich
from app.utils import JKT, jkt_range_to_utc, now_utc, ser, to_oid

router = APIRouter(prefix="/api", tags=["reports"])
PROJ = {"status_history": 0, "price_adjustments": 0, "idempotency_key": 0}


def summarize(orders: list) -> dict:
    return {
        "order_count": len(orders),
        "total_qty": sum(o["total_qty"] for o in orders),
        "total_order": sum(o["grand_total"] for o in orders),
        "total_paid": sum(o["total_paid"] for o in orders),
        "remaining": sum(max(o["grand_total"] - o["total_paid"], 0) for o in orders),
        "overpaid": sum(max(o["total_paid"] - o["grand_total"], 0) for o in orders),
        "price_pending_count": sum(1 for o in orders if o.get("price_pending")),
    }


def default_range(date_from: Optional[date], date_to: Optional[date]):
    today = now_utc().astimezone(JKT).date()
    return date_from or today.replace(day=1), date_to or today


@router.get("/reports/reseller")
async def reseller_report(date_from: Optional[date] = None, date_to: Optional[date] = None,
                          reseller_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    date_from, date_to = default_range(date_from, date_to)
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="Tanggal awal tidak boleh melebihi tanggal akhir.")
    flt: dict = {"created_at": jkt_range_to_utc(date_from, date_to)}
    if user["role"] != "admin":
        flt["reseller_id"] = user["reseller_id"]
    elif reseller_id:
        flt["reseller_id"] = to_oid(reseller_id, "Reseller")
    orders = await db.orders.find(flt, PROJ).sort("created_at", 1).to_list(10000)
    rows = [enrich(ser(o)) for o in orders]
    for r in rows:
        r.pop("items", None)
        if user["role"] != "admin":
            r.get("reseller_snapshot", {}).pop("is_special", None)
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "summary": summarize(orders), "rows": rows}


@router.get("/reports/admin")
async def admin_report(date_from: Optional[date] = None, date_to: Optional[date] = None, user: dict = Depends(require_admin)):
    date_from, date_to = default_range(date_from, date_to)
    rng = jkt_range_to_utc(date_from, date_to)
    orders = await db.orders.find({"created_at": rng}, PROJ).to_list(20000)
    resellers = {r["_id"]: r async for r in db.resellers.find()}
    groups: dict = {}
    for o in orders:
        groups.setdefault(o["reseller_id"], []).append(o)
    per_reseller = []
    for rid, os_ in groups.items():
        r = resellers.get(rid)
        per_reseller.append({"reseller_id": str(rid), "name": r["name"] if r else os_[0]["reseller_snapshot"]["name"],
                             "is_special": bool(r and r.get("is_special")), **summarize(os_)})
    per_reseller.sort(key=lambda x: -x["total_order"])
    payments = await db.order_payments.find({"paid_at": rng, "is_void": {"$ne": True}}).sort("paid_at", 1).to_list(20000)
    cash = []
    for p in payments:
        d = ser(p)
        r = resellers.get(p.get("reseller_id"))
        d["reseller_name"] = r["name"] if r else "-"
        cash.append(d)
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "summary": summarize(orders),
            "per_reseller": per_reseller, "cashflow": cash, "cashflow_total": sum(p["amount"] for p in payments)}


def chart(orders: list, days: int = 30) -> list:
    today = now_utc().astimezone(JKT).date()
    buckets = OrderedDict(((today - timedelta(days=i)).isoformat(), {"count": 0, "value": 0}) for i in range(days - 1, -1, -1))
    for o in orders:
        k = o["created_at"].astimezone(JKT).date().isoformat()
        if k in buckets:
            buckets[k]["count"] += 1
            buckets[k]["value"] += o["grand_total"]
    return [{"date": k, **v} for k, v in buckets.items()]


@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    flt = {} if user["role"] == "admin" else {"reseller_id": user["reseller_id"]}
    orders = await db.orders.find(flt, PROJ).sort("created_at", -1).to_list(50000)
    by_status = {s: sum(1 for o in orders if o["status"] == s) for s in ("menunggu_konfirmasi", "diproses", "selesai")}
    data = {**summarize(orders), "by_status": by_status, "recent": [enrich(ser(o)) for o in orders[:8]]}
    for r in data["recent"]:
        if user["role"] != "admin":
            r.get("reseller_snapshot", {}).pop("is_special", None)
        r.pop("items", None)
    if user["role"] == "admin":
        data.update(
            reseller_count=await db.resellers.count_documents({}),
            special_count=await db.resellers.count_documents({"is_special": True}),
            active_products=await db.products.count_documents({"is_active": True}),
            failed_notifications=await db.notification_logs.count_documents({"status": "failed"}),
            chart=chart(orders),
        )
    return data
