import os, stripe, re, time, subprocess
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from mongoDB import get_user_collection, user_find, get_order_collection, get_menu_collection  # 從 mongoDB.py 導入
from func import create_uuid, stripe_pay, generate_order_id, upload_image_to_imgur



app = Flask(__name__)
collection=get_user_collection()
order_collection = get_order_collection()
menu_collection = get_menu_collection()
bcrypt=Bcrypt(app)
app.config["JWT_SECRET_KEY"] = "my_screct_key"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 86400   #24hr
app.config["JWT_BLACKLIST_ENABLED"] = True
app.config["JWT_BLACKLIST_TOKEN_CHECKS"] = ["access"]
jwt = JWTManager(app)
blacklist = set()

# 初始化限流 IP限制請求頻率
limiter=Limiter(
    get_remote_address,
    app=app,
    default_limits=["1 per minute"]
)
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
#@limiter.limit("1 per minute")
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
    try:
        collection.insert_one({
            "_id":uid,
            "email":email,
            "password":hashed_password,
            "birth":birth
        })
        return jsonify({"_id":uid, "email":email, "message":"User created successfully"}), 201
    except Exception as e:
        return jsonify({"messag":"Created Fail"})

@app.route("/login", methods=["POST"])
def login():
    data=request.get_json()
    email = data.get('email')
    password = data.get('password')

    # 檢查用戶是否存在
    user = next((u for u in user_find() if u['email'] == email), None)
    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({"message": "電子郵件不存在或密碼錯誤"}), 401
        
    # 生成 JWT
    token = create_access_token(identity=user["email"])
    return jsonify({"message": "登入成功", "token": token}), 200
    


@app.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({"message": "測試確定帶入TOKEN登入", "user": current_user}), 200
    
@app.route("/logOut", methods=["POST"])
@jwt_required()
def logOut():
    jti=get_jwt()["jti"]
    blacklist.add(jti)
    return jsonify({"message":"Logout successful"}),200

@app.route("/create_stripe_pay", methods=["POST"])
def create_stripe_pay():
    return stripe_pay()

# 菜單系統api
# ------------------------------------------------------
@app.route('/menu', methods=["GET"])
def get_menu():
    """取得菜單列表"""
    menu = list(menu_collection.find({"is_available": True}))# 過濾掉is_available=False
    if not menu:
        return jsonify({"error": "Menu not found"}), 404

    
    return jsonify(menu), 200

@app.route('/menu/<item_id>', methods=["POST"])
def get_menu_item(item_id):
    """取得單一菜單品項資訊"""
    try:
        # 將 item_id 轉換為 float
        item_id = float(item_id)
    except ValueError:
        return jsonify({"error": "Invalid item_id format"}), 400
    
    # 查詢資料庫
    menu_item = menu_collection.find_one({"_id": item_id})
    if not menu_item:
        return jsonify({"error": "Menu item not found"}), 404
    return jsonify(menu_item), 200

@app.route('/menu', methods=["POST"])
def create_menu_item():
    """新增菜單品項"""
    data = request.form
    id = data.get("_id")
    name = data.get("name")
    description = data.get("description", "")
    price = data.get("price")
    category = data.get("category")
    image = request.files.get("image")
    now = datetime.now()

    if not name or not price or not category:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # 如果有提供image
        image_url = ""
        if image:
            image_url = upload_image_to_imgur(image.read())

        #構建菜單
        menu_item = {
            "_id": float(id),
            "name": str(name),
            "description": str(description),
            "price": float(price),  # 確保為數字
            "category": str(category),
            "image_url": str(image_url),
            "is_available": True, #默認
            "created_at": now,
            "updated_at": now
        }
        menu_collection.insert_one(menu_item)
        return jsonify({"message": "Menu item created successfully", "item": menu_item}), 201
    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500
    
@app.route('/menu/<item_id>', methods=["PATCH"])
def update_menu_item(item_id):
    """修改單一菜單品項資訊"""
    try:
        # 將 item_id 轉換為 float（與資料庫的 _id 格式一致）
        item_id = float(item_id)
    except ValueError:
        return jsonify({"error": "Invalid item_id format"}), 400

    # 查詢資料庫中的菜單項目
    menu_item = menu_collection.find_one({"_id": item_id})
    if not menu_item:
        return jsonify({"error": "Menu item not found"}), 404

    # 接收用戶提交的更新數據
    update_data = request.json
    if not update_data:
        return jsonify({"error": "No update data provided"}), 400

    # 定義允許更新的字段
    allowed_fields = {"name", "description", "price", "category", "image_url", "is_available"}

    # 過濾更新數據，僅允許更新指定字段
    filtered_update_data = {key: update_data[key] for key in update_data if key in allowed_fields}

    if not filtered_update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    # 添加 updated_at 時間戳
    filtered_update_data["updated_at"] = datetime.now()
    
    # 更新資料庫
    result = menu_collection.update_one(
        {"_id": item_id},
        {"$set": filtered_update_data}
    )

    if result.modified_count == 0:
        return jsonify({"error": "No changes made"}), 400

    # 返回更新後的菜單項目
    updated_menu_item = menu_collection.find_one({"_id": item_id})
    return jsonify(updated_menu_item), 200


