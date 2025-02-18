import json
import pandas as pd
from flask import jsonify, send_file
from dotenv import load_dotenv
from mongoDB import get_accounting, get_AccountHistory  # 導入資料庫集合
import io

load_dotenv()

def Cash_Flow_Statement():
    """
    依據 IFRS 標準，將科目分類為 營業、投資、籌資活動現金流，並依照 IFRS 科目代碼精細分類。
    """
    try:
        account_collection = get_accounting()
        data = list(account_collection.find())

        cash_flow_statement = {
            "營業活動現金流量": [],
            "投資活動現金流量": [],
            "籌資活動現金流量": [],
            "現金及約當現金增減淨額": 0
        }

        for first_level in data:
            second_grades = first_level.get("second_grade", [])

            for second in second_grades:
                third_grades = second.get("third_grade", [])

                for third in third_grades:
                    fourth_grades = third.get("fourth_grade", [])

                    for fourth in fourth_grades:
                        account_code = fourth.get("account_code", "")
                        account_name = fourth.get("account", "")
                        opening_balance = fourth.get("opening_balance", 0) or 0
                        end_balance = fourth.get("end_balance", 0) or 0
                        net_change = end_balance - opening_balance

                        # 跳過期初和期末皆為 0 的科目
                        if opening_balance == 0 and end_balance == 0:
                            continue

                        category = None

                        # **營業活動現金流量**
                        if account_code.startswith(("11", "12", "13")):
                            category = "營業活動現金流量"  # 營業現金、應收帳款等
                        elif account_code.startswith(("21", "22")):
                            category = "營業活動現金流量"  # 短期負債、應付帳款
                        elif account_code.startswith(("4", "5", "6", "8")):
                            category = "營業活動現金流量"  # 營業收入、成本、費用、所得稅
                        
                        # **投資活動現金流量**
                        elif account_code.startswith(("14", "15", "16", "17")):
                            category = "投資活動現金流量"  # 固定資產、投資性資產
                        elif account_code.startswith(("71", "72", "73", "74")):
                            category = "投資活動現金流量"  # 業外收入，如股利、利息收入
                        elif account_code.startswith(("75", "76", "77", "78")):
                            category = "投資活動現金流量"  # 業外支出，如投資損失
                        
                        # **籌資活動現金流量**
                        elif account_code.startswith(("23", "24", "25")):
                            category = "籌資活動現金流量"  # 長期負債、公司債
                        elif account_code.startswith(("3")):
                            category = "籌資活動現金流量"  # 股東權益，增資、配息

                        if category:
                            cash_flow_statement[category].append({
                                "科目": account_name,
                                "代碼": account_code,
                                "期初餘額": opening_balance,
                                "期末餘額": end_balance,
                                "現金流量變動": net_change
                            })

                            # **計算現金流變動**
                            cash_flow_statement["現金及約當現金增減淨額"] += net_change

        return cash_flow_statement
    except Exception as e:
        return {"error": str(e)}

#導出現金流量表Excel
def save_cash_flow_statement():
    """
    生成現金流量表，並存為 Excel，確保正確分類「營業活動」與「籌資活動」。
    """
    try:
        result = Cash_Flow_Statement()  # 獲取現金流量表資料
        excel_file = save_to_excel(result)  # 保存至 Excel 並獲得 BytesIO 物件
        return send_file(
            excel_file,
            as_attachment=True,
            download_name="現金流量表.xlsx",  # 設定下載文件名
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # 設定 MIME 類型
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
def save_to_excel(data, file_name="現金流量表.xlsx"):
    """
    將現金流量表資料存為 Excel 檔案。
    """
    excel_data = []
    for category, entries in data.items():
        if category == "現金及約當現金增減淨額":
            continue  # 忽略此分類
        for entry in entries:
            excel_data.append({
                "分類": category,
                "科目": entry["科目"],
                "代碼": entry["代碼"],
                "期初餘額": entry["期初餘額"],
                "期末餘額": entry["期末餘額"],
                "現金流量變動": entry["現金流量變動"]
            })

    # 將資料轉換為 DataFrame 並保存至 BytesIO
    output = io.BytesIO()
    df = pd.DataFrame(excel_data)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="現金流量表")
        writer.sheets["現金流量表"].sheet_state = 'visible'  # 設定工作表狀態為可見
    output.seek(0)  # 將指標移回開頭
    return output