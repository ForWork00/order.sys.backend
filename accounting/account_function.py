import os
from dotenv import load_dotenv
from flask import request, jsonify
from datetime import datetime
from mongoDB import get_accounting, get_AccountHistory

load_dotenv()

#查看寫入的紀錄
def get_history():
    try:
        history_collection = get_AccountHistory()
        account_code = request.args.get("account_code")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        query = {}

        if account_code:
            query["account_code"] = account_code

        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                query["timestamp"]["$lte"] = datetime.strptime(end_date, "%Y-%m-%d")

        histories = list(history_collection.find(query))
        for history in histories:
            history["_id"] = str(history["_id"])

        return jsonify({"histories": histories}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
#寫入用的API 可輸入負數數字 
def add_entry():
    try:
        history_collection = get_AccountHistory()
        account_collection = get_accounting()
        data = request.get_json()
        if not data or "account_code" not in data or "amount" not in data:
            return jsonify({"error": "請提供有效的 account_code 和 amount"}), 400
        #透過項目的代碼來進行寫入
        account_code = data["account_code"]
        amount = data["amount"]

        # 查找指定的第四級科目
        account = account_collection.find_one(
            {"second_grade.third_grade.fourth_grade.account_code": account_code}
        )

        if not account:
            return jsonify({"error": "未找到指定的科目"}), 404

        account_name = ""
        category_name = ""
        # 更新第四級的 `end_balance`
        for second in account.get("second_grade", []):
            for third in second.get("third_grade", []):
                for fourth in third.get("fourth_grade", []):
                    if fourth.get("account_code") == account_code:
                        fourth["end_balance"] = (fourth.get("end_balance", 0) or 0) + amount
                        account_name = fourth.get("account", "")  # 獲取科目名稱
                        category_name = account.get("account", "")  # 第一級科目名稱

        # 更新 MongoDB 資料庫
        account_collection.update_one({"_id": account["_id"]}, {"$set": account})

        #紀錄歷史寫入
        history = {
            "timestamp": datetime.now(),
            "account_code": account_code,
            "amount": amount,
            "category": category_name,
            "account_name": account_name  # 添加科目名稱
        }
        history_id = history_collection.insert_one(history).inserted_id

        # 轉換 ObjectId 為字串
        history["_id"] = str(history_id)

        return jsonify({"message": "帳目更新成功並記錄歷史", "history": history}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
#寫入期初餘額
def set_opening_balance():

    account_collection = get_accounting()
    data = request.get_json()
    account_code = data.get("account_code")
    amount = data.get("amount")

    if not account_code or amount is None:
        return jsonify({"error": "請提供有效的 account_code 和 amount"}), 400

    account = account_collection.find_one({"second_grade.third_grade.fourth_grade.account_code": account_code})
    if not account:
        return jsonify({"error": "未找到指定的科目"}), 404

    for second in account.get("second_grade", []):
        for third in second.get("third_grade", []):
            for fourth in third.get("fourth_grade", []):
                if fourth.get("account_code") == account_code:
                    fourth["opening_balance"] = amount  # 設定期初餘額

    account_collection.update_one({"_id": account["_id"]}, {"$set": account})
    return jsonify({"message": "期初餘額更新成功"}), 200