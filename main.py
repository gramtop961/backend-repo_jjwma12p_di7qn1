import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson.objectid import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Clothing Store API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utility helpers
class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        # accept plain string, ensure it's a valid ObjectId format where needed
        return str(v)


def to_dict(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


# Auth models (very basic demo auth - not production ready)
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "user"  # "user" or "admin"


class LoginRequest(BaseModel):
    email: str
    password: str


# Product models
class ProductIn(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    image_url: Optional[str] = None
    in_stock: bool = True


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    in_stock: Optional[bool] = None


# Order models
class OrderItemIn(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int


class CreateOrderRequest(BaseModel):
    customer_name: str
    customer_email: str
    shipping_address: str
    items: List[OrderItemIn]


class MarkPaidRequest(BaseModel):
    order_id: str


@app.get("/")
async def root():
    return {"message": "Clothing Store API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"⚠️ {str(e)[:80]}"
    return response


# Auth endpoints (very simple; plain-text password for demo)
@app.post("/auth/register")
def register(req: RegisterRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    existing = db["user"].find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = {
        "name": req.name,
        "email": req.email,
        "password": req.password,  # In production, hash this!
        "role": req.role,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = db["user"].insert_one(user_doc)
    return {"id": str(result.inserted_id), "name": req.name, "email": req.email, "role": req.role}


@app.post("/auth/login")
def login(req: LoginRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    user = db["user"].find_one({"email": req.email, "password": req.password})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"id": str(user.get("_id")), "name": user.get("name"), "email": user.get("email"), "role": user.get("role", "user")}


# Products CRUD (admin)
@app.post("/products")
def create_product(p: ProductIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    doc = p.model_dump()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    res = db["product"].insert_one(doc)
    return {"id": str(res.inserted_id), **p.model_dump()}


@app.get("/products")
def list_products():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    products = [to_dict(p) for p in db["product"].find().sort("created_at", -1)]
    return products


@app.get("/products/{product_id}")
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        return to_dict(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")


@app.put("/products/{product_id}")
def update_product(product_id: str, payload: ProductUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        return {"updated": False}
    updates["updated_at"] = datetime.utcnow()
    try:
        res = db["product"].update_one({"_id": ObjectId(product_id)}, {"$set": updates})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        return {"updated": True}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")


@app.delete("/products/{product_id}")
def delete_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        res = db["product"].delete_one({"_id": ObjectId(product_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        return {"deleted": True}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")


# Orders
@app.post("/orders")
def create_order(req: CreateOrderRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # compute subtotal from items
    subtotal = sum(item.price * item.quantity for item in req.items)
    doc = {
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "shipping_address": req.shipping_address,
        "items": [i.model_dump() for i in req.items],
        "subtotal": round(subtotal, 2),
        "status": "pending",
        "payment_method": "qr",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    res = db["order"].insert_one(doc)
    return {"id": str(res.inserted_id), **{k: v for k, v in doc.items() if k != "_id"}}


@app.get("/orders")
def list_orders():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    orders = [to_dict(o) for o in db["order"].find().sort("created_at", -1)]
    return orders


@app.post("/orders/mark-paid")
def mark_paid(payload: MarkPaidRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        res = db["order"].update_one({"_id": ObjectId(payload.order_id)}, {"$set": {"status": "paid", "paid_at": datetime.utcnow(), "updated_at": datetime.utcnow()}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Order not found")
        return {"updated": True}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")


# Simple monthly report (orders summary)
@app.get("/reports/monthly")
def monthly_report(year: Optional[int] = None, month: Optional[int] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from datetime import datetime as dt
    now = dt.utcnow()
    y = year or now.year
    m = month or now.month

    start = dt(y, m, 1)
    if m == 12:
        end = dt(y + 1, 1, 1)
    else:
        end = dt(y, m + 1, 1)

    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "revenue": {"$sum": "$subtotal"}}},
    ]
    agg = list(db["order"].aggregate(pipeline))
    summary = {row["_id"]: {"orders": row["count"], "revenue": round(row["revenue"], 2)} for row in agg}
    total_orders = sum(row["count"] for row in agg) if agg else 0
    total_revenue = round(sum(row["revenue"] for row in agg), 2) if agg else 0.0

    return {"year": y, "month": m, "summary": summary, "total_orders": total_orders, "total_revenue": total_revenue}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
