from flask_jwt_extended import jwt_required, get_jwt_identity
from typing import Any, Dict, List, Union
from functools import wraps
import logging

def authentication_required(accepted_roles: Union[str, List[str]] = None, unaccepted_roles: Union[str, List[str]] = None, required_scopes: Union[str, List[str]] = None, refresh: bool = False) -> Any:
    """Decorator to restrict access based on roles and/or scopes."""
    def decorator(fn):
        @wraps(fn) # Yeaaaah!!!
        #@jwt_required(refresh=refresh)
        def wrapper(*args, **kwargs):
            current_user = unaccepted_roles
         #   current_user = get_jwt_identity()
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