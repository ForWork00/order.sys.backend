import os
from pymongo.mongo_client import MongoClient
from dotenv import load_dotenv

# 載入 .env 檔案中的環境變數
load_dotenv()
# 從 .env 檔案中載入 MongoDB URL
mongoDB_url = os.getenv("MONGO_URI")
if not mongoDB_url:
    raise ValueError("MONGO_URI is not set in the environment variables.")
    
    # 指定資料庫名稱
database_name = os.getenv("DATABASE_NAME")
if not database_name:
    raise ValueError("DATABASE_NAME is not set in the environment variables.")
    
    # 建立 MongoDB 連線
client = MongoClient(mongoDB_url)
db = client[database_name]


def get_user_collection():
    return db["Users"]  # 返回特定的集合]

def user_find():
    return db.Users.find()

