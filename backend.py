from datetime import datetime
import json
from bson import ObjectId # type: ignore
from flask import Flask, Response, request, jsonify, send_file # type: ignore
import os, re, time, subprocess, logging
import requests # type: ignore
from datetime import datetime, timezone, timedelta
from flask_bcrypt import Bcrypt # type: ignore
from config import jwt_config
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt # type: ignore
from mongoDB import get_user_collection, user_find, create_date_id, get_revenues, get_expenses, insert_expense, del_all_coll, blacklisted_tokens_collection, backstage_user, get_user_collection # 從 mongoDB.py 導入
from func import create_uuid, generate_trend_chart, export_to_excel, total, format_user_data
from dotenv import load_dotenv # type: ignore
from accounting.balance_sheet import balance_sheet,balance_sheet_save
from accounting.cash_flow_statement import Cash_Flow_Statement, save_cash_flow_statement
from accounting.income_statement import get_income_statement, save_income_statement_to_excel
from accounting.account_function import get_history, add_entry, set_opening_balance
from menu.menu_sys import get_menu_sys, get_menu_item_sys, create_menu_item_sys, delete_menu_item_sys, update_menu_item_sys
from order.order_sys import get_orders_sys, get_order_sys, update_order_sys, create_order_sys, delete_order_sys
from coupons.coupons_sys import create_coupon_sys, get_user_coupons_sys, delete_coupon_sys, get_all_coupons_sys, update_coupon_sys, get_coupon_sys, bind_coupon_sys, create_admin_coupon_sys
from payment_api import payment_bp
from line_api import line_bp
from flask_cors import CORS # type: ignore
from waiting.waiting_system import take_queue, cancel_queue, call_specific_queue, auto_call_queue, get_queue_info
from reservation.reservation_sys import set_reservation_slots_sys, add_reservation_sys, get_reservations_sys, cancel_reservation_sys, get_all_reservations_sys, get_today_reservations_sys, delete_reservation_sys, get_reservations_by_date_sys

# 載入 .env 檔案
load_dotenv()

# 使用環境變數
mongo_uri = os.getenv('MONGO_URI')
database_name = os.getenv('DATABASE_NAME')
token = os.getenv('TOKEN')
flask_secret_key = os.getenv('FLASK_SECRET_KEY')

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
collection=get_user_collection()
bcrypt=Bcrypt(app)
app.config.from_object(jwt_config)
jwt = JWTManager(app)
blacklist = set()
blacklisted_tokens = set()

# 從環境變數中設置 secret_key，secret_key 用於 session 加密
app.secret_key = flask_secret_key
if not app.secret_key:
    raise ValueError("FLASK_SECRET_KEY 未設置")


# 註冊藍圖
app.register_blueprint(payment_bp, url_prefix='/payment')
app.register_blueprint(line_bp, url_prefix='/line')

def is_valid_email(email):
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"  #check email 格式是否正確
    return re.match(email_regex, email) is not None

def is_valid_birth(birth):
    if not re.match(r"^\d{8}$", birth):  #check birth格式、正確日期
        return False
    
    try:
        birth_date=datetime.strptime(birth, "%Y%m%d")
        if birth_date > datetime.now():
            return False
    except ValueError:
        return False
    return True
@app.route('/')
def home():
    return "Hello, World"

@app.route("/sign_up", methods=["POST"])
def sign_up():
    email=request.json.get("email")   #目前考慮email or LINE 連動登入
    password=request.json.get("password")
    birth=request.json.get("birth")

    if not email or not password or not birth:
        return jsonify({"error": "Missing fields"}), 400
    
    # 檢查信箱是否已經被註冊
    if collection.find_one({"email": email}):
        return jsonify({"error": "Email is already registered"}), 400
    
    if not is_valid_email(email):
        return jsonify({"error":"email format error"}), 400
    
    if not is_valid_birth(birth):
        return jsonify({"error":"birth format error is YYYYMMDD and not exceed today"}), 400
    
    #加密密碼
    hashed_password=bcrypt.generate_password_hash(password).decode("utf-8")
    
    uid=create_uuid()
    register_time=datetime.now()   # 註冊時間
    default_points=0   # 預設點數為0
    try:
        collection.insert_one({
            "_id":uid,
            "email":email,
            "password":hashed_password,
            "birth":birth,
            "register_time":register_time,
            "points":default_points
        })
        return jsonify({"_id":uid, "email":email, "message":"User created successfully"}), 201
    except Exception as e:
        return jsonify({"error":"Created Fail"})

