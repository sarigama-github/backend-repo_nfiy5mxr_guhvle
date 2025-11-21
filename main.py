import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product as ProductSchema, Order as OrderSchema

app = FastAPI(title="Civil Engineering E‑Commerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductCreate(ProductSchema):
    pass


class OrderCreate(OrderSchema):
    pass


def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    out = {**doc}
    _id = out.get("_id")
    if isinstance(_id, ObjectId):
        out["id"] = str(_id)
        del out["_id"]
    # Convert any nested ObjectId (e.g., in items)
    for k, v in list(out.items()):
        if isinstance(v, ObjectId):
            out[k] = str(v)
    return out


@app.get("/")
def read_root():
    return {"message": "Civil Engineering Store Backend Running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Products
@app.get("/api/products")
def list_products(category: Optional[str] = None, q: Optional[str] = None) -> List[dict]:
    if db is None:
        return []
    filt: dict = {}
    if category:
        filt["category"] = category
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
        ]
    docs = get_documents("product", filt)
    return [serialize_doc(d) for d in docs]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_doc(doc)


@app.post("/api/products", status_code=201)
def create_product(payload: ProductCreate) -> dict:
    product_id = create_document("product", payload)
    doc = db["product"].find_one({"_id": ObjectId(product_id)})
    return serialize_doc(doc)


@app.post("/api/products/seed")
def seed_products() -> dict:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    count = db["product"].count_documents({})
    if count > 0:
        return {"inserted": 0, "message": "Products already exist"}
    samples = [
        {
            "title": "Ready‑Mix Concrete (M25)",
            "description": "Premium grade M25 ready‑mix concrete suitable for foundations and slabs.",
            "price": 109.0,
            "category": "Concrete",
            "image": "https://images.unsplash.com/photo-1591459034474-3c73e6a4c5a3?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
        {
            "title": "TMT Steel Rebars 12mm",
            "description": "High strength corrosion‑resistant TMT bars for structural reinforcement.",
            "price": 2.2,
            "category": "Steel",
            "image": "https://images.unsplash.com/photo-1607040327302-8cfb0f2f03b2?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
        {
            "title": "Crushed Stone Aggregate 20mm",
            "description": "Washed angular aggregate ideal for RCC and road base layers.",
            "price": 35.0,
            "category": "Aggregates",
            "image": "https://images.unsplash.com/photo-1566577739112-5180d4bf939b?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
        {
            "title": "Portland Pozzolana Cement (50kg)",
            "description": "Low‑heat PPC cement with superior durability and workability.",
            "price": 7.5,
            "category": "Cement",
            "image": "https://images.unsplash.com/photo-1621847468514-f5f8d7c94605?q=80&w=1200&auto=format&fit=crop",
            "in_stock": True,
        },
    ]
    result = db["product"].insert_many(samples)
    return {"inserted": len(result.inserted_ids)}


# Orders
@app.post("/api/orders", status_code=201)
def create_order(payload: OrderCreate) -> dict:
    # Recalculate subtotal for safety
    subtotal = 0.0
    for item in payload.items:
        subtotal += item.price * item.quantity
    payload.subtotal = round(subtotal, 2)
    order_id = create_document("order", payload)
    doc = db["order"].find_one({"_id": ObjectId(order_id)})
    return serialize_doc(doc)


# Optional: expose simple schemas for viewer
@app.get("/schema")
def get_schema():
    from schemas import User, Product, Order
    return {
        "user": User.model_json_schema(),
        "product": Product.model_json_schema(),
        "order": Order.model_json_schema(),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
