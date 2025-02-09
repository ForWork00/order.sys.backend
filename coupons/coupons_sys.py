from datetime import datetime, timedelta
from mongoDB import get_user_collection, get_coupons_collection
import random
from flask import request, jsonify
from datetime import datetime

users_collection = get_user_collection()
coupons_collection = get_coupons_collection()

def generate_coupon_code():
    """生成 8 位數的隨機優惠券碼"""
    return "COUP" + str(random.randint(100000, 999999))

def get_user_coupons_sys(user_id):
    """獲取會員所有的優惠券"""
    coupons = list(coupons_collection.find({"user_id": user_id}))

    if not coupons:
        return jsonify({"message": "請去兌換優惠券"}), 200

    return jsonify({"coupons": coupons}), 200

def delete_coupon_sys(coupon_id):
    """刪除單一優惠券"""
    coupon = coupons_collection.find_one({"_id": coupon_id})

    if not coupon:
        return jsonify({"error": "Coupon not found"}), 404

    # 從資料庫刪除該優惠券
    coupons_collection.delete_one({"_id": coupon_id})

    return jsonify({"message": "Coupon deleted successfully"}), 200

def create_coupon_sys():
    """會員使用點數兌換優惠券"""
    
    data = request.json
    user_id = data.get("user_id")
    discount = data.get("discount")
    cost = data.get("cost")

    if not user_id or not discount or not cost:
        return jsonify({"error": "Missing required fields"}), 400
    
    # 檢查會員是否存在
    user = users_collection.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "找不到該會員"}), 404
    
    # 確保會員點數足夠
    user_points = user.get("points", 0)
    if user_points < cost:
        return jsonify({"error": "會員點數不足"}), 400

    # 產生優惠券代碼
    coupon_code = generate_coupon_code()
    
    # 設定有效期限 (默認 30 天後過期)
    now = datetime.now()
    expiration_date = now + timedelta(days=30)

    # 優惠券資料
    coupon = {
        "_id": str(coupon_code),
        "user_id": str(user_id),
        "discount": int(discount),
        "cost": int(cost),
        "status": "active",  # 預設為可用狀態
        "created_at": now,
        "expiration_date": expiration_date
    }

    # 插入優惠券到資料庫
    try:
        coupons_collection.insert_one(coupon)
        # 扣除會員點數
        users_collection.update_one({"_id": user_id}, {"$inc": {"points": -cost}})
    except Exception as e:
        return jsonify({"error": "Failed to create coupon", "details": str(e)}), 500

    return jsonify({"message": "Coupon created successfully", "coupon": coupon}), 201

def get_all_coupons_sys():
    """取得所有優惠券（管理員用）"""
    try:
        # 從資料庫取得所有優惠券資料
        coupons = list(coupons_collection.find())
        
        # 將資料轉換為 JSON 格式
        coupon_list = [{
            "_id": str(coupon["_id"]),
            "user_id": coupon.get("user_id"),
            "discount": coupon.get("discount"),
            "cost": coupon.get("cost"),
            "status": coupon.get("status"),
            "created_at": coupon.get("created_at"),
            "expiration_date": coupon.get("expiration_date")
        } for coupon in coupons]
        
        return jsonify({"coupons": coupon_list}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def update_coupon_sys(coupon_id):
    """更新優惠券資訊"""
    data = request.json
    update_fields = {}

    # 支援更新的欄位
    if "discount" in data:
        update_fields["discount"] = data["discount"]
    if "cost" in data:
        update_fields["cost"] = data["cost"]
    if "status" in data:
        update_fields["status"] = data["status"]

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    # 更新資料庫中的優惠券
    result = coupons_collection.update_one({"_id": coupon_id}, {"$set": update_fields})

    if result.matched_count == 0:
        return jsonify({"error": "Coupon not found"}), 404
    elif result.modified_count > 0:
        return jsonify({"message": "Coupon updated successfully", "updated_fields": update_fields}), 200
    else:
        return jsonify({"message": "No changes made"}), 200

def get_coupon_sys(coupon_id):
    """獲取單一優惠券資訊"""
    coupon = coupons_collection.find_one({"_id": coupon_id})

    if not coupon:
        return jsonify({"error": "Coupon not found"}), 404

    coupon_data = {
        "_id": str(coupon["_id"]),
        "user_id": coupon.get("user_id"),
        "discount": coupon.get("discount"),
        "cost": coupon.get("cost"),
        "status": coupon.get("status"),
        "created_at": coupon.get("created_at"),
        "expiration_date": coupon.get("expiration_date")
    }

    return jsonify(coupon_data), 200
    
def create_admin_coupon_sys():
    """管理員新增優惠券 (預設 cost 為 0)"""

    data = request.json
    discount = data.get("discount")
    expiration_date_str = data.get("expiration_date")

    # 檢查必要欄位
    if not discount or not expiration_date:
        return jsonify({"error": "缺少必要欄位 (discount, expiration_date)"}), 400

    try:
        # 轉換 expiration_date 為 datetime.date 格式
        expiration_date = datetime.strptime(expiration_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "expiration_date 格式錯誤，應為 YYYY-MM-DD"}), 400

    # 產生優惠券代碼
    coupon_code = generate_coupon_code()

    # 優惠券資料 (預設 cost 為 0)
    coupon = {
        "_id": coupon_code,
        "user_id": None,  # 預設未綁定會員
        "discount": int(discount),
        "cost": 0,  # 預設為 0
        "status": "active",
        "created_at": datetime.now(),
        "expiration_date": datetime.strptime(expiration_date, "%Y-%m-%d")
    }

    # 插入優惠券到資料庫
    try:
        coupons_collection.insert_one(coupon)
    except Exception as e:
        return jsonify({"error": "新增優惠券失敗", "details": str(e)}), 500

    return jsonify({
        "message": "優惠券創建成功",
        "coupon": coupon
    }), 201

def bind_coupon_sys():
    """會員輸入優惠券代碼進行綁定"""
    data = request.json

    user_id = data.get("user_id")
    coupon_id = data.get("coupon_id")

    if not user_id or not coupon_id:
        return jsonify({"error": "Missing user_id or coupon_id"}), 400

    # 查找優惠券
    coupon = coupons_collection.find_one({"_id": str(coupon_id)})

    if not coupon:
        return jsonify({"error": "Coupon not found"}), 404

    # 檢查優惠券是否已經被使用
    if coupon.get("user_id"):
        return jsonify({"error": "Coupon is already assigned or does not exist"}), 400

    # 綁定優惠券到會員
    result = coupons_collection.update_one(
        {"_id": str(coupon_id)},
        {"$set": {"user_id": user_id}}
    )

    if result.modified_count > 0:
        return jsonify({"message": "Coupon successfully bound to user"}), 200
    else:
        return jsonify({"error": "Failed to bind coupon"}), 500