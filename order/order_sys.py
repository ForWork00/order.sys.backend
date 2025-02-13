from flask import request, jsonify, send_file
from datetime import datetime
from mongoDB import get_order_collection, get_menu_collection, get_user_collection, get_coupons_collection
from func import generate_order_id, generate_qr_code


menu_collection = get_menu_collection()
order_collection = get_order_collection()
users_collection = get_user_collection()
coupons_collection = get_coupons_collection()


def get_orders_sys():
    """取得訂單列表"""
    orders = list(order_collection.find())
    return jsonify(orders), 200


def get_order_sys(order_id):
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

def update_order_sys(order_id):
    """修改訂單資訊，並在訂單完成後回饋點數，或在取消時恢復優惠券"""
    data = request.json
    allowed_statuses = ["completed", "canceled"]  # 允許的狀態
    update_fields = {}

    # 查找訂單
    order = order_collection.find_one({"_id": order_id})
    if not order:
        return jsonify({"error": "Order not found"}), 404

    # 檢查訂單是否已完成
    if order.get("status") == "completed":
        return jsonify({"error": "Cannot modify a completed order"}), 400

    if "user_id" in data:
        new_user_id = data["user_id"]

        if order.get("user_id", "none").lower() != "none":
            return jsonify({"error": "Cannot modify user_id. Order already has a valid user."}), 400

        # 如果原來的 user_id 是 'none'，允許更新
        update_fields["user_id"] = new_user_id


    if "status" in data:
        new_status = data["status"]
        if new_status not in allowed_statuses:
            return jsonify({"error": f"Invalid status. Allowed values are {allowed_statuses}"}), 400
        update_fields["status"] = new_status

        # 訂單完成後執行回饋邏輯
        if new_status == "completed":
            user_id = order.get("user_id")
            final_price = float(order.get("final_price", 0) or 0)  # 確保 final_price 為數字
            coupon_code = order.get("coupon_code")

            # 非會員結帳  只顯示 "Order completed"
            if not user_id:
                update_fields["updated_at"] = datetime.now()
                order_collection.update_one({"_id": order_id}, {"$set": update_fields})
                return jsonify({"message": "Order completed"}), 200

            # 會員未使用優惠券 回傳會員 ID 和回饋點數
            if coupon_code is None or coupon_code == "" or coupon_code.lower() == "none":
                reward_points = int(final_price // 100)  # 100元回饋1點

                if reward_points > 0:
                    # 更新會員點數
                    result = users_collection.update_one(
                        {"_id": user_id},
                        {"$inc": {"points": reward_points}}  # 直接增加點數
                    )

                    if result.modified_count > 0:
                        print(f"會員 {user_id} 的點數已更新，增加 {reward_points} 點")
                        update_fields["updated_at"] = datetime.now()
                        order_collection.update_one({"_id": order_id}, {"$set": update_fields})
                        return jsonify({
                            "message": "Order completed",
                            "user_id": user_id,
                            "reward_points": reward_points
                        }), 200

            # 會員使用優惠券 → 只顯示 "Order completed"
            update_fields["updated_at"] = datetime.now()
            order_collection.update_one({"_id": order_id}, {"$set": update_fields})
            return jsonify({"message": "Order completed"}), 200
        
        # 訂單取消邏輯
        elif new_status == "canceled":
            # 若訂單使用了優惠券，恢復優惠券狀態為 "active"
            if coupon_code and coupon_code.lower() != "none":
                coupons_collection.update_one({"_id": coupon_code}, {"$set": {"status": "active"}})

            update_fields["updated_at"] = datetime.now()
            order_collection.update_one({"_id": order_id}, {"$set": update_fields})
            return jsonify({"message": "Order canceled"}), 200
        
    # 如果沒有更新任何欄位
    return jsonify({"error": "No valid fields to update"}), 400

def create_order_sys():
    """用戶新增訂單"""
    data = request.json
    user_id = data.get("user_id")
    items = data.get("items")  
    coupon_code = data.get("coupon_code")  # 用戶輸入的優惠券
    payment_method = data.get("payment_method")  # 付款方式: 'cash' 或 'online'

    if not items or not isinstance(items, list):
        return jsonify({"error": "items is required and must be a list"}), 400

    if payment_method not in ["cash", "online"]:
        return jsonify({"error": "Invalid payment_method. Allowed values are 'cash' or 'online'"}), 400

    # 確認 user_id 是否有效
    user_data = None
    if user_id:
        user_data = users_collection.find_one({"_id": user_id})
        if not user_data:
            return jsonify({"error": "Invalid user_id"}), 400

    # 檢查優惠券
    discount_amount = 0
    if user_data and coupon_code:
        coupon = coupons_collection.find_one({"_id": coupon_code, "user_id": user_id, "status": "active"})
        if not coupon:
            return jsonify({"error": "Invalid coupon _id or not assigned to this user"}), 400

        # 檢查優惠券是否過期
        if datetime.now() > coupon["expiration_date"]:
            return jsonify({"error": "Coupon has expired"}), 400

        discount_amount = int(coupon["discount"])  # 優惠金額

    # 查詢菜單項目
    menu_item_ids = [item["menu_item_id"] for item in items]
    menu_items = {item["_id"]: item for item in menu_collection.find({"_id": {"$in": menu_item_ids}})}

    invalid_ids = [menu_id for menu_id in menu_item_ids if menu_id not in menu_items]
    if invalid_ids:
        return jsonify({"error": "Some menu items are invalid", "invalid_ids": invalid_ids}), 400

    # **計算總價**
    order_items_dict = {}  # 用來合併相同菜單項目 & 相同備註的品項
    total_price = 0

    for order_item_data in items:
        menu_item_id = order_item_data["menu_item_id"]
        quantity = order_item_data.get("quantity", 1)
        note = order_item_data.get("note", "")  # 預設為空字串

        # 確保這個 `menu_item_id` 存在
        if menu_item_id not in menu_items:
            continue

        menu_item = menu_items[menu_item_id]
        price = menu_item["price"]
        total = price * quantity

        # 生成合併的 key (menu_item_id + note)
        key = f"{menu_item_id}::{note}"

        # 若相同品項 & 備註已存在，則合併數量
        if key in order_items_dict:
            order_items_dict[key]["quantity"] += quantity
            order_items_dict[key]["total"] += total
        else:
            order_items_dict[key] = {
                "id": menu_item["_id"],
                "name": menu_item["name"],
                "price": price,
                "quantity": quantity,
                "note": note,
                "total": total,
            }

        total_price += total

    # 轉換 `order_items_dict` 為 `order_items` 列表
    order_items = list(order_items_dict.values())

    # 確保折扣金額不超過訂單總額
    discount_amount = min(discount_amount, total_price)
    final_price = max(total_price - discount_amount, 0)  # 確保不低於 0 元
    order_type = 2 if discount_amount > 0 else 1  # 若有折扣則為類型 2

    # 構建訂單資料
    order_id = generate_order_id()
    now = datetime.now()
    order = {
        "_id": order_id,
        "user_id": str(user_id),  
        "menu_items": order_items,
        "total_price": int(total_price),  # 原價
        "final_price": int(final_price),  # 折扣後價格
        "discount_amount": int(discount_amount),  # 折扣金額
        "type": int(order_type),  
        "coupon_code": str(coupon_code if discount_amount > 0 else None),  # 記錄使用的優惠券
        "status": "pending",
        "payment_method": payment_method,  # 記錄付款方式  
        "created_at": now,
        "updated_at": now,
    }

    # 插入訂單到數據庫
    try:
        order_collection.insert_one(order)
        # 標記優惠券為已使用
        if coupon_code and discount_amount > 0:
            coupons_collection.update_one({"_id": coupon_code}, {"$set": {"status": "used"}})
    except Exception as e:
        return jsonify({"error": "Failed to create order", "details": str(e)}), 500
    
    # 現場付款才回傳 QR Code
    if payment_method == "cash":
        qr_code_image = generate_qr_code(order_id)
        return send_file(qr_code_image, mimetype="image/png")

    return jsonify({
        "message": "Order created successfully",
        "order": order
    }), 201

def delete_order_sys(order_id):
    """刪除訂單"""
    order = order_collection.find_one({"_id": order_id})

    if not order:
        return jsonify({"error": "Order not found"}), 404

    # 嘗試刪除訂單
    result = order_collection.delete_one({"_id": order_id})

    if result.deleted_count > 0:
        return jsonify({"message": "Order deleted successfully"}), 200
    else:
        return jsonify({"error": "Failed to delete order"}), 500