@app.route("/login", methods=["POST"])
def login():
    data=request.get_json()
    email = data.get('email')
    password = data.get('password')

    # 檢查用戶是否存在
    user = next((u for u in user_find() if u['email'] == email), None)
    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({"error": "Email does not exist or password is incorrect"}), 401
    user_id=str(user["_id"])   # 確保 user_id 是 UUID 字串
    # 生成 JWT 並將 user_id 放入
    token = create_access_token(identity=user_id)
    return jsonify({"message": "Login successful", "token": token}), 200
    


@jwt.token_in_blocklist_loader
def check_token_revoked(jwt_header, jwt_payload):
    return blacklisted_tokens_collection.find_one({"jti":jwt_payload["jti"]}) is not None
@app.route("/logOut", methods=["POST"])
@jwt_required()
def logOut():
    jti=get_jwt()["jti"]
    blacklisted_tokens_collection.insert_one({"jti":jti})
    return jsonify({"message":"Logout successful"}),200



""" 取得會員個人資訊 """
@app.route("/get_userself", methods=["GET"])
@jwt_required()
def get_user():
    try:
        user_id=get_jwt_identity()   # 取得當前使用者的 user_id（JWT 身份識別）

        user=collection.find_one({"_id":str(user_id)})
        if not user:
            return jsonify({"error":"User does not exist"}), 404
        return jsonify(format_user_data(user)), 200
    except Exception as e:
        return jsonify({"error":f"An error occurred: {str(e)}"}), 500
        

""" 點數加扣 """
@app.route("/update_points", methods=["POST"])
def update_points():
    try:
        data = request.json
        user_id = data.get("user_id")
        points = data.get("points")  # 加/扣的點數 (正數為加點，負數為扣點)

        user=collection.find_one({"_id":user_id})
        if not user:
            return jsonify({"error":"User does not exist"}), 404

        current_points = user.get("points", 0)   # 確保點數欄位存在

        new_points = current_points + points   # 計算新的點數
        if new_points < 0:
            return jsonify({"error": "Not enough points"}), 400

        collection.update_one(   # 更新用戶點數
            {"_id": user["_id"]},  # uuid 作為查詢條件
            {"$set": {"points": new_points}}
        )

        return jsonify({
            "message": "點數更新成功",
            "new_points": new_points
        }), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred : {str(e)}"}), 500




@app.route("/api/expenses/add", methods=["POST"])   # 新增支出api
def add_expenses():
    data=request.json
    date_prefix=datetime.now().strftime("%Y%m%d")
    data["_id"]=create_date_id(date_prefix)
    data["created_time"]=datetime.now()
    insert_expense(data)
    return jsonify({"message":"Add Successfully"}), 201
    


def serialize_document(doc):
    """將 MongoDB 文件中的 ObjectId 轉換為字符串"""
    return {key: str(value) if key == "_id" else value for key, value in doc.items()}

@app.route("/api/search/report", methods=["GET"])   # 搜尋收入支出報表&生成圖形報表
def get_report():
    start_date=request.args.get("start_date")
    end_date=request.args.get("end_date")
    chart=request.args.get("chart", "fales").lower()=="true"
    chart_type=request.args.get("chart_type", "line").lower()

    try:
        start=datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        end=datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({"error":"Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'"})

    revenues=[serialize_document(doc) for doc in get_revenues(start, end)]
    expenses=[serialize_document(doc) for doc in get_expenses(start, end)]

    total_revenue=total(revenues, "total_price")
    total_expense=total(expenses, "amount")
    
    if chart:
        try:
                # 生成折線圖
            img = generate_trend_chart(revenues, expenses, chart_type)
            return send_file(img, mimetype="image/png")
        except Exception as e:
            return jsonify({"error": f"Failed to generate chart: {str(e)}"}), 500
    
    revenue_data=[{"total_price": r["total_price"], "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M:%S")} for r in revenues]
    expense_data=[{"amount": e["amount"], "created_time": e["created_time"].strftime("%Y-%m-%d %H:%M:%S")} for e in expenses]
    
    return jsonify({
        "revenues": revenue_data,
        "expenses": expense_data,
        "total_revenue":total_revenue,
        "total_expense":total_expense
        })
    


