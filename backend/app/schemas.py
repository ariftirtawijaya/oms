from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    voltage: Literal["12", "24", "-"] = "12"
    price: int = Field(ge=1)
    is_active: bool = True
    notes: str = ""

    @field_validator("voltage", mode="before")
    @classmethod
    def norm_voltage(cls, v):
        s = str(v or "-").strip().upper().removesuffix("V").strip()
        return s or "-"

    @field_validator("name")
    @classmethod
    def strip(cls, v):
        return " ".join(v.split())


class ResellerIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    wa: str = Field(min_length=8, max_length=25)
    address: str = ""
    is_special: bool = False
    notes: str = ""
    login_email: Optional[EmailStr] = None
    login_password: Optional[str] = Field(default=None, min_length=8, max_length=200)


class UserIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=150)
    role: Literal["admin", "reseller"]
    reseller_id: Optional[str] = None
    password: str = Field(min_length=8, max_length=200)
    must_change_password: bool = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    reseller_id: Optional[str] = None


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)
    must_change_password: bool = True


class OrderItemIn(BaseModel):
    product_id: Optional[str] = None
    custom_name: Optional[str] = Field(default=None, max_length=200)
    qty: int = Field(ge=1, le=100000)
    expected_price: Optional[int] = None


class OrderCreateIn(BaseModel):
    reseller_id: Optional[str] = None
    items: List[OrderItemIn] = Field(min_length=1)
    notes: str = Field(default="", max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=100)


class StatusIn(BaseModel):
    status: Literal["menunggu_konfirmasi", "diproses", "selesai"]


class ProgressItem(BaseModel):
    item_id: str
    qty_done: int = Field(ge=0)


class ProgressIn(BaseModel):
    items: List[ProgressItem]


class PaymentIn(BaseModel):
    amount: int = Field(gt=0)
    paid_at: Optional[datetime] = None
    notes: str = Field(default="", max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=100)


class PaymentVoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class PriceAdjustIn(BaseModel):
    item_id: str
    new_price: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=500)


class ResolveCustomIn(BaseModel):
    item_id: str
    product_id: Optional[str] = None
    unit_price: int = Field(ge=0)
    reason: str = Field(default="Penetapan harga produk custom", max_length=500)


class NotesIn(BaseModel):
    internal_notes: str = Field(default="", max_length=3000)


class ProfileIn(BaseModel):
    address: str = Field(default="", max_length=1000)
