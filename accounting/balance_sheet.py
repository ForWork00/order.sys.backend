import json
import pandas as pd
from flask import jsonify, send_file
from dotenv import load_dotenv
from mongoDB import get_accounting, get_AccountHistory  # 導入資料庫集合
import io

load_dotenv()

def balance_sheet():
    """
    依據 IFRS 標準將科目分類為：
    - 流動資產（Current Assets）
    - 非流動資產（Non-Current Assets）
    - 流動負債（Current Liabilities）
    - 非流動負債（Non-Current Liabilities）
    - 權益（Equity）
    """
    try:
        account_collection = get_accounting()  # 取得會計紀錄
        data = list(account_collection.find())
    
        balance_sheet_data = {
            "流動資產": [],
            "非流動資產": [],
            "流動負債": [],
            "非流動負債": [],
            "權益": [],
            "流動資產合計": 0,
            "非流動資產合計": 0,
            "流動負債合計": 0,
            "非流動負債合計": 0,
            "權益合計": 0,
            "資產總計": 0,
            "負債及權益總計": 0
        }

        for first_level in data:
            second_grades = first_level.get("second_grade", [])

            for second in second_grades:
                second_code = second.get("account_code", "")
                third_grades = second.get("third_grade", [])

                for third in third_grades:
                    fourth_grades = third.get("fourth_grade", [])

                    for fourth in fourth_grades:
                        account_code = fourth.get("account_code", "")
                        account_name = fourth.get("account", "")
                        opening_balance = fourth.get("opening_balance", 0) or 0
                        end_balance = fourth.get("end_balance", 0) or 0

                        # **略過 期初=0 且 期末=0 的科目**
                        if opening_balance == 0 and end_balance == 0:
                            continue

                        # **分類資產負債表**
                        category = None
                        first_digit = account_code[0] if account_code else ""

                        # ✅ **資產分類**
                        if first_digit == "1":
                            if second_code.startswith(("11", "12", "13")):  # 流動資產
                                category = "流動資產"
                            elif second_code.startswith(("14", "15", "16", "17")):  # 非流動資產
                                category = "非流動資產"

                        # ✅ **負債分類**
                        elif first_digit == "2":
                            if second_code.startswith(("21", "22")):  # 流動負債
                                category = "流動負債"
                            elif second_code.startswith(("23", "24", "25")):  # 非流動負債
                                category = "非流動負債"

                        # ✅ **權益分類**
                        elif first_digit == "3":
                            category = "權益"

                        if category:
                            # **存入分類**
                            balance_sheet_data[category].append({
                                "科目": account_name,
                                "代碼": account_code,
                                "期初餘額": opening_balance,
                                "期末餘額": end_balance
                            })

                            # **累加合計數據**
                            if category == "流動資產":
                                balance_sheet_data["流動資產合計"] += end_balance
                            elif category == "非流動資產":
                                balance_sheet_data["非流動資產合計"] += end_balance
                            elif category == "流動負債":
                                balance_sheet_data["流動負債合計"] += end_balance
                            elif category == "非流動負債":
                                balance_sheet_data["非流動負債合計"] += end_balance
                            elif category == "權益":
                                balance_sheet_data["權益合計"] += end_balance

        # **計算總計**
        balance_sheet_data["資產總計"] = (
            balance_sheet_data["流動資產合計"] + balance_sheet_data["非流動資產合計"]
        )
        balance_sheet_data["負債及權益總計"] = (
            balance_sheet_data["流動負債合計"] + balance_sheet_data["非流動負債合計"] + balance_sheet_data["權益合計"]
        )

        return balance_sheet_data  # 返回資產負債表數據
    except Exception as e:
        return {"error": str(e)}

def balance_sheet_save():
    """
    產生資產負債表，並存為 Excel。
    """
    try:
        # 獲取資產負債表數據
        response = balance_sheet()  # 直接返回字典，不是 Response 物件
        
        if isinstance(response, tuple):  # 若為元組，表示有錯誤
            result, status_code = response
            if status_code != 200:
                return jsonify(result), status_code  
        else:
            result = response  

        if "error" in result:
            return jsonify(result), 500 
        
        excel_file = save_balance_sheet_to_excel(result)  # 保存至 Excel 並獲得 BytesIO 物件
        return send_file(
            excel_file,
            as_attachment=True,
            download_name="資產負債表.xlsx",  # 設定下載文件名
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # 設定 MIME 類型
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def save_balance_sheet_to_excel(data, file_name="資產負債表.xlsx"):
    """
    將資產負債表資料存為 Excel 檔案。
    """
    excel_data = []
    categories = ["流動資產", "非流動資產", "流動負債", "非流動負債", "權益"]
    
    for category in categories:
        entries = data.get(category, [])
        for entry in entries:
            excel_data.append({
                "分類": category,
                "科目": entry["科目"],
                "代碼": entry["代碼"],
                "期初餘額": entry["期初餘額"],
                "期末餘額": entry["期末餘額"]
            })

    for category in categories:
        category_total_key = f"{category}合計"
        if category_total_key in data:
            excel_data.append({
                "分類": category + "合計",
                "科目": category_total_key,
                "代碼": "",
                "期初餘額": "",
                "期末餘額": data[category_total_key]
            })

    # 將資料轉換為 DataFrame 並保存至 BytesIO
    output = io.BytesIO()
    df = pd.DataFrame(excel_data)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="資產負債表")
        writer.sheets["資產負債表"].sheet_state = 'visible'  # 設定工作表狀態為可見
    output.seek(0)  # 將指標移回開頭
    return output
