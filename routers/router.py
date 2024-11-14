from flask import Blueprint, request
from flask_restx import Api, Resource
from controllers import auditoria, healthCheck  
from flask_cors import CORS, cross_origin
from conf.conf import api_cors_config

def addRouting(app):
    app.register_blueprint(healthCheckController)
    app.register_blueprint(auditoriaController, url_prefix='/v1')


healthCheckController = Blueprint('healthCheckController', __name__, url_prefix='/v1')
CORS(healthCheckController)

@healthCheckController.route('/')
def _():
    return healthCheck.healthCheck(documentDoc)

auditoriaController = Blueprint('auditoriaController', __name__)
CORS(auditoriaController)
documentDoc = Api(auditoriaController, version='1.0', title='auditoria_mid', description='Api mid para la obtención de logs de AWS', doc="/swagger")

documentNamespaceController = documentDoc.namespace("auditoria", description="Consulta logs de AWS")

@documentNamespaceController.route('/', strict_slashes=False)
class documentGetAll(Resource):
    @documentDoc.doc(responses={
        200: 'Success',
        206: 'Partial Content',
        500: 'Server error',
        404: 'Not found',
        400: 'Bad request'
    })    
    @cross_origin(**api_cors_config)
    def get(self):
        """
            Consulta eventos de logs en AWS CloudWatch.

            Parameters
            ----------
            Ninguno

            Returns
            -------
            Response
                Respuesta con los logs consultados o error.
        """
        params = request.args  # Obtener parámetros de la URL
        return auditoria.getAll(params)