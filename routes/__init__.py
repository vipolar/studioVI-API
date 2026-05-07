from flask import Blueprint
from .gages import gages_blueprint
from .models import models_blueprint
from .services import services_blueprint
#from .utilities import utilities_blueprint

api_blueprint = Blueprint('api', __name__)

api_blueprint.register_blueprint(gages_blueprint, url_prefix='/usage')
api_blueprint.register_blueprint(models_blueprint, url_prefix='/models')
api_blueprint.register_blueprint(services_blueprint, url_prefix='/services')
#api_blueprint.register_blueprint(utilities_blueprint, url_prefix='/utilities')