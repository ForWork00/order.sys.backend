from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import bcrypt, os
from dotenv import load_dotenv
from config import jwt_config
from mongoDB import backstage_user, blacklisted_tokens_collection, get_user_collection
from func import format_user_data
import json
load_dotenv()


collection=get_user_collection()

app=Flask(__name__)
app.config.from_object(jwt_config)
jwt=JWTManager(app)
blacklisted_tokens = set()

@app.route("/backstage/registers", methods=["POST"])
def register():
    data=request.json
    hashed_password=bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt())

    if backstage_user.find_one({"username":data["username"]}):
        return jsonify({"message":"Username already exists"}), 400
    
    new_user={
        "username":data["username"],
        "password":hashed_password.decode("utf-8"),
        "role":data.get("role", "user"),
        "permissions":data.get("permissions", {})
    }
    backstage_user.insert_one(new_user)
    return jsonify({"message":"User registered successfully!"}), 201


@app.route("/backstage/login", methods=["POST"])
def login():
    data=request.json
    user=backstage_user.find_one({"username": data["username"]})
    if user and bcrypt.checkpw(data["password"].encode("utf-8"), user["password"].encode("utf-8")):
        access_token=create_access_token(identity=json.dumps({
            "id":str(user["_id"]),
            "role":user["role"]
        }))
        return jsonify(access_token=access_token), 200
    return jsonify({"message":"Invalid credentials"}), 401



@app.route("/users", methods=["GET"])   #取得用者（管理最大權限使用）
@jwt_required()
def get_users():
    current_user=json.loads(get_jwt_identity())
    user=backstage_user.find_one({"_id":ObjectId(current_user["id"])})

    if user["role"] != "admin":
        return jsonify({"message":"Permission denied"}), 403
    
    users=backstage_user.find()
    result=[
        {"id":str(u["_id"]), "username":u["username"], "role":u["role"], "permissions":u["permissions"]}
        for u in users
    ]
    return jsonify(result), 200


@app.route("/update-permissions/<user_id>", methods=["PUT"])
@jwt_required()
def update_permissions(user_id):
    current_user=json.loads(get_jwt_identity())   # 確保identity是dict
    user=backstage_user.find_one({"_id":ObjectId(current_user["id"])})

    if user["role"] != "admin":
        return jsonify({"message":"Permission denied"}), 403
    
    data=request.json
    target_user=backstage_user.find_one({"_id":ObjectId(user_id)})
    if not target_user:
        return jsonify({"message":"User not found"}), 404
    
    backstage_user.update_one(
        {"_id":ObjectId(user_id)},
        {"$set":{"permissions":data["permissions"]}}
    )
    return jsonify({"message":"Permissions updated successfully"}), 200


@app.route("/get_user")   # 搜尋會員
def get_user():
    try:
        user_id=request.args.get("user_id")
        email=request.args.get("email")

        query={}

        if user_id:
            query["_id"]=user_id
        if email:
            query["email"]=email
        
        if query:
            user=collection.find_one(query)
            if not user:
                return jsonify({"error":"User does not exist"}), 404
            return jsonify(format_user_data(user)), 200
        else:
            users=collection.find()
            user_list=[format_user_data(user) for user in users]
            return jsonify(user_list), 200
    except Exception as e:
        return jsonify({"error":f"An error occurred: {str(e)}"}), 500
        


@jwt.token_in_blocklist_loader
def check_token_revoked(jwt_header, jwt_payload):
    return blacklisted_tokens_collection.find_one({"jti":jwt_payload["jti"]}) is not None   # 查詢是否在黑名單

@app.route("/backstage/logout", methods=["POST"])
@jwt_required()
def logout():
    jti=get_jwt()["jti"]
    blacklisted_tokens_collection.insert_one({"jti":jti})
    return jsonify({"message":"Logged out successfully"}), 200

if __name__ =="__main__":
    app.run(debug=True)

