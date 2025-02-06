from flask import Blueprint, jsonify, request, redirect, session, url_for
import os
import requests

# 建立 Blueprint
line_bp = Blueprint('line', __name__)

# LINE 商家參數
LINE_CHANNEL_ID = os.getenv('LINE_CHANNEL_ID')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CALLBACK_URI = os.getenv('LINE_CALLBACK_URI')


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

    # 返回用戶token
    return jsonify({
        "access_token": access_token
    })

# 用戶資料頁面
@line_bp.route('/profile', methods=['GET'])
def profile():
    # 從前端的 headers 中獲取 access_token
    access_token = request.headers.get('Authorization')
    if not access_token:
        return jsonify({'error': '缺少 Access Token'}), 401

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

# 登出
@line_bp.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('line_login_url_generate'))

