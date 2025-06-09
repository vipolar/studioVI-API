from flask import Blueprint
from .services import services_blueprint
from .usage import usage_blueprint

api_blueprint = Blueprint('api', __name__)

api_blueprint.register_blueprint(services_blueprint, url_prefix='/services')
api_blueprint.register_blueprint(usage_blueprint, url_prefix='/usage')