@app.route("/api/report/export", methods=["GET"])  # 匯出excel
def export_report():
    try:
        start_date=request.args.get("start_date")
        end_date=request.args.get("end_date")
        start=datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        end=datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")

        revenues=get_revenues(start, end)
        expenses=get_expenses(start, end)
        output=export_to_excel(revenues, expenses)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        as_attachment=True, download_name="report_xlsx")
    except Exception as e:
        logging.error(f"Error in exporting report :{e}")
        return jsonify({"error":str(e)}), 500


""" 工程用（使用前請再仔細確認） """
@app.route("/db/del_all_coll", methods=["DELETE"])   # 使用前請看mongoDB.py中的函式進行調整刪除內容
def delete_all_coll():
    try:
        delete_count=del_all_coll()
        return jsonify({
            "message":"Deleted successfully",
            "delete_count":delete_count
        }), 200
    except Exception as e:
        return jsonify({
            "message":"An error occurred while deleting",
            "error":str(e)
        }), 500

# 菜單系統api
# ------------------------------------------------------
@app.route('/menu', methods=["GET"])
def get_menu():
    """取得菜單列表"""
    return get_menu_sys()

@app.route('/menu/<item_id>', methods=["POST"])
def get_menu_item(item_id):
    """取得單一菜單品項資訊"""
    return get_menu_item_sys(item_id)

@app.route('/menu', methods=["POST"])
def create_menu_item():
    """新增菜單品項"""
    return create_menu_item_sys()
    
@app.route('/menu/<item_id>', methods=["PUT"])
def update_menu_item(item_id):
    """修改單一菜單品項資訊"""
    return update_menu_item_sys(item_id)

@app.route('/menu/<item_id>', methods=["DELETE"])
def delete_menu_item(item_id):
    """刪除單一菜單品項資訊"""
    return delete_menu_item_sys(item_id)

# 訂單系統api
# -----------------------------------------------------
@app.route('/orders', methods=["GET"])
def get_orders():
    """取得訂單列表"""
    return get_orders_sys()

@app.route('/orders/<order_id>', methods=["POST"])
def get_order(order_id):
    """查詢單一訂單資訊"""
    return get_order_sys(order_id)

@app.route('/orders/<order_id>', methods=["PUT"])
def update_order(order_id):
    """修改訂單資訊"""
    return update_order_sys(order_id)

@app.route('/orders', methods=["POST"])
def create_order():
    """用戶新增訂單"""
    return create_order_sys()

@app.route('/orders/<order_id>', methods=["DELETE"])
def delete_order(order_id):
    """用戶刪除單一訂單"""
    return delete_order_sys(order_id)

# 優惠券系統api
# -----------------------------------------------------
@app.route('/coupons', methods=["POST"])
def create_coupon():
    """會員使用點數兌換優惠券（新增優惠券）"""
    return create_coupon_sys()

@app.route('/coupons', methods=["GET"])
def get_all_coupons():
    """獲取所有優惠券（管理員用）"""
    return get_all_coupons_sys()

@app.route('/coupons/<coupon_id>', methods=["GET"])
def get_coupon(coupon_id):
    """獲取單一優惠券資訊"""
    return get_coupon_sys(coupon_id)

@app.route('/coupons/<user_id>', methods=["GET"])
def get_user_coupons(user_id):
    """獲取特定會員的所有優惠券"""
    return get_user_coupons_sys(user_id)

@app.route('/coupons/<coupon_id>', methods=["PUT"])
def update_coupon(coupon_id):
    """更新優惠券資訊（例如修改有效期限）"""
    return update_coupon_sys(coupon_id)