# 訂單系統api
# -----------------------------------------------------
@app.route('/orders', methods=["GET"])
def get_orders():
    """取得訂單列表"""
    orders = list(order_collection.find())
    return jsonify(orders), 200

@app.route('/orders/<order_id>', methods=["POST"])
def get_order(order_id):
    """取得單一訂單資訊"""
    try:
        # 將 order_id 轉換為 str
        order_id = str(order_id)
    except ValueError:
        return jsonify({"error": "Invalid order_id format"}), 400

    order = order_collection.find_one({"_id": order_id})
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order), 200

@app.route('/orders/<order_id>', methods=["PATCH"])
def update_order(order_id):
    """修改訂單資訊"""
    data = request.json
    allowed_statuses = ["pending", "completed", "canceled"]  # 允許的狀態
    update_fields = {}

    if "status" in data:
        #檢查是否有符合allowed_statuses列表裡這幾種，若符合則更新status狀態
        new_status = data["status"]
        if new_status not in allowed_statuses:
            return jsonify({"error": f"Invalid status. Allowed values are {allowed_statuses}"}), 400
        update_fields["status"] = new_status

    update_fields["updated_at"] = datetime.now()

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    result = order_collection.update_one({"_id": order_id}, {"$set": update_fields})
    if result.matched_count == 0:
        return jsonify({"error": "Order not found"}), 404
    return jsonify({"message": "Order updated successfully"}), 200

@app.route('/orders', methods=["POST"])
def create_order():
    """用戶新增訂單（登入或不登入）"""
    data = request.json
    user_id = data.get("user_id")
    items = data.get("items")  # 預期格式: [{"menu_item_id": "123", "quantity": 2}, ...]

    # 檢查 items 格式
    if not items or not isinstance(items, list):
        return jsonify({"error": "items is required and must be a list"}), 400

    # 確認 user_id 是否對應到資料庫
    user_data = None
    if user_id:
        user_data = collection.find_one({"_id": user_id})
        if not user_data:
            return jsonify({"error": "Invalid user_id"}), 400

    # 構建菜單項目 ID 和數量
    try:
        menu_item_ids = [float(item["menu_item_id"]) for item in items]
    except ValueError:
        return jsonify({"error": "Invalid menu_item_id format"}), 400

    quantities = {item["menu_item_id"]: item.get("quantity", 1) for item in items}

    # 查詢菜單項目
    menu_items = list(menu_collection.find({"_id": {"$in": menu_item_ids}}))
    found_ids = {item["_id"] for item in menu_items}
    invalid_ids = [menu_id for menu_id in menu_item_ids if menu_id not in found_ids]

    if invalid_ids:
        return jsonify({"error": "Some menu items are invalid", "invalid_ids": invalid_ids}), 400

    # 計算總價並構建訂單項目
    order_items = []
    total_price = 0
    order_type = 1  # 預設訂單類型為 1（不使用優惠）

    for item in menu_items:
        quantity = quantities.get(item["_id"], 1)  # 默認數量為 1
        price = float(item["price"])  # 確保價格為數字類型
        total = price * quantity

        order_items.append({
            "id": item["_id"],
            "name": item["name"],
            "price": price,
            "quantity": quantity,
            "total": total,
        })
        total_price += total

    # 如果 user_id 存在且對應到用戶，檢查是否使用優惠
    if user_data:
        order_type = data.get("type", 1)  # 使用前端傳入的 type 值，若無則默認為 1

    # 構建訂單資料
    order_id = generate_order_id()
    now = datetime.now()
    order = {
        "_id": order_id,
        "user_id": user_id,  # 登入用戶的 user_id，未登入為 None
        "menu_items": order_items,
        "total_price": total_price,
        "type": order_type,  # 新增 type 欄位，1: 不使用優惠，2: 使用優惠
        "status": "pending",  # 訂單初始狀態
        "created_at": now,
        "updated_at": now,
    }

    # 插入訂單到數據庫
    try:
        order_collection.insert_one(order)
    except Exception as e:
        return jsonify({"error": "Failed to create order", "details": str(e)}), 500

    # 返回訂單結果
    return jsonify({"message": "Order created successfully", "order": order}), 201

'''
#優惠券系統api
# ------------------------------------------------------
@app.route('/coupons', methods=["POST"])
def buy_coupons():
    """購買優惠券放到購物車"""

'''



if __name__ == "__main__":
    app.run(debug=True)
