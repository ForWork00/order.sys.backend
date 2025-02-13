from flask import request, jsonify
from datetime import datetime
from mongoDB import get_reservations_collection, reservation_settings_collection, get_user_collection
from func import generate_reservation_id

reservations_collection = get_reservations_collection()

reservation_settings = reservation_settings_collection()

users_collection = get_user_collection()

def set_reservation_slots_sys():
    """店家設定時段、桌數與每桌人數"""
    data = request.json
    slots = data.get("slots")

    if not slots or not isinstance(slots, list):
        return jsonify({"error": "slots is required and must be a list"}), 400

    for slot in slots:
        if "time_range" not in slot or "tables" not in slot or "max_per_table" not in slot:
            return jsonify({"error": "Each slot must include 'time_range', 'tables', and 'max_per_table'"}), 400

        # 檢查資料型態
        time_range = slot.get("time_range")
        tables = slot.get("tables")
        max_per_table = slot.get("max_per_table")

        if not isinstance(time_range, str):
            return jsonify({"error": f"Invalid time_range format: {time_range}"}), 400

        if not isinstance(tables, int) or tables <= 0:
            return jsonify({"error": f"Invalid tables value: {tables}. Must be a positive integer."}), 400

        if not isinstance(max_per_table, int) or max_per_table <= 0:
            return jsonify({"error": f"Invalid max_per_table value: {max_per_table}. Must be a positive integer."}), 400

        # 儲存時段設定到 MongoDB
        try:
            reservation_settings.update_one(
                {"time_range": time_range},
                {"$set": {"tables": tables, "max_per_table": max_per_table}},
                upsert=True
            )
        except Exception as e:
            return jsonify({
                "error": "Failed to update reservation slots",
                "details": str(e)
            }), 500

    return jsonify({"message": "Reservation slots updated successfully"}), 200



def add_reservation_sys():
    """新增預約"""
    data = request.json
    user_id = data.get("user_id")
    time_range = data.get("time_range")
    guests = data.get("guests")
    contact_info = data.get("contact_info", "")
    reservation_date_str = data.get("reservation_date")  # 使用字串表示的預約日期

    # 檢查是否有必要的欄位
    if not all([user_id, time_range, guests, reservation_date_str, contact_info]):
        return jsonify({"error": "Missing required fields"}), 400

    # 轉換 reservation_date 為 datetime
    try:
        reservation_date = datetime.strptime(reservation_date_str, "%Y-%m-%d")  # 轉為 datetime.datetime 格式
    except ValueError:
        return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD"}), 400

    # 確認 user_id 是否有效
    user_data = None
    if user_id:
        user_data = users_collection.find_one({"_id": user_id})
        if not user_data:
            return jsonify({"error": "Invalid user_id"}), 400
        
    # 檢查時段是否可用
    slot = reservation_settings.find_one({"time_range": time_range})
    if not slot:
        return jsonify({"error": "Invalid time range"}), 400

    max_per_table = slot["max_per_table"]
    total_tables = slot["tables"]

    # 計算該時段的現有預約人數
    existing_reservations = reservations_collection.find({
        "reservation_date": reservation_date,
        "time_range": time_range
    })
    total_reserved = sum(reservation["guests"] for reservation in existing_reservations)

    if total_reserved + guests > total_tables * max_per_table:
        return jsonify({"error": "Not enough seats available"}), 400

    # 生成預約 ID
    reservation_id = generate_reservation_id()

    # 儲存預約
    reservation = {
        "_id": reservation_id,
        "user_id": user_id,
        "time_range": time_range,
        "guests": guests,
        "reservation_date": reservation_date,  # 存儲為 datetime.datetime
        "contact_info": contact_info,
        "status": "active",
        "created_at": datetime.now()
    }

    try:
        reservations_collection.insert_one(reservation)
    except Exception as e:
        return jsonify({"error": "Failed to create reservation", "details": str(e)}), 500

    return jsonify({
        "message": "Reservation created successfully",
        "reservation_id": reservation_id
    }), 201



def get_reservations_sys():
    """查詢聯絡資訊"""
    contact_info = request.args.get("contact_info")  # 只需聯絡資訊即可查詢

    # 確認是否有提供聯絡資訊
    if not contact_info:
        return jsonify({"error": "contact_info is required"}), 400

    query = {"contact_info": {"$regex": contact_info, "$options": "i"}}  # 支援部分匹配和大小寫不敏感

    try:
        # 查詢符合條件的預約
        reservations = list(reservations_collection.find(query))

        # 格式化 ObjectId
        for reservation in reservations:
            reservation["_id"] = str(reservation["_id"])

        # 若查無預約
        if not reservations:
            return jsonify({"message": "No reservations found for the provided contact_info"}), 200

        return jsonify(reservations), 200

    except Exception as e:
        return jsonify({"error": "Failed to retrieve reservations", "details": str(e)}), 500


