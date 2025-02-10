import uuid, io, openpyxl, matplotlib, os, requests
import pandas as pd
import matplotlib.pyplot as plt
import qrcode
from io import BytesIO
from datetime import datetime
from mongoDB import get_user_collection
from flask import request, jsonify
from dotenv import load_dotenv

load_dotenv()

collection = get_user_collection()

"""imgur"""
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID")
IMGUR_API_URL = os.getenv("IMGUR_API_URL")
IMGUR_CLIENT_SECRET = os.getenv("IMGUR_CLIENT_SECRET")
IMGUR_ACCESS_TOKEN = os.getenv("IMGUR_ACCESS_TOKEN")
"""generate_order_id"""
current_date = None # 用來存儲當天的日期
sequence_number = 0 # 用來存儲當天的序號


""" userID """
def create_uuid():
    return str(uuid.uuid4()).replace("-", "")[:8]

""" 會員資訊回傳格式 """
def format_user_data(user):
    return {
        "id":user["_id"],
        "email":user.get("email", "unknow"),
        "register":user.get("register_time", "unknow"),
        "points":user.get("points", 0)
    }

""" 計算總額 """
def total(data, key):
    return sum(item[key] for item in data)



""" 收入支出趨勢圖 """
matplotlib.use('Agg')  # 設置無需 GUI 的後端
def generate_trend_chart(revenues, expenses, chart_type="line"):   # 生成趨勢圖
    revenues_dates=[item["updated_at"] for item in revenues]
    revenues_values=[item["total_price"] for item in revenues]

    expenses_dates=[item["created_time"] for item in expenses]
    expenses_values=[item["amount"] for item in expenses]
    # 繪製圖表
    plt.figure(figsize=(10, 6))
    if chart_type=="line":
        plt.plot(revenues_dates, revenues_values, label="Revenue", color="green", marker="o")
        plt.plot(expenses_dates, expenses_values, label="Expense", color="red", marker="o")
    elif chart_type=="bar":
        plt.bar(revenues_dates, revenues_values, label="Revenue", color="green", alpha=0.7)
        plt.bar(expenses_dates, expenses_values, label="Expense", color="red",alpha=0.7)
    
    plt.xlabel("Date")
    plt.ylabel("Amount")
    plt.title(f"Revenue & Expenses")
    plt.xticks(rotation=45)   # 旋轉 X 軸標籤以避免重疊
    plt.legend()
    plt.grid(True)

    # 儲存圖表
    file_name=f"trend_chart.png"
    chart_path=os.path.join(os.getcwd(), file_name)
    plt.savefig(chart_path)
    plt.close()
    return chart_path



""" 匯出 收入與支出excel """
def export_to_excel(Revenues, Expenses):
    df_Revenues=pd.DataFrame(Revenues)
    df_Expenses=pd.DataFrame(Expenses)

    output=io.BytesIO()   #寫入excell
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_Revenues.to_excel(writer, index=False, sheet_name="Revenues")
        df_Expenses.to_excel(writer, index=False, sheet_name="Expenses")
    output.seek(0)
    return output


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
        return {
            "image_url": response_data["data"]["link"], 
            "deletehash": response_data["data"]["deletehash"]
        }
    else:
        raise Exception(f"Imgur upload failed: {response_data}")


def delete_image_to_imgur(imgur_deletehash):
    """刪除 imgur 上的圖片，返回成功/失敗"""
    if not imgur_deletehash:
        return {"success": False, "error": "無效的 imgur_deletehash"}
    
    # 呼叫已認證 Imgur API 刪除圖片
    headers = {"Authorization": f"Bearer {IMGUR_ACCESS_TOKEN}"}
    response = requests.delete(f"{IMGUR_API_URL}/{imgur_deletehash}", headers=headers)

    if response.status_code == 200:
        return {"success": True}
    else:
        return {"success": False, "error": response.json()}


def generate_qr_code(order_id):
    """ 生成 QR Code 並直接回傳圖片檔案 """
    qr = qrcode.make(order_id)  # 生成 QR Code
    img_io = io.BytesIO()  # 建立記憶體中的檔案
    qr.save(img_io, format="PNG")  # 儲存為 PNG 格式
    img_io.seek(0)  # 將檔案指標移到開頭
    return img_io  # 回傳圖片資料
