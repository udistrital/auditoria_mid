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
def health_check():
    return healthCheck.health_check(documentDoc)

auditoriaController = Blueprint('auditoriaController', __name__)
CORS(auditoriaController)

documentDoc = Api(auditoriaController, version='1.0', title='auditoria_mid', description='Api mid para la obtención de logs de AWS', doc="/swagger")
documentNamespaceController = documentDoc.namespace("auditoria", description="Consulta logs de AWS")

auditoria_params=model_params.define_parameters(documentDoc)

@documentNamespaceController.route('/', strict_slashes=False)
class DocumentGetAll(Resource):
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
    },
    body=auditoria_params['filtro_log_model'])
    @cross_origin(**api_cors_config)
    def post(self):
        """
        Filtra y pagina logs de AWS con base en parámetros específicos.

        Permite búsqueda avanzada con múltiples filtros y paginación para mejor performance.
        Los logs pueden ser procesados completamente (standard) o mínimamente (flexible) según el typeSearch.

        Ejemplo de parámetros requeridos:
        ```json
        {
            "fechaInicio":1751371200,
            "horaInicio":"07:00",
            "fechaFin":1751461200,
            "horaFin":"08:00",
            "tipo_log":"GET",
            "codigoResponsable":"",
            "palabraClave":"",
            "nombreApi":"polux_crud",
            "entornoApi":"SANDBOX",
            "typeSearch":"flexible",
            "pagina":1,
            "limite":5000
        }
        ```
        La respuesta para tipo de búsqueda 'Estandar' incluye metadatos de paginación y los logs encontrados.
        Cada log contiene:
        - Tipo de log
        - Fecha y hora
        - Usuario responsable
        - Nombre del responsable
        - Documento del responsable
        - Rol del responsable
        - Dirección IP
        - API consumida
        - Petición realizada (endpoint, método, datos)
        - Evento en base de datos (si aplica)
        - Tipo de error (si aplica)
        - Mensaje de error (si aplica)

        La respuesta para  tipo de búsqueda 'Flexible' incluye páginación, pero los datos en crudo,es decir el mensaje de error sin procesar
        ya que el procesamiento de la información se hace directamente desde el front.

        ```json
        {
            "Status": "Successful request",
            "Code": "200",
            "Data": [
                "2025/07/01 12:00:21.715 [I] [middleware.go:163] {"
                "    app_name: polux_crud,"
                "    host: xxx.xx.x.xxx:xxxxx,"
                "    end_point: /,"
                "    method: GET,"
                "    date: 2025-07-01T12:00:21Z,"
                "    sql_orm: {...},"
                "    ip_user: xxx.xx.x.xxx,"
                "    user_agent: ELB-HealthChecker/2.0,"
                "    user: Error WSO2,"
                "    data: {\"RouterPattern\":\"/\"}"
                "}"
                ...
            ],
            "Pagination": {
                "pagina": 1,
                "limite": 20,
                "total registros": 20,
                "paginas": 1
            }
        }
        """
        params = request.json
        return auditoria.get_logs_filtrados(params)
