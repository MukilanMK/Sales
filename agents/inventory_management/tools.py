import requests
from shared.database import sales_collection

def fetch_inventory_from_api():
    """Fetch today's inventory sales data from API."""
    response = requests.get("http://127.0.0.1:5000/inventory")
    response.raise_for_status()
    raw = response.json()

    # Return compact summary to reduce LLM token usage
    compact = [
        {
            "id": p["product_id"],
            "name": p["product_name"],
            "category": p["category"],
            "sales": p["today_sales"],
            "stock": p["remaining_stock"],
        }
        for p in raw
    ]
    return raw, compact

def store_inventory(inventory_data):
    """Store inventory snapshots in MongoDB."""
    if isinstance(inventory_data, dict):
        inventory_data = [inventory_data]

    docs = []
    for item in inventory_data:
        doc = {k: v for k, v in item.items() if k != "_id"}
        docs.append(doc)

    if docs:
        sales_collection.insert_many(docs)
    
    return f"Stored {len(docs)} inventory records successfully."

def get_historical_sales():
    """Retrieve historical sales data."""
    raw = list(
        sales_collection.find(
            {},
            {"_id": 0}
        ).sort("_id", -1).limit(5)
    )

    compact = []
    for p in raw:
        compact.append({
            "id": p.get("product_id", p.get("id", "")),
            "name": p.get("product_name", p.get("name", "")),
            "sales": p.get("today_sales", p.get("sales", 0)),
            "stock": p.get("remaining_stock", p.get("stock", 0)),
            "date": p.get("date", ""),
        })

    return compact
