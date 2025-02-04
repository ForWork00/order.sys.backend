from flask import Blueprint, request, jsonify
import importlib.util
from datetime import datetime
import hashlib
import urllib.parse
import requests
import os

# 建立 Blueprint
payment_bp = Blueprint('payment', __name__)


# 建立信用卡付款訂單
@payment_bp.route('/create_payment/credit', methods=['GET', 'POST'])
def create_payment_credit():
    try:
        # 從請求中獲取參數
        merchant_trade_no = request.args.get('MerchantTradeNo', type=str)
        total_amount = request.args.get('TotalAmount', type=int)
        item_name = request.args.get('ItemName', type=str)

        # 檢查必填參數
        if merchant_trade_no is None or total_amount is None or item_name is None:
            return jsonify({'error': 'MerchantTradeNo, TotalAmount, ItemName, are required'}), 400

        # 導入 ECPay SDK
        spec = importlib.util.spec_from_file_location(
            "ecpay_payment_sdk",
            "./ecpay_payment_sdk.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        order_params = {
            'MerchantTradeNo': merchant_trade_no, # 前端傳入的MerchantTradeNo
            'StoreID': '',
            'MerchantTradeDate': datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            'PaymentType': 'aio',
            'TotalAmount': total_amount, # 前端傳入的TotalAmount
            'TradeDesc': '訂單測試',
            'ItemName': item_name, # 前端傳入的ItemName
            'ReturnURL': f"{os.getenv('ORDER_SYS_URL')}/payment/return_url",
            'ChoosePayment': 'Credit',
            'ClientBackURL': f"{os.getenv('ORDER_SYS_URL')}/payment/client_back_url",
            'OrderResultURL': f"{os.getenv('ORDER_SYS_URL')}/payment/order_result_url",
            'NeedExtraPaidInfo': 'Y',
            'EncryptType': 1,
        }

        ecpay_payment_sdk = module.ECPayPaymentSdk(
            MerchantID=os.getenv('ECPay_MerchantID'),
            HashKey=os.getenv('ECPay_HashKey'),
            HashIV=os.getenv('ECPay_HashIV')
        )

        final_order_params = ecpay_payment_sdk.create_order(order_params)
        action_url = 'https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5'
        html = ecpay_payment_sdk.gen_html_post_form(action_url, final_order_params)

        return html

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 建立Apple Pay付款訂單
@payment_bp.route('/create_payment/apple_pay', methods=['GET', 'POST'])
def create_payment_apple_pay():
    try:
        # 從請求中獲取參數
        merchant_trade_no = request.args.get('MerchantTradeNo', type=str)
        total_amount = request.args.get('TotalAmount', type=int)
        item_name = request.args.get('ItemName', type=str)

        # 檢查必填參數
        if merchant_trade_no is None or total_amount is None or item_name is None:
            return jsonify({'error': 'MerchantTradeNo, TotalAmount, ItemName, are required'}), 400

        # 導入 ECPay SDK
        spec = importlib.util.spec_from_file_location(
            "ecpay_payment_sdk",
            "./ecpay_payment_sdk.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        order_params = {
            'MerchantTradeNo': merchant_trade_no, # 前端傳入的MerchantTradeNo
            'StoreID': '',
            'MerchantTradeDate': datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            'PaymentType': 'aio',
            'TotalAmount': total_amount, # 前端傳入的TotalAmount
            'TradeDesc': '訂單測試',
            'ItemName': item_name, # 前端傳入的ItemName
            'ReturnURL': f"{os.getenv('ORDER_SYS_URL')}/payment/return_url",
            'ChoosePayment': 'Apple Pay',
            'ClientBackURL': f"{os.getenv('ORDER_SYS_URL')}/payment/client_back_url",
            'OrderResultURL': f"{os.getenv('ORDER_SYS_URL')}/payment/order_result_url",
            'NeedExtraPaidInfo': 'Y',
            'EncryptType': 1,
        }

        ecpay_payment_sdk = module.ECPayPaymentSdk(
            MerchantID=os.getenv('ECPay_MerchantID'),
            HashKey=os.getenv('ECPay_HashKey'),
            HashIV=os.getenv('ECPay_HashIV')
        )

        final_order_params = ecpay_payment_sdk.create_order(order_params)
        action_url = 'https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5'
        html = ecpay_payment_sdk.gen_html_post_form(action_url, final_order_params)

        return html

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 處理callback
@payment_bp.route('/return_url', methods=['POST'])
def return_url():
    try:
        # 獲取回調數據
        callback_data = request.form.to_dict()

        # 處理回調數據
        # 例如：更新訂單狀態、記錄交易資訊等
        print("Callback data:", callback_data)

        # 回應綠界
        return '1|OK'

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 尚未實作
@payment_bp.route('/client_back_url', methods=['GET', 'POST'])
def client_back_url():
    return 'Client Back URL'

# 處理訂單結果 (前端顯示)
@payment_bp.route('/order_result_url', methods=['GET', 'POST'])
def order_result_url():
    try:
        # 獲取回調數據
        result_data = request.form.to_dict()
        print("Received result data:", result_data)  # 添加日誌

        if result_data.get('RtnCode') == '1':
            # 交易成功
            message = "交易成功！"

            # 取得訂單ID
            order_id = result_data.get('MerchantTradeNo')  

            # 發送 PATCH 請求更新訂單狀態
            response = requests.patch(f"{os.getenv('ORDER_SYS_URL')}/orders/{order_id}", json={"status": "completed"}) 

            # 若更新失敗，則回傳失敗訊息
            if response.status_code != 200:
                print(f"Failed to update order status: {response.json()}")
        else:
            # 交易失敗
            message = f"交易失敗，原因：{result_data.get('RtnMsg')}"

        # 返回結果頁面
        return f"""
        <html>
            <head><title>交易結果</title></head>
            <body>
                <h1>{message}</h1>
                <p>交易編號：{result_data.get('MerchantTradeNo')}</p>
                <p>交易金額：{result_data.get('TradeAmt')}</p>
            </body>
        </html>
        """

    except Exception as e:
        print("Error occurred:", str(e))  # 添加日誌
        return f"An error occurred: {str(e)}", 500

def verify_check_mac_value(data):
    
    # 排除 CheckMacValue 本身
    if 'CheckMacValue' in data:
        check_mac_value = data.pop('CheckMacValue')
    else:
        return False

    # 排序參數
    sorted_data = sorted(data.items())

    # 組合字串
    raw = 'HashKey=pwFHCqoQZGmho4w6&' + '&'.join(f'{k}={v}' for k, v in sorted_data) + '&HashIV=EkRm7iFT261dpevs'

    # 進行 URL encode
    raw = urllib.parse.quote_plus(raw).lower()

    # 計算 SHA256
    calculated_mac = hashlib.sha256(raw.encode('utf-8')).hexdigest().upper()

    # 比較計算結果與回傳的 CheckMacValue
    return calculated_mac == check_mac_value 