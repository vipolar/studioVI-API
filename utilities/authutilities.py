from flask_jwt_extended import create_access_token, create_refresh_token, set_access_cookies, set_refresh_cookies
from flask import make_response, jsonify
from models import User
import datetime

def generate_token(user: User, fresh: bool = False, response_message: str = "Authentication successful!"):
    if user.confirmed is False:
        return make_response(jsonify({"message": "Immediate password change is required!"}), 202)

    access_token = create_access_token(identity=user.id, additional_claims={"username": user.username, "role": user.role, "scopes": user.scopes}, fresh=fresh, expires_delta=datetime.timedelta(minutes=15))
    refresh_token = create_refresh_token(identity=user.id, expires_delta=datetime.timedelta(days=7))

    response = jsonify({
        "message": response_message,
        "user": user.username
    })
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response

def invalidate_token(response_message: str = "Logged out successfully!"):
    response = make_response(jsonify({"message": response_message}), 200)    
    response.set_cookie("access_token", "", expires=0, httponly=True, secure=True)
    response.set_cookie("refresh_token", "", expires=0, httponly=True, secure=True)
    return response
