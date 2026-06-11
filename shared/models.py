from pydantic import BaseModel
from typing import List


class ProductRecommendation(BaseModel):
    product_id: str
    name: str
    quantity: int
    category: str

class InventoryAgentOutput(BaseModel):
    replenishments: List[ProductRecommendation]
