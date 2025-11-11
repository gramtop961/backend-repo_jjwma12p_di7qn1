"""
Database Schemas for Clothing Store

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase class name.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Plain text password (will be hashed)")
    role: str = Field("user", description="user or admin")
    is_active: bool = Field(True)


class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: Optional[str] = Field(None, description="Product category")
    image_url: Optional[str] = Field(None, description="Image URL")
    in_stock: bool = Field(True)


class OrderItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int


class Order(BaseModel):
    user_id: Optional[str] = None
    customer_name: str
    customer_email: str
    shipping_address: str
    items: List[OrderItem]
    subtotal: float
    status: str = Field("pending", description="pending|paid|cancelled")
    payment_method: str = Field("qr", description="qr for QR code payments")
    paid_at: Optional[datetime] = None


# These schemas are used for validation/documentation by the database viewer and backend.
