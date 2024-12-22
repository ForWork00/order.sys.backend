import os, stripe, re, time, subprocess
from datetime import datetime
from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from mongoDB import get_user_collection, user_find  # 從 mongoDB.py 導入
from func import create_uuid, stripe_pay


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
limiter=Limiter(
    get_remote_address,
    app=app,
    default_limits=["1 per minute"]
)
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
@app.route('/')
def home():
    return "Hello, World"

@app.route("/sign_up", methods=["POST"])
@limiter.limit("1 per minute")
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
    try:
        collection.insert_one({
            "_id":uid,
            "email":email,
            "password":hashed_password,
            "birth":birth
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

@app.route('/webhook', methods=['POST'])
def webhook():
    # 驗證私鑰
    secret = request.headers.get("X-Webhook-Secret")
    WEBHOOK_SECRET = os.getenv("TOKEN")
    USERNAME = os.getenv("USERNAME")
    
    if not WEBHOOK_SECRET or not USERNAME:
        return jsonify({"error": "Environment variables missing"}), 500

    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 403

    # 從GitHub上拉取main代碼
    try:
        project_dir = f"/home/{USERNAME}/order.sys.backend"  # 使用格式化字符串
        requirements_file = os.path.join(project_dir, "requirements.txt")
        reload_command = f"{USERNAME}.pythonanywhere.com"

        # Step 1: 拉取代碼
        subprocess.run(["git", "-C", project_dir, "pull"], check=True)

        # Step 2: 安裝依賴
        subprocess.run(["pip3", "install", "-r", requirements_file], check=True)


        return jsonify({"message": "Update successful!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
