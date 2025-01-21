import re, logging
from datetime import datetime
from bson import ObjectId
from flask import Flask, request, jsonify, send_file
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from mongoDB import get_user_collection, user_find, create_date_id, get_revenues, get_expenses, insert_expense, del_all_coll # 從 mongoDB.py 導入
from func import create_uuid, generate_trend_chart, export_to_excel, process_data, total
from Pay import stripe_pay


app = Flask(__name__)
collection=get_user_collection()
bcrypt=Bcrypt(app)
app.config["JWT_SECRET_KEY"] = "my_screct_key"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 86400   #24hr
app.config["JWT_BLACKLIST_ENABLED"] = True
app.config["JWT_BLACKLIST_TOKEN_CHECKS"] = ["access"]
jwt = JWTManager(app)
blacklist = set()

# 初始化限流 IP限制請求頻率
# limiter=Limiter(
#     get_remote_address,
#     app=app,
#     default_limits=["1 per minute"]
# )
def is_valid_email(email):
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"  #check email 格式是否正確
    return re.match(email_regex, email) is not None

def is_valid_birth(birth):
    if not re.match(r"^\d{8}$", birth):  #check birth格式、正確日期
        return False
    
    try:
        birth_date=datetime.strptime(birth, "%Y%m%d")
        if birth_date > datetime.now():
            return False
    except ValueError:
        return False
    return True


@app.route("/sign_up", methods=["POST"])
# @limiter.limit("1 per minute")
def sign_up():
    email=request.json.get("email")   #目前考慮email or LINE 連動登入
    password=request.json.get("password")
    birth=request.json.get("birth")

    if not email or not password or not birth:
        return jsonify({"error": "Missing fields"}), 400
    
    # 檢查信箱是否已經被註冊
    if collection.find_one({"email": email}):
        return jsonify({"error": "Email is already registered"}), 400
    
    if not is_valid_email(email):
        return jsonify({"error":"email format error"}), 400
    
    if not is_valid_birth(birth):
        return jsonify({"error":"birth format error is YYYYMMDD and not exceed today"}), 400
    
    #加密密碼
    hashed_password=bcrypt.generate_password_hash(password).decode("utf-8")
    
    uid=create_uuid()
    register_time=datetime.now()   # 註冊時間
    default_points=0   # 預設點數為0
    try:
        collection.insert_one({
            "_id":uid,
            "email":email,
            "password":hashed_password,
            "birth":birth,
            "register_time":register_time,
            "points":default_points
        })
        return jsonify({"_id":uid, "email":email, "message":"User created successfully"}), 201
    except Exception as e:
        return jsonify({"messag":"Created Fail"})

@app.route("/login", methods=["POST"])
def login():
    data=request.get_json()
    email = data.get('email')
    password = data.get('password')

    # 檢查用戶是否存在
    user = next((u for u in user_find() if u['email'] == email), None)
    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({"message": "電子郵件不存在或密碼錯誤"}), 401
        
    # 生成 JWT
    token = create_access_token(identity=user["email"])
    return jsonify({"message": "登入成功", "token": token}), 200
    


@app.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({"message": "測試確定帶入TOKEN登入", "user": current_user}), 200
    
@app.route("/logOut", methods=["POST"])
@jwt_required()
def logOut():
    jti=get_jwt()["jti"]
    blacklist.add(jti)
    return jsonify({"message":"Logout successful"}),200


@app.route("/create_stripe_pay", methods=["POST"])
def create_stripe_pay():
    return stripe_pay()


""" 取得用戶資訊 """
@app.route("/get_user/<user_id>")   # (DB中的_id)->以uuid 來抓取
def get_user(user_id):
    try:
        user=collection.find_one({"_id":user_id})
        if not user:
            return jsonify({"error":"User does not exist"}), 404
        
        register_time=user.get("register_time")
        if register_time:
            formatted_time=register_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_time="Unkown"
        
        return jsonify({
            "id": user["_id"],
            "email": user.get("email", "Unkown"),
            "register_time": formatted_time,
            "points": user.get("points", 0)  # 如果沒有 points 欄位，預設為 0
        })
    except Exception as e:
        return jsonify({"error":f"An error occurred: {str(e)}"}), 500
        

