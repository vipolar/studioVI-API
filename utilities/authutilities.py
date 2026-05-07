from flask_jwt_extended import create_access_token, create_refresh_token, set_access_cookies, set_refresh_cookies
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask import make_response, jsonify
from typing import Any, List, Union
from functools import wraps
from models import User
import datetime

def authentication_required(accepted_roles: Union[str, List[str]] = None, unaccepted_roles: Union[str, List[str]] = None, required_scopes: Union[str, List[str]] = None, refresh: bool = False) -> Any:
    """Decorator to restrict access based on roles and/or scopes."""
    def decorator(fn):
        @wraps(fn) # Yeaaaah!!!
        @jwt_required(refresh=refresh)
        def wrapper(*args, **kwargs):
            current_user = get_jwt_identity()
            if (accepted_roles is not None):
                if isinstance(accepted_roles, list):
                    for role in accepted_roles:
                        if current_user["role"] == role:
                            return fn(*args, **kwargs)
                elif isinstance(accepted_roles, str):
                    if current_user["role"] == accepted_roles:
                        return fn(*args, **kwargs)

                raise PermissionError("Unauthorized")
            if (required_scopes is not None):
                if isinstance(required_scopes, str):
                    required_scopes = [required_scopes]

                if set(required_scopes).issubset(current_user["scopes"]):
                    return fn(*args, **kwargs)

                raise PermissionError("Unauthorized")
        return wrapper
    return decorator

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