@app.route('/coupons/<coupon_id>', methods=["DELETE"])
def delete_coupon(coupon_id):
    """刪除單一優惠券"""
    return delete_coupon_sys(coupon_id)

#管理員新增優惠券
@app.route('/coupons/admin', methods=["POST"])
def create_admin_coupon():
    return create_admin_coupon_sys()

#會員輸入優惠券代碼進行綁定
@app.route('/coupons/bind', methods=["POST"])
def bind_coupon():
    return bind_coupon_sys()

# 會計報表api
# -----------------------------------------------------
#現金流量表
@app.route('/accounting/cash_flow_statement', methods=["GET"])
def fetch_cash_flow_statement():
    print("MONGO_URI:", os.getenv("MONGO_URI"))
    print("DATABASE_NAME:", os.getenv("DATABASE_NAME"))
    return Cash_Flow_Statement()

 #現金流量表導出excel   
@app.route('/accounting/cash_flow_statement/save', methods=["POST"])
def download_cash_flow_statement():
    return save_cash_flow_statement()

#損益表
@app.route('/accounting/income_statement', methods=["GET"])
def fetch_income_statement():
    return get_income_statement()

#損益表導出excel
@app.route('/accounting/income_statement/save', methods=["POST"])
def download_income_statement():
    try:
        response = get_income_statement()  # 獲取損益表資料
        
        if isinstance(response, dict) and "error" in response:
            return jsonify(response), 500  # 如果出錯則回傳錯誤信息
        
        # 保存損益表至 Excel，並獲得 BytesIO 物件
        excel_file = save_income_statement_to_excel(response)
        
        # 使用 send_file 將 Excel 檔案返回給客戶端
        return send_file(
            excel_file,
            as_attachment=True,
            download_name="損益表.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  
        )   
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#資產負債表
@app.route("/accounting/balance_sheet", methods=["GET"])
def get_balance_sheet():
    return balance_sheet()

#資產負債表導出excel
@app.route("/accounting/balance_sheet/save", methods=["POST"])
def save_balance_sheet():
    return balance_sheet_save()

#記帳歷史紀錄
@app.route("/get_history", methods=["POST"])
def fetch_get_add_history():
    return get_history()

#會計記帳
@app.route("/add_entry", methods=["POST"])
def fetch_add_accounting_entry():
    return add_entry()

#設定期初餘額
@app.route("/set_opening_balance", methods=["POST"])
def fetch_set_opening_balance():
    return set_opening_balance()



#========================後台環境==============================#

@app.route("/backstage/registers", methods=["POST"])
def register():
    data=request.json
    hashed_password=bcrypt.generate_password_hash(data["password"]).decode("utf-8")

    if backstage_user.find_one({"username":data["username"]}):
        return jsonify({"message":"Username already exists"}), 400
    
    new_user={
        "username":data["username"],
        "password":hashed_password,
        "role":data.get("role", "user"),
        "permissions":data.get("permissions", {})
    }
    backstage_user.insert_one(new_user)
    return jsonify({"message":"User registered successfully!"}), 201


@app.route("/backstage/login", methods=["POST"])
def backstage_login():
    data=request.json
    user=backstage_user.find_one({"username": data["username"]})
    if user and bcrypt.check_password_hash( user["password"], data["password"]):
        access_token=create_access_token(
            identity=str(user["_id"]),
            additional_claims={"role":user["role"]}
        )
        return jsonify(access_token=access_token), 200
    return jsonify({"message":"Invalid credentials"}), 401



@app.route("/users", methods=["GET"])   #取得用者（管理最大權限使用）
@jwt_required()
def get_backstage_user():
    current_user=get_jwt_identity()
    jwt_data=get_jwt()
    role=jwt_data.get("role", "")

    user=backstage_user.find_one({"_id":ObjectId(current_user)})

    if not user:
        return jsonify({"message": "User not found"}), 404
    if role != "admin":
        return jsonify({"message":"Permission denied"}), 403
    
    users=backstage_user.find()
    result=[
        {"id":str(u["_id"]), "username":u["username"], "role":u["role"], "permissions":u["permissions"]}
        for u in users
    ]
    return jsonify(result), 200


