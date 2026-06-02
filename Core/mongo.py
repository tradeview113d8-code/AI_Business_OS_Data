from pymongo import MongoClient
from Core.config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db     = client[DB_NAME]

def ping():
    try:
        client.admin.command("ping")
        return True
    except:
        return False
