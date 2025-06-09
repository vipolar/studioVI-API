from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    password_hash = db.Column(db.String(128), nullable=False)
    username = db.Column(db.String(96), unique=True, nullable=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    role = db.Column(db.String(32), nullable=False, default="user")
    scopes = db.Column(db.String, nullable=False, default="")

    def set_scopes(self, scopes_list):
        self.scopes = ",".join(scopes_list)

    def get_scopes(self):
        return self.scopes.split(",") if self.scopes else []

    def set_password(self, password):
        """Hashes password and stores it."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Checks if provided password matches stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Returns user info (excluding password hash)."""
        return {"id": self.id, "username": self.username, "role": self.role, "scopes": self.get_scopes()}
