import json
import pandas as pd
from flask import jsonify
from dotenv import load_dotenv
from mongoDB import get_accounting, get_AccountHistory  # 導入資料庫集合
import os

load_dotenv()

 #現金流量表
def Cash_Flow_Statement():
    """
    依據 IFRS 標準將科目分類為 營業、投資、籌資活動現金流。
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
                second_code = second.get("account_code", "")
                third_grades = second.get("third_grade", [])

                for third in third_grades:
                    fourth_grades = third.get("fourth_grade", [])

                    for fourth in fourth_grades:
                        account_code = fourth.get("account_code", "")
                        account_name = fourth.get("account", "")
                        opening_balance = fourth.get("opening_balance", 0) or 0
                        end_balance = fourth.get("end_balance", 0) or 0
                        net_change = end_balance - opening_balance
                        if opening_balance == 0 and end_balance == 0:
                            continue

                        # if not account_code or not account_code[0].isdigit():
                        #     continue  # 忽略無效代碼

                        # **分類現金流量**
                        category = None
                        first_digit = account_code[0]

                        if first_digit == "1":  # 現金、銀行存款
                            category = "營業活動現金流量"
                        elif first_digit == "2":
                            if second_code.startswith(("21", "22")):  # 短期應付帳款、負債
                                category = "營業活動現金流量"
                            elif second_code.startswith(("23", "24", "25")):  # 應付公司債、長期負債
                                category = "籌資活動現金流量"
                        elif first_digit == "3":  # 股東權益 (股本、股利)
                            category = "籌資活動現金流量"
                        elif first_digit == "4":  # 營業收入
                            category = "營業活動現金流量"
                        elif first_digit == "5":  # 營業成本
                            category = "營業活動現金流量"
                        elif first_digit == "6":  # 營業費用
                            category = "營業活動現金流量"
                        elif first_digit == "7":
                            if second_code.startswith(("71", "72", "73", "74")):  # 業外收入
                                category = "投資活動現金流量"
                            elif second_code.startswith(("75", "76", "77", "78")):  # 業外支出
                                category = "投資活動現金流量"
                        elif first_digit == "8":  # 所得稅
                            category = "營業活動現金流量"

                        if category:
                            # **將數據存入對應分類**
                            cash_flow_statement[category].append({
                                "科目": account_name,
                                "代碼": account_code,
                                "期初餘額": opening_balance,
                                "期末餘額": end_balance,
                                "現金流量變動": net_change
                            })
                            
                            cash_flow_statement["現金及約當現金增減淨額"] += net_change

        return cash_flow_statement
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
#導出現金流量表Excel
def save_cash_flow_statement():
    """
    生成現金流量表，並存為 Excel，確保正確分類「營業活動」與「籌資活動」。
    """
    try:
        result = Cash_Flow_Statement()
        save_to_excel(result)
        return jsonify({"message": "現金流量表已保存", "file": "cash_flow_statement.xlsx"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
def save_to_excel(data, file_name="現金流量表.xlsx"):
    excel_data = []
    for category, entries in data.items():
        if category == "現金及約當現金增減淨額":
            continue
        for entry in entries:
            excel_data.append({
                "分類": category,
                "科目": entry["科目"],
                "代碼": entry["代碼"],
                "期初餘額": entry["期初餘額"],
                "期末餘額": entry["期末餘額"],
                "現金流量變動": entry["現金流量變動"]
            })
    df = pd.DataFrame(excel_data)
    df.to_excel(file_name, index=False, encoding="utf-8")