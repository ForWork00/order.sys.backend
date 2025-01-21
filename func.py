import uuid, io, openpyxl, matplotlib, os
import pandas as pd
import matplotlib.pyplot as plt

from io import BytesIO
from datetime import datetime
from mongoDB import get_revenues, get_expenses
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()



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