def cancel_reservation_sys():
    """根據 contact_info 和 user_id 取消預約"""
    data = request.json
    contact_info = data.get("contact_info")
    user_id = data.get("user_id")

    # 驗證必填欄位
    if not contact_info or not user_id:
        return jsonify({"error": "Both contact_info and user_id are required"}), 400

    try:
        # 查找對應的預約
        reservation = reservations_collection.find_one({"contact_info": contact_info, "user_id": user_id, "status": "active"})

        if not reservation:
            return jsonify({"error": "Reservation not found"}), 404

        # 更新預約狀態為 "canceled"
        reservations_collection.update_one(
            {"_id": reservation["_id"]},
            {"$set": {"status": "canceled"}}
        )

        return jsonify({"message": "Reservation canceled successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Failed to cancel reservation", "details": str(e)}), 500


def get_all_reservations_sys():
    """查詢所有預約"""
    try:
        # 查詢資料庫中所有預約
        reservations = list(reservations_collection.find())

        # 如果有預約，格式化為 JSON
        if reservations:
            for reservation in reservations:
                reservation["_id"] = str(reservation["_id"])  # 將 ObjectId 轉換為字串

            return jsonify({"reservations": reservations}), 200
        else:
            return jsonify({"message": "No reservations found"}), 200

    except Exception as e:
        return jsonify({"error": "Failed to retrieve reservations", "details": str(e)}), 500

def get_reservations_by_date_sys(): 
    """根據指定日期查詢預約"""
    date_str = request.args.get("date")  # 從查詢參數中獲取日期

    if not date_str:
        return jsonify({"error": "Date is required. Please provide a date in the format YYYY-MM-DD"}), 400

    try:
        # 確保日期格式正確
        date = datetime.strptime(date_str, "%Y-%m-%d")

        # 設定範圍查詢：當天的開始和結束時間
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())

        # 查詢 reservation_date 落在當天範圍內的所有預約
        reservations = list(reservations_collection.find({
            "reservation_date": {"$gte": start_of_day, "$lt": end_of_day}
        }))

        # 如果有預約，格式化為 JSON
        if reservations:
            for reservation in reservations:
                reservation["_id"] = str(reservation["_id"])  # 將 ObjectId 轉換為字串

            return jsonify({"reservations": reservations}), 200
        else:
            return jsonify({"message": f"No reservations found for {date_str}"}), 200

    except ValueError:
        return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD"}), 400
    except Exception as e:
        return jsonify({"error": "Failed to retrieve reservations", "details": str(e)}), 500

def get_today_reservations_sys():
    """查詢當天所有預約"""
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())  # 今日的 00:00:00
    today_end = datetime.combine(datetime.now().date(), datetime.max.time())  # 今日的 23:59:59

    try:
        # 查詢 reservation_date 在今天範圍內的所有預約
        reservations = list(reservations_collection.find({
            "reservation_date": {
                "$gte": today_start,
                "$lt": today_end
            }
        }))

        # 如果有預約，格式化為 JSON
        if reservations:
            for reservation in reservations:
                reservation["_id"] = str(reservation["_id"])  # 將 ObjectId 轉換為字串

            return jsonify({"reservations": reservations}), 200
        else:
            return jsonify({"message": "No reservations found for today"}), 200

    except Exception as e:
        return jsonify({"error": "Failed to retrieve reservations", "details": str(e)}), 500
   
def delete_reservation_sys(reservation_id):
    """根據預約 ID 刪除預約"""
    try:
        # 在資料庫中查找該預約
        reservation = reservations_collection.find_one({"_id": reservation_id})

        if not reservation:
            return jsonify({"error": f"Reservation with ID {reservation_id} not found"}), 404

        # 刪除預約
        result = reservations_collection.delete_one({"_id": reservation_id})

        if result.deleted_count > 0:
            return jsonify({"message": f"Reservation with ID {reservation_id} deleted successfully"}), 200
        else:
            return jsonify({"error": "Failed to delete reservation"}), 500

    except Exception as e:
        return jsonify({"error": "Failed to delete reservation", "details": str(e)}), 500
