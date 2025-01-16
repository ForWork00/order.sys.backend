import uuid, stripe, os
import requests
from datetime import datetime
from flask import jsonify, request
from dotenv import load_dotenv
load_dotenv()

"""imgur"""
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID")
IMGUR_API_URL = os.getenv("IMGUR_API_URL")
IMGUR_CLIENT_SECRET = os.getenv("IMGUR_CLIENT_SECRET")
IMGUR_ACCESS_TOKEN = os.getenv("IMGUR_ACCESS_TOKEN")
"""generate_order_id"""
current_date = None # 用來存儲當天的日期
sequence_number = 0 # 用來存儲當天的序號


def create_uuid():
    return str(uuid.uuid4()).replace("-", "")[:8]

stripe.api_key="stripePay_key"
def stripe_pay():
    try:
        data = request.json
        amount = int(data["amount"]) *100

        payment_intent=stripe.PaymentIntent.create(
            amount=amount,
            currency="twd",
            payment_method="card",
            confirm=True,
            return_url="http://localhost:4242/success"
        )
        return jsonify(payment_intent)    # 返回JSON
    except Exception as e:
        return jsonify(error=str(e)),403   # 如果創建支付時發生錯誤，返回錯誤訊息

def generate_order_id():
    """
    訂單建立規則
    日期、使用者的uuid
    如:
    時區 UTC+8
    今年2024/12/31 11:14
    例如當天第一筆訂單會出現001以此類推
    跨日則會重製
    menber = "001"
    結果會出現如下
    2412311114001
    """
    global current_date, sequence_number

    # 取得當前日期和時間（時區 UTC+8）
    now = datetime.now()
    date_part = now.strftime('%y%m%d') # 提取日期部分，例如 "241231"
    time_part = now.strftime('%H%M')   # 提取時間部分，例如 "1114"

    if current_date != date_part:  # 檢查是否是新的一天
        current_date = date_part   # 更新為新的日期
        sequence_number = 0        # 重置當天序號

    sequence_number += 1
    menber = f"{sequence_number:03}" # 格式化為 3 位數字，例如 "001"

    order_id = f"{date_part}{time_part}{menber}"
    return order_id






def upload_image_to_imgur(image_data):
    """上傳圖片至 imgur 並回傳圖片 URL"""

    headers = {"Authorization": f"Bearer {IMGUR_ACCESS_TOKEN}"}
    files = {"image": image_data}

    response = requests.post(IMGUR_API_URL, headers=headers, files=files)
    response_data = response.json()

    if response.status_code == 200 and response_data.get("success"):
        return response_data["data"]["link"]
    else:
        raise Exception(f"Imgur upload failed: {response_data}")