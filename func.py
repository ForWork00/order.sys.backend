import uuid, io, openpyxl, matplotlib, os, requests
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
from mongoDB import get_revenues, get_expenses
from collections import defaultdict
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


""" userID """
def create_uuid():
    return str(uuid.uuid4()).replace("-", "")[:8]


""" 根據指定的時間（日、月、年）從日期字串中提取對應的關鍵字 """
def extract_date_key(date_str:str, granularity:str) -> str:
    date_obj=datetime.fromisoformat(date_str)
    if granularity=="year":
        return str(date_obj.year)
    elif granularity=="month":
        return f"{date_obj.year}-{date_obj.month:02d}"
    elif granularity=="day":
        return f"{date_obj.year}-{date_obj.month:02d}-{date_obj.day:02d}"
    else:
        raise ValueError("Invalid, Use 'day', 'month', or 'year'.")


""" 指定日期類型進行分組計算總和 """
def process_data(revenues, expenses, date_type):
    result={"revenues":{}, "expenses":{}}

    for rev in revenues:
        date_key=extract_date_key(rev["updated_at"], date_type)
        result["revenues"][date_key]=result["revenues".get(date_key, 0)+rev["total_price"]]

    for exp in expenses:
        date_key=extract_date_key(exp["created_time"], date_type)
        result["expenses"][date_key]=result["expenses".get(date_key, 0)+exp["amount"]]
    return result


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
        return response_data["data"]["link"]
    else:
        raise Exception(f"Imgur upload failed: {response_data}")
