import os
from pymongo.mongo_client import MongoClient
from pymongo import ReturnDocument
from flask import jsonify
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

""" 修改db當中Expenses的id """
expense_collection=db["Expenses"]
def create_date_id(date_prefix:str)->str:
    count=db.counts.find_one_and_update(
        {"_id":"expense_id"},
        {"$inc":{"sequence_value":1}},   # 自增 1
        return_document=ReturnDocument.AFTER,   # 返回更新後的文件
        upsert=True
        )
    sequence=count["sequence_value"]
    return f"{date_prefix}{sequence:04d}"


""" 刪除db集合中資料(工程用) 使用前請再確認！！！ """
def del_all_coll():
    try:
        result=expense_collection.delete_many({})   # 需要用到(請更改要清除集合)
        return result.deleted_count   # 回傳刪除的筆數
    except Exception as e:
        raise Exception(f"Failed to delete:{str(e)}")


""" accounting use """
# def insert_revenue(data):   #收入
#     db.Revenues.insert_one(data)

def insert_expense(data):   #支出
    db.Expenses.insert_one(data)


def get_revenues(start_date, end_date):   # 查詢收入（抓訂餐資訊）
    return list(db.Orders.find({"updated_at":{"$gte":start_date, "$lte":end_date}}, {"_id":0, "total_price":1, "updated_at":1}))

def get_expenses(start_date, end_date):   # 查詢支出
    return list(db.Expenses.find({"created_time":{"$gte":start_date, "$lte":end_date}}, {"_id":0, "amount":1, "created_time":1}))