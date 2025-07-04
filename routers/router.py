from flask import Blueprint, request
from flask_restx import Api, Resource
from controllers import auditoria, healthCheck  
from flask_cors import CORS, cross_origin
from conf.conf import api_cors_config
from models import model_params

def add_routing(app):
    app.register_blueprint(healthCheckController)
    app.register_blueprint(auditoriaController, url_prefix='/v1')

healthCheckController = Blueprint('healthCheckController', __name__, url_prefix='/v1')
CORS(healthCheckController)

@healthCheckController.route('/')
def _():
    return healthCheck.health_check(documentDoc)

auditoriaController = Blueprint('auditoriaController', __name__)
CORS(auditoriaController)

documentDoc = Api(auditoriaController, version='1.0', title='auditoria_mid', description='Api mid para la obtención de logs de AWS', doc="/swagger")
documentNamespaceController = documentDoc.namespace("auditoria", description="Consulta logs de AWS")

auditoria_params=model_params.define_parameters(documentDoc)

@documentNamespaceController.route('/', strict_slashes=False)
class document_get_all(Resource):
    @documentDoc.doc(responses={
        200: 'Success',
        206: 'Partial Content',
        400: 'Bad request',
        404: 'Not found',
        500: 'Server error'
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
        params = request.args  
        return auditoria.get_all(params)


@documentNamespaceController.route('/buscarLog', strict_slashes=False)
class FilterLogs(Resource):
    @documentDoc.doc(responses={
        200: 'Success',
        206: 'Partial Content',
        400: 'Bad request',
        404: 'Not found',
        500: 'Server error'
    }, body=auditoria_params['filtro_log_model'])  
    @documentNamespaceController.expect(auditoria_params['filtro_log_model'])  
    @cross_origin(**api_cors_config)
    def post(self):
        """
        Filtra los logs de AWS con base en parámetros específicos.

        Parameters
        ----------
        request : json
            Un JSON que contiene:
            - fechaInicio (str): Fecha de inicio en formato aaaa-mm-dd
            - horaInicio (str): Hora de inicio en formato hh:mm
            - fechaFin (str): Fecha de fin en formato aaaa-mm-dd
            - horaFin (str): Hora de fin en formato hh:mm
            - tipo_log (str): Tipo de log (GET, POST, PUT, etc.)
            - codigoResponsable (int): Código del responsable
            - rolResponsable (str): Rol del responsable

        Returns
        -------
        Response
            Respuesta con los logs filtrados en formato JSON.
        """
        params = request.json 
        return auditoria.post_buscar_log(params)

@documentNamespaceController.route('/buscarLogsFiltrados', strict_slashes=False)
class FilterLogsPaginated(Resource):
    @documentDoc.doc(responses={
        200: 'Success',
        400: 'Bad request',
        404: 'Not found',
        500: 'Server error'
    })
    @documentDoc.param('nombreApi', 'Nombre del API (ej: polux_crud)', required=True)
    @documentDoc.param('entornoApi', 'Entorno (SANDBOX, PRODUCTION, TEST)', required=True)
    @documentDoc.param('fechaInicio', 'Fecha de inicio (YYYY-MM-DD)', required=True)
    @documentDoc.param('horaInicio', 'Hora de inicio (HH:MM)', required=True)
    @documentDoc.param('fechaFin', 'Fecha de fin (YYYY-MM-DD)', required=True)
    @documentDoc.param('horaFin', 'Hora de fin (HH:MM)', required=True)
    @documentDoc.param('page', 'Número de página', default=1)
    @documentDoc.param('limit', 'Registros por página', default=10)
    @documentDoc.param('tipo_log', 'Método HTTP (GET, POST, PUT, DELETE)')
    @documentDoc.param('codigoResponsable', 'Email del usuario responsable')
    @documentDoc.param('api', 'API específica')
    @documentDoc.param('endpoint', 'Endpoint específico')
    @documentDoc.param('ip', 'Dirección IP')
    @cross_origin(**api_cors_config)
    def get(self):
        """
        Filtra y pagina logs de AWS con base en parámetros en la URL.
        
        Permite búsqueda incremental con paginación para mejor performance.
        """
        params = request.args
        return auditoria.get_logs_filtrados(params)