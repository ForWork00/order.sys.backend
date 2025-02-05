import os, random
from dotenv import load_dotenv
from flask import request, jsonify
from datetime import datetime
from mongoDB import get_menu_collection
from func import upload_image_to_imgur, delete_image_to_imgur

load_dotenv()

menu_collection = get_menu_collection()

def generate_unique_id():
    """生成 8 位數不重複的 ID"""
    while True:
        new_id = str(random.randint(10000000, 99999999))  # 8 位數字
        if not menu_collection.find_one({"_id": new_id}):  # 確保唯一
            return new_id

def get_menu_sys():
    try:
        menu = list(menu_collection.find())
        if not menu:
            return jsonify({"error": "Menu not found"}), 404
        return jsonify(menu), 200
    
    except Exception as e:
        return {"error": str(e)}

def get_menu_item_sys(item_id):

    try:
        # 將 item_id 轉換為 str
        item_id = str(item_id)
    except ValueError:
        return jsonify({"error": "菜單編號格式錯誤"}), 400
    
    menu_item = menu_collection.find_one({"_id": item_id})

    if not menu_item:
        return jsonify({"error": "菜單項目未找到"}), 404
    return jsonify(menu_item), 200

def create_menu_item_sys():
    """建立菜單品項"""
    data = request.form
    name = data.get("name")
    description = data.get("description", "")
    price = data.get("price")
    category = data.get("category")
    image = request.files.get("image")
    now = datetime.now()

    if not name or not price or not category:
        return jsonify({"error": "缺少必要欄位"}), 400

    try:
        menu_id = generate_unique_id()
        
        # 預設圖片資訊
        image_url = ""
        imgur_deletehash = ""

        if image:
            imgur_response = upload_image_to_imgur(image.read())  # 回傳 dict
            image_url = imgur_response["image_url"]
            imgur_deletehash = imgur_response["deletehash"]

        menu_item = {
            "_id": menu_id,
            "name": str(name),
            "description": str(description),
            "price": int(price),
            "category": str(category),
            "image_url": str(image_url),
            "imgur_deletehash": str(imgur_deletehash),
            "is_available": True,
            "created_at": now,
            "updated_at": now
        }

        menu_collection.insert_one(menu_item)
        return jsonify({"message": "菜單品項成功建立", "item": menu_item}), 201
    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500

def update_menu_item_sys(item_id):
    """修改單一菜單品項資訊"""
    try:
        # 將 item_id 轉換為 str（與資料庫的 _id 格式一致）
        item_id = str(item_id)
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
    allowed_fields = {"name", "description", "price", "category", "is_available"}

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

    updated_menu_item = menu_collection.find_one({"_id": item_id})
    # 返回更新後的菜單項目
    return jsonify(updated_menu_item), 200
  
def delete_menu_item_sys(item_id):
    """刪除菜單並同時刪除以上傳至 imgur 的圖片"""
    try:
        # 將 item_id 轉換為 str（與資料庫的 _id 格式一致）
        item_id = str(item_id)
    except ValueError:
        return jsonify({"error": "Invalid item_id format"}), 400

    menu_item = menu_collection.find_one({"_id": item_id})
    if not menu_item:
        return jsonify({"error": "菜單項目未找到"}), 404

    #從 MongoDB 獲取圖片資訊
    imgur_deletehash = menu_item.get("imgur_deletehash")  # 確保你存了 deletehash

    # 先嘗試刪除圖片（如果有圖片）
    if imgur_deletehash:
        imgur_response = delete_image_to_imgur(imgur_deletehash)
        if not imgur_response["success"]:
            return jsonify({"error": "無法刪除圖片", "imgur_response": imgur_response["error"]}), 500

    # 從 MongoDB 刪除該菜單項目
    menu_collection.delete_one({"_id": item_id})

    return jsonify({"message": "菜單項目已成功刪除"}), 200