""" 點數加扣 """
@app.route("/update_points", methods=["POST"])
def update_points():
    try:
        data = request.json
        user_id = data.get("user_id")
        points = data.get("points")  # 加/扣的點數 (正數為加點，負數為扣點)

        user=collection.find_one({"_id":user_id})
        if not user:
            return jsonify({"error":"User does not exist"}), 404

        current_points = user.get("points", 0)   # 確保點數欄位存在

        new_points = current_points + points   # 計算新的點數
        if new_points < 0:
            return jsonify({"error": "Not enough points"}), 400

        collection.update_one(   # 更新用戶點數
            {"_id": user["_id"]},  # uuid 作為查詢條件
            {"$set": {"points": new_points}}
        )

        return jsonify({
            "message": "點數更新成功",
            "new_points": new_points
        }), 200
    except Exception as e:
        return jsonify({"error": f"發生錯誤: {str(e)}"}), 500



""" accounting use """
# @app.route("/api/revenues/add", methods=["POST"])   # 新增額外收入用api
# def add_revenues():
#     data=request.json
#     data["date"]=datetime.strptime(data["date"], "%Y-%m-%d")  #這邊要改成自動抓新增資料的時間
#     insert_revenue(data)
#     return jsonify({"message":"Add Successfully"}), 201

@app.route("/api/expenses/add", methods=["POST"])   # 新增支出api
def add_expenses():
    data=request.json
    date_prefix=datetime.now().strftime("%Y%m%d")
    data["_id"]=create_date_id(date_prefix)
    data["created_time"]=datetime.now()
    insert_expense(data)
    return jsonify({"message":"Add Successfully"}), 201
    


def serialize_document(doc):
    """將 MongoDB 文件中的 ObjectId 轉換為字符串"""
    return {key: str(value) if key == "_id" else value for key, value in doc.items()}

@app.route("/api/search/report", methods=["GET"])   # 搜尋收入支出報表&生成圖形報表
def get_report():
    start_date=request.args.get("start_date")
    end_date=request.args.get("end_date")
    chart=request.args.get("chart", "fales").lower()=="true"
    chart_type=request.args.get("chart_type", "line").lower()

    try:
        start=datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        end=datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({"error":"Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'"})

    revenues=[serialize_document(doc) for doc in get_revenues(start, end)]
    expenses=[serialize_document(doc) for doc in get_expenses(start, end)]

    total_revenue=total(revenues, "total_price")
    total_expense=total(expenses, "amount")
    
    if chart:
        try:
                # 生成折線圖
            img = generate_trend_chart(revenues, expenses, chart_type)
            return send_file(img, mimetype="image/png")
        except Exception as e:
            return jsonify({"error": f"Failed to generate chart: {str(e)}"}), 500
    
    revenue_data=[{"total_price": r["total_price"], "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M:%S")} for r in revenues]
    expense_data=[{"amount": e["amount"], "created_time": e["created_time"].strftime("%Y-%m-%d %H:%M:%S")} for e in expenses]
    
    return jsonify({
        "revenues": revenue_data,
        "expenses": expense_data,
        "total_revenue":total_revenue,
        "total_expense":total_expense
        })
    


@app.route("/api/report/export", methods=["GET"])  # 匯出excel
def export_report():
    try:
        start_date=request.args.get("start_date")
        end_date=request.args.get("end_date")
        start=datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        end=datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")

        revenues=get_revenues(start, end)
        expenses=get_expenses(start, end)
        output=export_to_excel(revenues, expenses)
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        as_attachment=True, download_name="report_xlsx")
    except Exception as e:
        logging.error(f"匯出報表發生錯誤:{e}")
        return jsonify({"error":str(e)}), 500


""" 工程用（使用前請再仔細確認） """
@app.route("/db/del_all_coll", methods=["DELETE"])   # 使用前請看mongoDB.py中的函式進行調整刪除內容
def delete_all_coll():
    try:
        delete_count=del_all_coll()
        return jsonify({
            "message":"Deleted successfully",
            "delete_count":delete_count
        }), 200
    except Exception as e:
        return jsonify({
            "message":"An error occurred while deleting",
            "error":str(e)
        }), 500

if __name__ == "__main__":
    app.run(debug=True, threaded=False)