@app.route("/update-permissions/<user_id>", methods=["PUT"])
@jwt_required()
def update_permissions(user_id):
    current_user=(get_jwt_identity())
    user=backstage_user.find_one({"_id":ObjectId(current_user)})

    if user["role"] != "admin":
        return jsonify({"message":"Permission denied"}), 403
    
    data=request.json
    target_user=backstage_user.find_one({"_id":ObjectId(user_id)})
    if not target_user:
        return jsonify({"message":"User not found"}), 404
    
    backstage_user.update_one(
        {"_id":ObjectId(user_id)},
        {"$set":{"permissions":data["permissions"]}}
    )
    return jsonify({"message":"Permissions updated successfully"}), 200


@app.route("/get_user")   # 搜尋會員
def get_users():
    try:
        user_id=request.args.get("user_id")
        email=request.args.get("email")

        query={}

        if user_id:
            query["_id"]=user_id
        if email:
            query["email"]=email
        
        if query:
            user=collection.find_one(query)
            if not user:
                return jsonify({"error":"User does not exist"}), 404
            return jsonify(format_user_data(user)), 200
        else:
            users=collection.find()
            user_list=[format_user_data(user) for user in users]
            return jsonify(user_list), 200
    except Exception as e:
        return jsonify({"error":f"An error occurred: {str(e)}"}), 500
        


@jwt.token_in_blocklist_loader
def check_token_revoked(jwt_header, jwt_payload):
    return blacklisted_tokens_collection.find_one({"jti":jwt_payload["jti"]}) is not None   # 查詢是否在黑名單

@app.route("/backstage/logout", methods=["POST"])
@jwt_required()
def logout():
    jti=get_jwt()["jti"]
    blacklisted_tokens_collection.insert_one({"jti":jti})
    return jsonify({"message":"Logged out successfully"}), 200

# 候位系統api
# -----------------------------------------------------
#抽取候位號碼
@app.route("/queue/take", methods=["POST"])
def queue_take():
    return take_queue()
#取消候位號碼
@app.route("/queue/cancel/<int:queue_number>", methods=["DELETE"])
def queue_cancel(queue_number):
    return cancel_queue(queue_number)
#指定叫號
@app.route("/queue/call/<int:queue_number>", methods=["POST"])
def queue_call(queue_number):
    return call_specific_queue(queue_number)
#自動叫下一個候位號碼
@app.route("/queue/auto-call", methods=["POST"])
def queue_auto_call():
    return auto_call_queue()
#取得候位資訊
@app.route("/queue/info", methods=["GET"])
def queue_info():
    return get_queue_info()

# 定位系統api
# -----------------------------------------------------
@app.route("/set_reservation_slots", methods=["POST"])
def reservation_slots():
    """店家設定時段、桌數與每桌人數"""
    return set_reservation_slots_sys()
 
@app.route("/reservations", methods=["POST"])
def add_reservation():
    """新增預約"""
    return add_reservation_sys()
   
@app.route("/reservations", methods=["GET"])
def get_reservations():
    """電話查詢預約可模糊查詢"""
    return get_reservations_sys()

@app.route("/reservations", methods=["PUT"])
def cancel_reservation():
    """會員取消預約"""
    return cancel_reservation_sys()

@app.route("/reservations/all", methods=["GET"])
def get_all_reservations():
    """查詢所有預約"""
    return get_all_reservations_sys()

@app.route("/reservations/date", methods=["GET"])
def get_reservations_by_date():
    """根據指定日期查詢預約"""
    return get_reservations_by_date_sys()

@app.route("/reservations/today", methods=["GET"])
def get_today_reservations():
    """查詢當天所有預約"""
    return get_today_reservations_sys()

@app.route("/reservations/<reservation_id>", methods=["DELETE"])
def delete_reservation(reservation_id):
    """刪除單筆預約"""
    return delete_reservation_sys(reservation_id)

if __name__ == "__main__":
    app.run(debug=True, threaded=False)
