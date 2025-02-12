from flask import Blueprint, jsonify, request, redirect, session, url_for
import os
import requests
import jwt
import datetime
from mongoDB import find_line_user, create_line_user


# 建立 Blueprint
line_bp = Blueprint('line', __name__)

# LINE 商家參數
LINE_CHANNEL_ID = os.getenv('LINE_CHANNEL_ID')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CALLBACK_URI = os.getenv('LINE_CALLBACK_URI')

# 用於簽名 JWT 的密鑰
JWT_SECRET = os.getenv('JWT_SECRET')

# 生成 LINE 登入 URL
@line_bp.route('/login_url', methods=['GET'])
def line_login_url_generate():
    state = os.urandom(16).hex()  # 用於防止 CSRF 攻擊 ， 每次登入隨機生成16位元字串
    session['oauth_state'] = state
    login_url = (
        f"https://access.line.me/oauth2/v2.1/authorize?"
        f"response_type=code&"
        f"client_id={LINE_CHANNEL_ID}&"
        f"redirect_uri={LINE_CALLBACK_URI}&"
        f"state={state}&"
        f"scope=profile%20openid%20email"
    )
    return jsonify({"login_url": login_url})

# LINE 登入回調
@line_bp.route('/callback', methods=['GET'])
def line_callback():
    code = request.args.get("code")
    state = request.args.get("state")

    # 驗證 state 以防止 CSRF
    if state != session.get('oauth_state'):
        return jsonify({'error': 'State 不匹配'}), 400

    if not code:
        return jsonify({'error': '缺少授權碼'}), 400

    # 獲取 Access Token
    token_url = "https://api.line.me/oauth2/v2.1/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINE_CALLBACK_URI,
        "client_id": LINE_CHANNEL_ID,
        "client_secret": LINE_CHANNEL_SECRET,
    }

    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code != 200:
        return jsonify({'error': '獲取 Token 失敗', 'details': response.text}), 400

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return jsonify({'error': '獲取 Token 失敗'}), 400

    # 獲取用戶資料以取得 user_id
    profile_url = "https://api.line.me/v2/profile"
    profile_headers = {
        "Authorization": f"Bearer {access_token}"
    }
    profile_response = requests.get(profile_url, headers=profile_headers)
    if profile_response.status_code != 200:
        return jsonify({'error': '獲取用戶資料失敗', 'details': profile_response.text}), 400

    profile_data = profile_response.json()
    user_id = profile_data.get("userId")  # 根據 LINE API，userId 是大寫的

    if not user_id:
        return jsonify({'error': '無法獲取 user_id'}), 400

    # 返回用戶token和JWT
    jwt_token = jwt.encode({
        'access_token': access_token,
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # 設定過期時間
    }, JWT_SECRET, algorithm='HS256')

    # 檢查用戶是否首次登入
    user = find_line_user(user_id)
    if not user:
        # 首次登入，將 user_id 儲存至資料庫
        create_line_user(user_id, profile_data)  # 儲存用戶資料

    return jsonify({
        "access_token": access_token,
        "jwt_token": jwt_token  
    })

# 用戶資料
@line_bp.route('/profile', methods=['GET'])
def profile():
    # 從前端的 headers 中獲取 jwt_token
    jwt_token = request.headers.get('Authorization')
    if not jwt_token:
        return jsonify({'error': '缺少 JWT Token'}), 401

    try:
        # 驗證 JWT Token
        payload = jwt.decode(jwt_token, JWT_SECRET, algorithms=['HS256'])
        access_token = payload['access_token']  # 從 JWT 中獲取 access_token
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'JWT Token 已過期'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': '無效的 JWT Token'}), 401

    # 獲取用戶資料
    profile_url = "https://api.line.me/v2/profile"
    profile_headers = {
        "Authorization": f"Bearer {access_token}"
    }
    profile_response = requests.get(profile_url, headers=profile_headers)
    if profile_response.status_code != 200:
        return jsonify({'error': '獲取用戶資料失敗', 'details': profile_response.text}), 400

    profile_data = profile_response.json()

    return jsonify({
        "user_profile": profile_data
    })

