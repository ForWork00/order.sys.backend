import uuid, stripe, os

from flask import jsonify, request
from dotenv import load_dotenv
load_dotenv()

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
