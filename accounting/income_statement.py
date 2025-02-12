import json
import pandas as pd
from flask import jsonify
from dotenv import load_dotenv
from mongoDB import get_accounting, get_AccountHistory  # 導入資料庫集合
import os

load_dotenv()

def get_income_statement():
    try:
        get_accounting()
        get_AccountHistory()
        account_collection = get_accounting()
        data = list(account_collection.find())

        income_statement = {
            "營業總收入": 0,
            "營業總成本": 0,
            "毛利": 0,
            "營業利潤": 0,
            "利潤總額": 0,
            "淨利潤": 0,
            "其他綜合損益": 0,
            "全面收益總額": 0,
            "營業收入": [],
            "營業成本": [],
            "營業費用": [],
            "業外收入": [],
            "業外支出": [],
            "所得稅": []
        }

        for first_level in data:
            second_grades = first_level.get("second_grade", [])
            
            for second in second_grades:
                third_grades = second.get("third_grade", [])

                for third in third_grades:
                    fourth_grades = third.get("fourth_grade", [])

                    for fourth in fourth_grades:
                        account_name = fourth.get("account", "")
                        account_code = fourth.get("account_code", "")
                        opening_balance = fourth.get("opening_balance", 0) or 0
                        end_balance = fourth.get("end_balance", 0) or 0
                        if opening_balance == 0 and end_balance == 0:
                            continue

                        # **透過第一級代碼篩選**
                        first_digit = account_code[0]

                        if first_digit == "4":  # 營業收入
                            income_statement["營業總收入"] += end_balance
                            income_statement["營業收入"].append({
                                "科目": account_name,
                                "代碼": account_code,
                                "期末餘額": end_balance
                            })
                        elif first_digit == "5":  # 營業成本
                            income_statement["營業總成本"] += end_balance
                            income_statement["營業成本"].append({
                                "科目": account_name,
                                "代碼": account_code,
                                "期末餘額": end_balance
                            })
                        elif first_digit == "6":  # 營業費用
                            income_statement["營業費用"].append({
                                "科目": account_name,
                                "代碼": account_code,
                                "期末餘額": end_balance
                            })
                        elif first_digit == "7":  # 業外收入或業外支出
                            second_digit = account_code[1] if len(account_code) > 1 else ""
                            if second_digit in "1234":  # 71~74 屬於業外收入
                                income_statement["業外收入"].append({
                                    "科目": account_name,
                                    "代碼": account_code,
                                    "期末餘額": end_balance
                                })
                            elif second_digit in "5678":  # 75~78 屬於業外支出
                                income_statement["業外支出"].append({
                                    "科目": account_name,
                                    "代碼": account_code,
                                    "期末餘額": end_balance
                                })
                        elif first_digit == "8":  # 所得稅
                            income_statement["所得稅"].append({
                                "科目": account_name,
                                "代碼": account_code,
                                "期末餘額": end_balance
                            })
                        elif first_digit == "9":  # 其他綜合損益
                            income_statement["其他綜合損益"] += end_balance

        # **計算各項財務數據**
        income_statement["毛利"] = income_statement["營業總收入"] - income_statement["營業總成本"]
        income_statement["營業利潤"] = income_statement["毛利"] - sum(
            item["期末餘額"] for item in income_statement["營業費用"]
        )
        income_statement["利潤總額"] = income_statement["營業利潤"] + sum(
            item["期末餘額"] for item in income_statement["業外收入"]
        ) - sum(item["期末餘額"] for item in income_statement["業外支出"])
        income_statement["淨利潤"] = income_statement["利潤總額"] - sum(
            item["期末餘額"] for item in income_statement["所得稅"]
        )
        income_statement["全面收益總額"] = income_statement["淨利潤"] + income_statement["其他綜合損益"]

        return income_statement
    except Exception as e:
        return {"error": str(e)}



def save_income_statement():
    try:
        response = get_income_statement()
        
        if isinstance(response, tuple):  # 若為元組，表示有錯誤
            result, status_code = response
            if status_code != 200:
                return jsonify(result), status_code  
        else:
            result = response  

        if "error" in result:
            return jsonify(result), 500  

        #保存損益表至 Excel
        save_income_statement_to_excel(result)
        return jsonify({"message": "損益表已保存", "file": "損益表.xlsx"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def save_income_statement_to_excel(data, file_name="損益表.xlsx"):
    """
    將損益表資料存為 Excel 檔案，並移除每股收益計算。
    忽略期初與期末都為 0 的科目。
    """
    excel_data = []
    categories = ["營業收入", "業外收入", "營業成本", "營業費用", "業外支出", "所得稅"]

    # **將明細寫入 Excel**
    for category in categories:
        entries = data.get(category, [])
        for entry in entries:
            if entry.get("期末餘額", 0) != 0:  #忽略期末為 0 的項目
                excel_data.append({
                    "分類": category,
                    "科目": entry["科目"],
                    "代碼": entry["代碼"],
                    "期末餘額": entry["期末餘額"]
                })

    # **加入合計數據**
    summary_fields = ["營業總收入", "營業總成本", "營業利潤", "利潤總額", "淨利潤"]
    for field in summary_fields:
        if data[field] != 0:  # 忽略合計為 0 的項目
            excel_data.append({
                "分類": field,
                "科目": field,
                "代碼": "",
                "期末餘額": data[field]
            })

    # 轉換 DataFrame 並保存
    if excel_data:  # 確保不存入空檔案
        df = pd.DataFrame(excel_data)
        df.to_excel(file_name, index=False, encoding="utf-8")
