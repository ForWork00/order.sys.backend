from flask import Flask, request, jsonify
from cachetools import TTLCache
from datetime import datetime
import re
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# 暫存最近 100 筆候位資料，TTL 設定為 1 小時（3600 秒）
queue_cache = TTLCache(maxsize=100, ttl=3600)

# 全域變數用於追蹤候位狀態
queue_counter = 1  # 自增的候位號碼
current_queue_number = None  # 目前已叫號的號碼，若無則為 None
next_queue_number = None  # 下一組候位號碼
remaining_groups = 0  # 候位中尚未叫號的組數

"""
#error code
400 ->請求參數錯誤
403 ->號碼狀態無法呼叫
405 ->號碼不存在
""" 

def update_queue_info():
    """
    更新目前號碼、下一組號碼與剩餘組數的資訊。
    - current_queue_number：顯示最後一個叫過的號碼（若無則為 None）。
    - next_queue_number：顯示第一個 waiting 狀態的號碼。
    - remaining_groups：顯示剩餘候位組數。
    """
    global current_queue_number, next_queue_number, remaining_groups
    waiting_queues = sorted(num for num, data in queue_cache.items() if data["status"] == "waiting")
    
    # 目前號碼顯示已叫過的最後一組號碼，還未叫號則為 None
    current_queue_number = None if not waiting_queues else waiting_queues[0] - 1
    next_queue_number = waiting_queues[0] if waiting_queues else None  # 下一組候位號碼
    remaining_groups = len(waiting_queues) - 1 if len(waiting_queues) > 1 else 0  # 剩餘組數


def take_queue():
    """
    抽取候位號碼：
    - 支援 JSON 和 form-data 格式的請求。
    - 檢查必要參數（people、source），並驗證格式。
    - 來源可以是 Line official 或 onsite，Line official 需提供姓名與電話號碼。
    """
    global queue_counter
    if request.is_json:
        data = request.get_json()
    else:
        data = {key.strip(): value for key, value in request.form.items()}  # 處理 form-data

    # 檢查必要參數
    if "people" not in data or "source" not in data:
        return jsonify({"error": "缺少必要參數"}), 400

    # 驗證人數是否為有效數字
    try:
        people = int(data["people"])
    except ValueError:
        return jsonify({"error": "人數必須為有效數字"}), 400

    if people <= 0:
        return jsonify({"error": "人數必須大於 0"}), 400

    source = data["source"]
    if source not in ["Line official", "onsite"]:
        return jsonify({"error": "來源只能是 Line official 或 onsite"}), 400 

    # 如果是 Line official，則需要提供有效的姓名與電話號碼
    name = data.get("name")
    phone = data.get("phone")
    if source == "Line official":
        if not name or not re.match(r"^[A-Za-z\u4e00-\u9fa5]+$", name):
            return jsonify({"error": "姓名不可包含數字或特殊符號"}), 400
        if not phone or len(phone) != 10 or not phone.isdigit() or not phone.startswith("09"):
            return jsonify({"error": "電話號碼格式不正確，必須為 09 開頭的 10 碼數字"}), 400

    # 生成號碼並更新 queue_counter
    queue_number = queue_counter
    queue_counter += 1

    # 儲存候位資料到快取
    queue_cache[queue_number] = {
        "queue_number": queue_number,
        "name": name,
        "phone": phone,
        "people": people,
        "source": source,
        "status": "waiting",
        "created_at": datetime.utcnow()
    }

    # 更新候位資訊
    update_queue_info()

    return jsonify({"queue_number": queue_number, "status": "waiting"})


def cancel_queue(queue_number):
    """
    取消候位號碼：
    - 若號碼存在於快取中，將其移除並更新候位資訊。
    - 如果號碼不存在或已過期，回傳 404。
    """
    if queue_number not in queue_cache:
        return jsonify({"error": "號碼不存在或已過期"}), 404

    queue_cache.pop(queue_number)  # 從快取移除該號碼
    update_queue_info()
    return jsonify({"queue_number": queue_number, "status": "cancelled"})


def call_specific_queue(queue_number):
    """
    指定叫號：
    - 僅限 waiting 狀態的號碼能被叫號，並將其移除快取。
    - 若號碼不存在或非 waiting 狀態，回傳相應錯誤。
    """
    if queue_number not in queue_cache:
        return jsonify({"error": "號碼不存在或已過期"}), 404

    if queue_cache[queue_number]["status"] != "waiting":
        return jsonify({"error": "該號碼無法被叫號"}), 403

    queue_cache.pop(queue_number)  # 從快取移除該號碼
    update_queue_info()
    return jsonify({"queue_number": queue_number, "status": "completed"})


def auto_call_queue():
    """
    自動叫下一個候位號碼：
    - 依序尋找第一個 waiting 狀態的號碼，並將其設為 completed。
    - 若無待叫號碼，回傳 405 錯誤。
    """
    global current_queue_number
    for queue_number, data in sorted(queue_cache.items()):
        if data["status"] == "waiting":
            current_queue_number = queue_number  # 更新目前號碼
            queue_cache.pop(queue_number)  # 從快取移除該號碼
            update_queue_info()
            return jsonify({"queue_number": queue_number, "status": "completed"})

    return jsonify({"error": "目前無候位號碼"}), 405


def get_queue_info():
    """
    取得候位資訊：
    - current_number：目前號碼（若無已叫號，顯示為 None）。
    - next_number：下一組候位號碼。
    - next_people：下一組人數（若無則為 0）。
    - remaining_groups：尚未叫號的組數。
    """
    next_people = queue_cache[next_queue_number]["people"] if next_queue_number else 0
    return jsonify({
        "current_number": current_queue_number,
        "next_number": next_queue_number,
        "next_people": next_people,
        "remaining_groups": remaining_groups
    })


