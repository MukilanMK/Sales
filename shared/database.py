import os

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(
    os.getenv("MONGO_URI")
)

db = client["supply_chain"]

sales_collection = db["sales_history"]
