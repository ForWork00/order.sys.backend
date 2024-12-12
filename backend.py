import pymongo, os, stripe
client=pymongo.MongoClient("mongodb+srv://gary:gary1217@atlascluster.d0ukjd8.mongodb.net/")
db=client.backend
print("success")

from flask import Flask, request, jsonify, redirect, session
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

app = Flask(__name__)

@app.route("/sign_up", methods=["POST"])
def sign_up():
    email=request.form.get["email"]   #目前考慮email or LINE 連動登入
    password=request.form.get["password"]   #在研究之前先用個password先擋一下

    collection=db.user_id
    result=collection.find_one({
        "email":email
    })
    if result !=None:
        return redirect("/error?msg=信箱已經被註冊")
    collection.insert_one({
        "email":email,

    })
    return redirect("/success=註冊成功")


app.config["JWT_SECRET_KEY"] = "my_screct_key"  #待驗證
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
@app.route("/login", methods=["POST"])
def login():
    data=request.get_json()
    email = data.get('email')
    password = data.get('password')
    # email=request.form["email"]
    # password=request.form["password"]
    collection=db.user_id

    result=collection.find_one({
        "$and":[
            {"email":email},
            {"password":password}
        ]
    })
    # 驗證輸入
    if not email or not password:
        return jsonify({"message": "請輸入電子郵件和密碼"}), 400

    # 檢查用戶是否存在
    user = next((u for u in db.user_id if u['email'] == email), None)
    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({"message": "電子郵件不存在或密碼錯誤"}), 401
        
    # 生成 JWT
    token = create_access_token(identity={"id": user["id"], "email": user["email"]})
    return jsonify({"message": "登入成功", "token": token})
    # if result==None:
    #     return redirect("/error?msg=帳號密碼輸入錯誤")
    # session["email"]=result["email"]
    # return redirect("/success=登入成功")


@app.route("/protected")
def protected():
    current_user = get_jwt_identity()
    return jsonify({"message": "歡迎進入保護區域", "user": current_user})


@app.route("/signOut")
def signOut():
    del session["email"]
    return redirect("/success=完成登出")

@app.route("/")
def find():
    return redirect("/123")

stripe.api_key = "sk_test_51QBrlCByxTEIQfBXCEuz9gYnoZD53sOZR80clSPblmSW3MbtmEsM5C7AvFK4nEPyuKpRFiwCFXwhlQEwnvwwVlpV00dLCqWczC"
@app.route("/create_stripe_pay")
def create_stripe_pay():
    try:
        data = request.json
        amount = int(data["amount"]) *100

        payment_intent=stripe.PaymentIntent.create(
            amount=amount,
            currency="twd",
            payment_method="manual",
            confirm=True,
            return_url="http://localhost:4242/success"
        )
        return jsonify(payment_intent)    # 返回JSON
    except Exception as e:
        return jsonify(error=str(e)),403   # 如果創建支付時發生錯誤，返回錯誤訊息



if __name__ == "__main__":
    app.run(debug=True)
