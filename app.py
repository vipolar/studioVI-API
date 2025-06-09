from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
from utilities.authutilities import generate_token, invalidate_token
from utilities.decorators import authentication_required
from flask import Flask, request, jsonify
from models import db, User, bcrypt
from routes import api_blueprint
from globals import components
from flask_cors import CORS
import logging

app = Flask(__name__)
app.config.from_object("config.Config")
app.register_blueprint(api_blueprint)
jwtmg = JWTManager(app)
bcrypt.init_app(app)
db.init_app(app)
CORS(app, supports_credentials=True, origins=["http://localhost:5173"])


@app.route("/login", methods=["POST"])
def login():
    """Authenticates a user and returns a JWT."""
    response = {}

    try:
        data = request.json
        if not data or not data.get("username") or not data.get("password"):
            raise ValueError("Username and password required")

        user = User.query.filter_by(username=data["username"]).first()
        if not user or not user.check_password(data["password"]):
            raise PermissionError("Invalid credentials")
        
        response = generate_token(user, fresh=True, response_message="Logged into the Workstation successfully!")
    except PermissionError as e:
        return jsonify({"error": f"Failed to authenticate user: {str(e)}"}), 401
    except Exception as e:
        return jsonify({"error": f"Failed to authenticate user: {str(e)}"}), 500

    return response

@app.route("/register", methods=["POST"])
@authentication_required(accepted_roles="admin")
def register():
    """Registers a new user."""
    new_user = {}

    try:
        data = request.json

        if not data or not data.get("username") or not data.get("password"):
            raise ValueError("Username and password required")

        if User.query.filter_by(username=data["username"]).first():
            raise ValueError("Username is already taken")
        
        if data.get("role") and data.get("role") not in app.config["JWT_AVAILABLE_ROLES"]:
            raise ValueError("Invalid role provided")
        
        if data.get("scopes"):
            if isinstance(data.get("scopes"), list):
                for scope in data["scopes"]:
                    if scope not in app.config["JWT_AVAILABLE_SCOPES"]:
                        raise ValueError(f"Invalid scope provided: {scope}")
            else:
                raise ValueError("Scopes must be provided as a list")

        new_user = User(username=data["username"], role=data.get("role", app.config["JWT_DEFAULT_ROLE"]))
        new_user.set_scopes(data.get("scopes", app.config["JWT_DEFAULT_SCOPES"]))
        new_user.set_password(data["password"])
        new_user.confirmed = False
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        return jsonify({"error": f"Failed to register a new user: {str(e)}"}), 400

    return jsonify({"message": "User registered successfully", "user": new_user.to_dict()}), 201

@app.route("/reset_password", methods=["POST"])
def reset_password():
    """Resets the password for a user."""

    try:
        data = request.json
        if not data or not data.get("username") or not data.get("old_password") or not data.get("new_password"):
            raise ValueError("Username, old password, and new password required")

        user = User.query.filter_by(username=data["username"]).first()
        if not user or not user.check_password(data["old_password"]):
            raise PermissionError("Invalid credentials")
        
        user.set_password(data["new_password"])
        user.confirmed = True
        db.session.commit()
    except PermissionError as e:
        return jsonify({"error": f"Failed to reset password: {str(e)}"}), 401
    except Exception as e:
        return jsonify({"error": f"Failed to reset password: {str(e)}"}), 500

    return jsonify({"message": "Password reset successfully!"}), 200

@app.route('/refresh_token', methods=['POST'])
@authentication_required(refresh=True)
def refresh_token():
    """Refreshes the JWT token."""
    response = {}

    try:
        response = generate_token(get_jwt_identity(), fresh=False, response_message="Authentication token refreshed successfully!")
    except Exception as e:
        return jsonify({"error": f"Failed to refresh token: {str(e)}"}), 500
    
    return response

@app.route("/logout", methods=["POST"])
def logout(): 
    """Logs out a user by invalidating the JWT."""
    response = {}

    try:   
        response = invalidate_token(response_message="Logged out successfully!")
    except Exception as e:
        return jsonify({"error": f"Failed to log out: {str(e)}"}), 500

    return response

# will have to go into the services.py file
@app.route("/auth", methods=["GET"])
def validate_token():
    try:
        verify_jwt_in_request()
        user = get_jwt_identity()
        return jsonify({"user": user}), 200
    except Exception as e:
        return jsonify({"error": "Unauthorized"}), 401

with app.app_context():
    logging.basicConfig(
        level=logging.DEBUG, format='[%(asctime)s] [%(levelname)s] %(module)s: %(message)s'
    )

    logging.info("Initializing the application...")
    logging.info("Loading components...") 
    components.scan_all()
    logging.info("Initalizing DB...") 
    db.create_all()

    default_admin_username = app.config["APP_ADMIN_USERNAME"]
    default_admin_password = app.config["APP_ADMIN_PASSWORD"]

    if not User.query.filter_by(username=default_admin_username).first():
        logging.info(f"Creating default admin user: {default_admin_username}")
        admin_user = User(username=default_admin_username, role="admin")
        admin_user.set_scopes(app.config["JWT_AVAILABLE_SCOPES"])
        admin_user.set_password(default_admin_password)
        admin_user.confirmed = True
        db.session.add(admin_user)
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)