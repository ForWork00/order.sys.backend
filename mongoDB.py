import os
from pymongo.mongo_client import MongoClient
from pymongo import ReturnDocument
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

# 使用者資訊
# ----------------------------------------------------
def get_user_collection():
    """取得 Users 集合"""
    return db["Users"]

def user_find():
    """查詢所有使用者資訊"""
    return list(get_user_collection().find())

# 訂單系統
# -----------------------------------------------------
def get_order_collection():
    """取得 Orders 集合"""
    return db["Orders"]


# 菜單系統
# ------------------------------------------------------
def get_menu_collection():
    """取得 Menu 集合"""
    return db["Menu"]

# 優惠券系統
# ------------------------------------------------------
def get_coupons_collection():
    """取得 Coupons 集合"""
    return db["Coupons"]

# 定位系統
def get_reservations_collection():
    """取得 Reservations 集合"""
    return db["Reservations"]

def reservation_settings_collection():
    """取得 Reservations_settings 集合"""
    return db["reservation_settings"]

""" 修改db當中Expenses的id """
expense_collection=db["Expenses"]
def create_date_id(date_prefix:str)->str:
    count=db.Counts.find_one_and_update(
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
def insert_expense(data):   #支出
    db.Expenses.insert_one(data)


def get_revenues(start_date, end_date):   # 查詢收入（抓訂餐資訊）
    return list(db.Orders.find({"updated_at":{"$gte":start_date, "$lte":end_date}}, {"_id":0, "total_price":1, "updated_at":1}))

def get_expenses(start_date, end_date):   # 查詢支出
    return list(db.Expenses.find({"created_time":{"$gte":start_date, "$lte":end_date}}, {"_id":0, "amount":1, "created_time":1}))



""" backstage user """
backstage_user = db["BSusers"]

blacklisted_tokens_collection = db["blacklisted_tokens"]   #存放後台登出token的紀錄

#會計系統
# ------------------------------------------------------
def get_accounting():   # 取得所有會計項目
    return db["Accounting"]

def get_AccountHistory():   #取得會計寫入紀錄
    return db["AccountHistory"]


# LINE使用者資料
# ------------------------------------------------------
def get_line_user_collection():
    return db["LineUsers"]

def find_line_user(user_id):
    return get_line_user_collection().find_one({"user_id": user_id})

def create_line_user(user_id, profile_data):
    get_line_user_collection().insert_one({"user_id": user_id, "profile": profile_data})

