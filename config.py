from typing import Dict, List
import os

class Config:
    JWT_DEFAULT_ROLE: str = "user"
    JWT_COOKIE_SECURE: bool = False
    JWT_COOKIE_SAMESITE: str = "Lax"
    JWT_COOKIE_CSRF_PROTECT: bool = False
    JWT_DEFAULT_SCOPES: List[str] = ["read"]
    JWT_TOKEN_LOCATION: List[str] = ["cookies"]
    JWT_AVAILABLE_ROLES: List[str] = ["admin", "user"]
    JWT_AVAILABLE_SCOPES: List[str] = ["read", "write", "delete"]
    JWT_DEFAULT_ROLE_SCOPES: Dict[str, List[str]] = {
        "admin": ["read", "write", "delete"],
        "user": ["read"]
    }
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your_jwt_secret")  # Change this too!
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your_secret_key")  # Change this!
    JWT_BLACKLIST_TOKEN_CHECKS: List[str] = ['access', 'refresh']
    JWT_REFRESH_TOKEN_EXPIRES: int = 604800  # 1 week
    JWT_ACCESS_TOKEN_EXPIRES: int = 3600  # 1 hour
    JWT_BLACKLIST_ENABLED: bool = True   

    APP_ADMIN_USERNAME: str = os.getenv("APP_ADMIN_USERNAME", "admin")
    APP_ADMIN_PASSWORD: str = os.getenv("APP_ADMIN_PASSWORD", "password")
    
    PROCESS_GRACEFUL_SHUTDOWN_TIMEOUT: int = os.getenv("PROCESS_GRACEFUL_SHUTDOWN_TIMEOUT", 5)
    COMPONENTS_LOGS_DIRECTORY: str = os.getenv("COMPONENTS_LOGS_DIRECTORY", "instance/logs")
    
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///database.db"
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    STUDIO_BASE_DIR: str = os.getenv("STUDIO_BASE_DIR", None)
    METADATA_IDENTIFIER: str = os.getenv("METADATA_IDENTIFIER", "id")
    METADATA_FILE_NAME: str = os.getenv("METADATA_FILE_NAME", ".metadata.json")
    METADATA_ACCEPTED_TYPES: List[str] = os.getenv("METADATA_ACCEPTED_TYPES", ["model", "service"])
    
