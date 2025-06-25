
import os
import boto3
import json
from datetime import datetime
import time
from flask import Response
from models import respuesta_log
import re
import requests
from pytz import timezone, utc
from datetime import datetime, timedelta
import time
import logging
from botocore.config import Config

MIME_TYPE_JSON = "application/json"
ERROR_WSO2_SIN_USUARIO = "Error WSO2 - Sin usuario"
USUARIO_NO_REGISTRADO ="Usuario no registrado"
NOMBRE_NO_ENCONTRADO = "Nombre no encontrado"
LIMIT = 5000

# Configurar logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = boto3.client(
    'logs',
    region_name='us-east-1',
    config=Config(
        retries={
            'max_attempts': 3,
            'mode': 'adaptive'
        }
    ),
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
)

def sanitizar_filtro(texto):
    return re.sub(r'[^\w\s\-\.]', '', texto)

def get_all_logs(params):
    """
        Consulta eventos de logs en CloudWatch para un grupo de logs específico en un rango de tiempo
        
        Parameters
        ----------
        params : MultiDict
            parámetros que incluyen el nombre del grupo de logs, tiempo de inicio y tiempo de fin

        Returns
        -------
        json : lista de eventos de logs o información de errores
    """
    try:
        log_group_name = params.get('log_group_name', '/ecs/polux_crud_test')
        start_time = int(time.mktime(datetime(2024, 8, 1, 0, 0).timetuple()) * 1000)
        end_time = int(time.mktime(datetime(2024, 8, 2, 0, 0).timetuple()) * 1000)

        response = client.filter_log_events(
            logGroupName=log_group_name,
            startTime=start_time,
            endTime=end_time
        )

        events = [{"timestamp": event['timestamp'], "message": event['message']} for event in response.get('events', [])]
        
        if not events:
            return Response(json.dumps({'Status': 'No logs found', 'Code': '404', 'Data': []}), status=404, mimetype=MIME_TYPE_JSON)
        
        return Response(json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': events}), status=200, mimetype=MIME_TYPE_JSON)
    
    except Exception as e:
        return Response(json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}), status=500, mimetype=MIME_TYPE_JSON)

def construir_query(params):
    '''
    Genera dinámicamente una cadena de consulta (query string) para CloudWatch Logs Insights con base en los 
    parámetros recibidos como filtros (método HTTP, correo del usuario, etc.). Esta consulta se usará para obtener 
    registros de logs que coincidan con esos criterios.

    Parameters
    ----------
        filtro_busqueda: texto (por ejemplo GET, POST, etc.).
        filtro_email_user: correo del usuario que generó el log.
        limit: cantidad de registros a recuperar.

    Return
    ------
        Query en formato string para ejecutar en CloudWatch Logs.
    '''
    filtro_busqueda = re.escape(params["filterPattern"])
    filtro_email_user = re.escape(params["emailUser"])
    limit = int(params.get("limit", LIMIT))

    if filtro_busqueda and filtro_email_user:
        return f"""
        fields @timestamp, @message
        | filter @message like /{filtro_busqueda}/ 
        and @message like /middleware/
        and @message like /{filtro_email_user}/
        | sort @timestamp desc
        | limit 5
        """
    elif filtro_busqueda:
        return f"""
        fields @timestamp, @message
        | filter @message like /{filtro_busqueda}/
        and @message like /middleware/
        | sort @timestamp desc
        | limit 5
        """
    else:
        raise ValueError("El parámetro del método HTTP o el correo del usuario son obligatorios.")

def convertir_tiempo_a_utc(start_str, end_str, timezone_str='America/Bogota'):
    '''
    Convierte una fecha y hora en formato local (por ejemplo, hora de Bogotá) al formato UTC requerido por AWS CloudWatch. 
    Esto es necesario porque CloudWatch Logs opera en UTC.

    Parameters
    ----------
        datetime en hora local (ej. "2025-04-12 00:00").
        Zona horaria local (America/Bogota).

    Return
    ------
        Timestamp en formato UTC (epoch seconds) para consultas en AWS.
    '''
    try:
        datetime.strptime(start_str, "%Y-%m-%d %H:%M")
        datetime.strptime(end_str, "%Y-%m-%d %H:%M")
    except ValueError as e:
        raise ValueError(f"Formato de fecha inválido. Use 'YYYY-MM-DD HH:MM'. Error: {str(e)}")
    local_tz = timezone(timezone_str)
    start = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
    end = datetime.strptime(end_str, "%Y-%m-%d %H:%M")
    return int(local_tz.localize(start).astimezone(utc).timestamp()), int(local_tz.localize(end).astimezone(utc).timestamp())

def ejecutar_query_cloudwatch(query_string, log_group, start_time, end_time):
    '''
    Lanza una consulta a CloudWatch Logs Insights y espera hasta obtener el resultado.
    Es una función bloqueante (usa while) que consulta periódicamente si el resultado está listo.

    Parameters
    ----------
        client: cliente AWS Boto3 para CloudWatch Logs.
        query_string: string generado previamente con filtros.
        log_group: nombre del grupo de logs.
        start_time y end_time: tiempo en formato UTC (epoch seconds).

    Return
    ------
        Diccionario con los resultados de la query (status, results, etc.).
    '''
    try:
        # 1. Imprimir la query completa para depuración
        '''
        logger.info("\n" + "="*50)
        logger.info("QUERY QUE SE ENVÍA A AWS CLOUDWATCH:")
        logger.info(query_string)
        logger.info("="*50 + "\n")
        
        # 2. Imprimir metadatos de la consulta
        logger.info(f"Grupo de logs: {log_group}")
        logger.info(f"Rango de tiempo: {start_time} a {end_time}")
        
        '''
        # 3. Ejecutar la consulta normalmente
        response = client.start_query(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            queryString=query_string,
        )
        '''
        logger.info("Query iniciada en CloudWatch", extra={
            'query_id': response['queryId'],
            'status': 'started'
        })
        '''
        query_id = response['queryId']
        print(f"ID de consulta en AWS: {query_id}")
        
        while True:
            result = client.get_query_results(queryId=query_id)
            '''
            logger.info("\n" + "="*50)
            logger.info("RESULTADO!!!!!!!!!!!!!!!:")
            logger.info(result)
            logger.info("="*50 + "\n")
            '''
            if result['status'] in ['Complete', 'Failed', 'Cancelled']:
                return result
    except Exception as e:
        print(f"\nERROR AL EJECUTAR QUERY:\n{query_string}\nERROR: {str(e)}\n")
        raise

def procesar_logs(results):
    '''
    Transforma los logs crudos obtenidos desde CloudWatch en objetos estructurados (RespuestaLog).
    Extrae y limpia datos del mensaje del log, enriquece con información del usuario (nombre, documento, rol)
    y construye el objeto final.

    Parameters
    ----------
        Resultado de logs (lista de logs crudos de AWS).
        Funciones auxiliares: extract_log_data, buscar_user_rol, buscar_nombre_user, etc.

    Return
    ------
        Lista de objetos estructurados (RespuestaLog) listos para enviar al frontend o API.
    '''
    eventos = []
    for log in results:
        try:
            message = next(item['value'] for item in log if item['field'] == '@message')
            extracted_data = extract_log_data(message)

            fecha = extracted_data.get("fecha", "")
            fecha_convertida = ""
            try:
                fecha_convertida = datetime.strptime(fecha, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            usuario_log = extracted_data.get("usuario", "").strip()
            if usuario_log not in ["N/A", "Error", "Error WSO2", ERROR_WSO2_SIN_USUARIO, ""]:
                usuario_log += "@udistrital.edu.co"
            else:
                usuario_log = ERROR_WSO2_SIN_USUARIO

            if usuario_log != ERROR_WSO2_SIN_USUARIO:
                resultado = buscar_user_rol(usuario_log)
                if USUARIO_NO_REGISTRADO in resultado:
                    rol = "Rol no encontrado"
                    doc = "Documento no encontrado"
                    nombre = NOMBRE_NO_ENCONTRADO
                elif "error" in resultado:
                    rol = doc = nombre = "Error"
                else:
                    rol = resultado.get("roles")
                    doc = resultado.get("documento")
                    nombre = buscar_nombre_user(doc)
            else:
                rol = "Rol no encontrado"
                doc = "Documento no encontrado"
                nombre = NOMBRE_NO_ENCONTRADO

            log_obj = respuesta_log.RespuestaLog(
                tipo_log=extracted_data.get("tipo_log"),
                fecha=fecha_convertida,
                rol_responsable=usuario_log,
                nombre_responsable=nombre,
                documento_responsable=doc,
                direccion_accion=extracted_data.get("direccionAccion", "N/A"),
                rol=rol,
                apis_consumen=extracted_data.get("apiConsumen", "N/A"),
                peticion_realizada=extract_log_json(
                    extracted_data.get("endpoint"),
                    extracted_data.get("api"),
                    extracted_data.get("metodo"),
                    usuario_log,
                    extracted_data.get("data")
                ),
                evento_bd=reemplazar_valores_log(extracted_data.get("metodo"), extracted_data.get("sql_orm")),
                tipo_error="N/A",
                mensaje_error=message
            )
            eventos.append(log_obj)
        except Exception as e:
            print(f"Error procesando log: {e}")
    return eventos

def paginar_eventos(events, page, limit):
    '''
    Realiza una paginación en memoria sobre una lista de logs ya procesados. Extrae solo el conjunto de logs correspondientes a la página solicitada.

    Parameters
    ----------
        eventos: lista completa de logs.
        page: número de página actual.
        limit: número de registros por página.

    Return
    ------
        Sublista de logs correspondiente a la página (eventos[start:end]).
    '''
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paged_logs = events
    total_pages = (len(events) + limit - 1) // limit
    return paged_logs, total_pages

def get_one_log(params):
    """
        Consulta un solo evento de logs en CloudWatch para un grupo de logs específico con filtros adicionales.

        Parameters
        ----------
        params : MultiDict
            Parámetros que incluyen:
            - logGroupName (str): Nombre del grupo de logs.
            - logStreamNames (list): Lista de streams dentro del grupo de logs.
            - startTime (str): Tiempo de inicio (formato: 'YYYY-MM-DD HH:MM').
            - endTime (str): Tiempo de fin (formato: 'YYYY-MM-DD HH:MM').
            - filterPattern (str): Patrón para filtrar los logs.
            - limit (int): Límite de eventos a devolver.

        Returns
        -------
        json : Evento de log o información de error.
    """
    try:
        limit = int(params.get("limit"))
        page = int(params.get("page"))
        print("\nPAGINACION!!!!!!!!!!!!!!!:")
        print(f"Página: {page}, Límite: {limit}")
        entorno_api = 'prod' if params['environmentApi'] == 'PRODUCTION' else 'test'
        log_group = f"/ecs/{params['logGroupName']}_{entorno_api}"
        query_string = construir_query(params)
        start_time, end_time = convertir_tiempo_a_utc(params['startTime'], params['endTime'])
        result = ejecutar_query_cloudwatch(query_string, log_group, start_time, end_time)

        if result['status'] == 'Complete' and result['results']:
            eventos = procesar_logs(result['results'])
            
            paged_logs, total_pages = paginar_eventos(eventos, page, limit)
            return Response(
                json.dumps({
                    'Status': 'Successful request',
                    'Code': '200',
                    'Data': [vars(log) for log in paged_logs],
                    'Pagination': {
                        'page': page,
                        'limit': limit,
                        'total': len(eventos),
                        'pages': total_pages
                    }
                }),
                status=200,
                mimetype=MIME_TYPE_JSON
            )

        return Response(
            json.dumps({'Status': 'No logs found or query failed', 'Code': '404', 'Data': []}),
            status=404,
            mimetype=MIME_TYPE_JSON
        )

    except Exception as e:
        return Response(
            json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}),
            status=500,
            mimetype=MIME_TYPE_JSON
        )
    
def extraer_error(log_string):
    """
    Procesa una cadena de log y retorna tipoError y mensajeError.
    Si no hay error en el log, retorna "N/A" para ambos valores.
    """
    tipo_error = "N/A"
    mensaje_error = "N/A"

    # Extraer la parte JSON del log
    json_start = log_string.find("{", log_string.find("data: {"))
    json_end = log_string.rfind("}}") + 2  # Último }} para cerrar JSON correctamente

    if json_start != -1 and json_end != -1:
        log_data_string = log_string[json_start:json_end]

        # Verificar si hay una llave adicional y corregirla
        try:
            log_data = json.loads(log_data_string)
        except json.JSONDecodeError:
            # Si falla, intentamos quitar la última llave y volver a parsear
            last_curly_index = log_data_string.rfind("}")
            log_data_string = log_data_string[:last_curly_index]
            log_data = json.loads(log_data_string)

        # Extraer datos del JSON
        if log_data.get("json", {}).get("Success") is False:
            status = log_data["json"].get("Status", "N/A")
            data_error = log_data["json"].get("Data", "N/A")
            endpoint = log_data["json"].get("Message", "N/A")

            # Interpretar el tipo de error
            if status == "500":
                tipo_error = "500 Internal Server Error"
            elif status == "400":
                tipo_error = "400 Bad Request"
            else:
                tipo_error = status

            # Formatear el mensaje de error
            mensaje_error = (
                f"Mensaje de error: {data_error}\n"
                f"Endpoint: {endpoint}\n"
                f"Tipo de error: {tipo_error}"
            )

    return tipo_error, mensaje_error

def extract_log_data(log_entry):
    """
    Extrae información clave del mensaje del log usando expresiones regulares.

    Parameters
    ----------
    message : str
        El mensaje del log.

    Returns
    -------
    dict
        Diccionario con los datos extraídos.
    """
    patterns = {
        "apiConsumen": r"app_name:\s([^\s,]+)",
        "api": r"host:\s([^\s,]+)",
        "endpoint": r"end_point:\s([^\s,]+)",
        "metodo": r"method:\s([^\s,]+)",
        "fecha": r"date:\s([^\s,]+)",
        "direccionAccion": r"ip_user:\s([^\s,]+)",
        "user_agent": r"user_agent:\s([^\s,]+)",
        "usuario": r"\b, user:\s([^\s,]+)",
        "data": r"data:\s({.*})", 
        "tipo_log": r"\[([a-zA-Z0-9\._-]+)(?=\.\w+:)",
        "sql_orm": r"sql_orm:\s\{(.*?)\},\s+ip_user:"
    }

    extracted_data = {}
    clean_log = re.sub(r"\x1b\[[0-9;]*m", "", log_entry)

    for key, pattern in patterns.items():
        match = re.search(pattern, clean_log)
        if match:
            value = match.group(1)
            if key == "data":
                try:
                    extracted_data[key] = json.loads(value)
                except json.JSONDecodeError:
                    extracted_data[key] = value  
            else:
                extracted_data[key] = value

    return extracted_data

def extract_log_json(endpoint,api,metodo,usuario,data_json):
    data = {}
    data["endpoint"] = endpoint
    data["api"] = api
    data["metodo"] = metodo
    data["usuario"] = usuario
    data["data"] = data_json
    json_result = json.dumps(data, indent=4)
    return json_result

  

def buscar_user_rol(user_email):
    """
    Envía un método POST a la URL especificada con la información en formato JSON.

    Args:
        user_email (str): El correo electrónico del usuario que se enviará en el JSON.

    Returns:
        dict: La respuesta del servidor en formato JSON, o un error en caso de falla.
    """
    url = f"{os.environ['API_AUDITORIA_MID']}/v1/token/userRol"
    headers = {"Content-Type": MIME_TYPE_JSON}
    
    payload = {"user": user_email}
    
    try:    
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()  

        if response.status_code == 400 and "System" in response_data and "Error" in response_data["System"]:
            return {USUARIO_NO_REGISTRADO}
        else:
            response.raise_for_status() 

            roles_a_excluir = ["Internal/everyone"]
            filtered_roles = [role for role in response_data.get("role", []) if role not in roles_a_excluir]

            return {"roles": ", ".join(filtered_roles), "documento": response_data.get("documento")}
    
    except requests.exceptions.RequestException:
        return {USUARIO_NO_REGISTRADO} 

def buscar_nombre_user(documento):
    url = f"{os.environ['API_TERCEROS_CRUD']}/v1/datos_identificacion?query=numero:{documento}"
    headers = {"Content-Type": MIME_TYPE_JSON}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            nombre_completo = data[0].get("TerceroId", {}).get("NombreCompleto", NOMBRE_NO_ENCONTRADO)
            return nombre_completo
        else:
            return NOMBRE_NO_ENCONTRADO
    except requests.exceptions.RequestException as e:
        return {"error": str(e)} 

def reemplazar_valores_log(metodo,log):
    """
    Procesa un log, extrae los valores de una consulta SQL y los reemplaza en su lugar correspondiente.
    
    Args:
        log (str): Parte del log con la consulta SQL y los valores a reemplazar.
        
    Returns:
        str: Consulta SQL con los valores reemplazados.
    """
    if metodo.upper() == "POST":
        patron = r'\[(.*?)\] - (.+)'
        match = re.search(patron, log)
        print('POST')
        print(match)
        if match:
            consulta = match.group(1)
            valores = match.group(2).split(", ")

            for i, valor in enumerate(valores, start=1):
                consulta = consulta.replace(f"${i}", valor.strip())

            return consulta
        else:
            return "El formato del log POST no es válido: " + log
        
    elif metodo.upper() == "PUT":
        patron = r'\[(.*?)\] - (.+)'
        match = re.search(patron, log)
        print('PUT')
        print(match)
        if match:
            consulta = match.group(1)
            valores = re.findall(r'`([^`]*)`', match.group(2))

            for i, valor in enumerate(valores, start=1):
                consulta = consulta.replace(f"${i}", valor.strip())
            return consulta
        else:
            return "El formato del log PUT no es válido: " + log
        
    elif metodo.upper() == "GET":
        patron = r'\[(.*?)\] - (.+)'
        match = re.search(patron, log)
        if match:
            consulta = match.group(1)
            valores = re.findall(r'`([^`]*)`', match.group(2))

            for i, valor in enumerate(valores, start=1):
                consulta = consulta.replace(f"${i}", valor.strip())
            return consulta
        else:
            return "El formato del log GET no es válido: " + log
        
    elif metodo.upper() == "DELETE":
        patron = r'\[(.*?)\] - (.+)'
        match = re.search(patron, log)
        if match:
            consulta = match.group(1)
            valores = re.findall(r'`([^`]*)`', match.group(2))

            for i, valor in enumerate(valores, start=1):
                consulta = consulta.replace(f"${i}", valor.strip())
            return consulta
        else:
            return "El formato del log DELETE no es válido: " + log
    else:
        return

def construir_count_query(params):
    """Construye y loguea la query de conteo"""
    query_parts = ["fields @timestamp", "| filter @message like /middleware/"]
    
    if params.get('tipo_log'):
        tipo_log_escaped = re.escape(params['tipo_log'])
        query_parts.append(f'| filter @message like /{tipo_log_escaped}/')
        print(f"Filtro por tipo_log: {params['tipo_log']}")
    
    if params.get('codigoResponsable'):
        usuario_escaped = re.escape(params['codigoResponsable'])
        query_parts.append(f'| filter @message like /{usuario_escaped}/')
        print(f"Filtro por usuario: {params['codigoResponsable']}")
    
    query_parts.append("| stats count() as total")
    query = "\n".join(query_parts)
    
    print("\nQUERY DE CONTEO CONSTRUIDA:")
    print(query)
    
    return query

def construir_data_query(params, page, limit):
    """Construye y loguea la query de datos con paginación adecuada"""
    query_parts = ["fields @timestamp, @message", "| filter @message like /middleware/"]
    
    if params.get('tipo_log'):
        tipo_log_escaped = re.escape(params['tipo_log'])
        query_parts.append(f'| filter @message like /{tipo_log_escaped}/')
    
    if params.get('codigoResponsable'):
        usuario_escaped = re.escape(params['codigoResponsable'])
        query_parts.append(f'| filter @message like /{usuario_escaped}/')
    
    # Paginación correcta en CloudWatch Insights
    query_parts.extend([
        "| sort @timestamp desc",
        f"| limit {limit}",
    ])
    
    query = "\n".join(query_parts)
    '''
    logger.info("\nQUERY DE DATOS CONSTRUIDA:")
    logger.info(query)
    logger.info(f"Página: {page}, Límite: {limit}")
    '''
    
    return query

def get_filtered_logs(params):
    """Obtiene logs filtrados con paginación real desde CloudWatch
    
    Args:
        params (dict): Parámetros de filtrado y paginación
        
    Returns:
        Response: Respuesta Flask con los logs y metadatos de paginación
    """
    try:
        # Validar parámetros requeridos
        required_params = ['nombreApi', 'entornoApi', 'fechaInicio', 'horaInicio', 'fechaFin', 'horaFin']
        for param in required_params:
            if param not in params:
                return Response(
                    json.dumps({
                        'Status': 'Bad Request', 
                        'Code': '400',
                        'Error': f"Falta el parámetro requerido: {param}"
                    }),
                    status=400,
                    mimetype=MIME_TYPE_JSON
                )
        
        # Configurar paginación
        page = max(1, int(params.get('page', params.get('pagina', 1))))
        limit = min(max(1, int(params.get('limit', params.get('limite', 100)))), 10000)
        
        # Determinar entorno y grupo de logs
        entorno_api = 'prod' if params['entornoApi'].upper() == 'PRODUCTION' else 'test'
        log_group = f"/ecs/{params['nombreApi']}_{entorno_api}"
        
        # Convertir tiempos a UTC
        start_time, end_time = convertir_tiempo_a_utc(
            f"{params['fechaInicio']} {params['horaInicio']}",
            f"{params['fechaFin']} {params['horaFin']}"
        )
        
        # 1. Obtener datos paginados
        data_query = construir_data_query(params, page, limit)
        data_result = ejecutar_query_cloudwatch(data_query, log_group, start_time, end_time)
        
        # 2. Obtener conteo total para paginación
        count_query = construir_count_query(params)
        count_result = ejecutar_query_cloudwatch(count_query, log_group, start_time, end_time)
        
        # Procesar resultados
        if data_result['status'] == 'Complete' and data_result['results']:
            eventos = procesar_logs(data_result['results'])
            eventos_filtrados = aplicar_filtros_adicionales(eventos, params)
            
            # Obtener total de registros
            if count_result['status'] == 'Complete' and count_result['results']:
                total_registros = int(count_result['results'][0][0]['value'])
            else:
                total_registros = len(eventos_filtrados)
            
            return Response(
                json.dumps({
                    'Status': 'Successful request',
                    'Code': '200',
                    'Data': [vars(log) for log in eventos_filtrados],
                    'Pagination': {
                        'pagina': page,
                        'limite': limit,
                        'total': total_registros,
                        'paginas': (total_registros + limit - 1) // limit
                    }
                }),
                status=200,
                mimetype=MIME_TYPE_JSON
            )
        else:
            return Response(
                json.dumps({
                    'Status': 'No logs found',
                    'Code': '404',
                    'Data': [],
                    'Pagination': {
                        'pagina': page,
                        'limite': limit,
                        'total': 0,
                        'paginas': 0
                    }
                }),
                status=404,
                mimetype=MIME_TYPE_JSON
            )
            
    except ValueError as e:
        return Response(
            json.dumps({
                'Status': 'Bad Request', 
                'Code': '400',
                'Error': f"Parámetros inválidos: {str(e)}"
            }),
            status=400,
            mimetype=MIME_TYPE_JSON
        )
    except Exception as e:
        import traceback
        print(f"Error en get_filtered_logs: {str(e)}")
        print(traceback.format_exc())
        
        return Response(
            json.dumps({
                'Status': 'Internal Error',
                'Code': '500',
                'Error': str(e),
                'Details': traceback.format_exc() if os.environ.get('FLASK_ENV') == 'development' else None
            }),
            status=500,
            mimetype=MIME_TYPE_JSON
        )

def get_filtered_logs2(params):
    try:
        # Configuración básica
        page = int(params.get('pagina', 1))
        limit = int(params.get('limite', 100))
        entorno_api = 'prod' if params['entornoApi'].upper() == 'PRODUCTION' else 'test'
        log_group = f"/ecs/{params['nombreApi']}_{entorno_api}"
        
        # 1. Primero obtener los logs sin filtros adicionales para diagnóstico
        query = construir_data_query(params, page, limit)
        start_time, end_time = convertir_tiempo_a_utc(
            f"{params['fechaInicio']} {params['horaInicio']}",
            f"{params['fechaFin']} {params['horaFin']}"
        )
        
        result = ejecutar_query_cloudwatch(query, log_group, start_time, end_time)
        
        # Agregar logs de depuración
        print("\n=== RESULTADO CRUDO DE AWS ===")
        print(f"Estado: {result.get('status')}")
        print(f"Número de resultados: {len(result.get('results', []))}")
        
        if result['status'] == 'Complete' and result['results']:
            eventos = procesar_logs(result['results'])
            
            print("\n=== EVENTOS PROCESADOS ===")
            print(f"Número de eventos: {len(eventos)}")
            if eventos:
                print("Primer evento:", eventos[0])
            
            # Aplicar filtros (comentar temporalmente para diagnóstico)
            eventos_filtrados = aplicar_filtros_adicionales(eventos, params)
            
            print("\n=== EVENTOS FILTRADOS ===")
            print(f"Número de eventos filtrados: {len(eventos_filtrados)}")
            
            # Obtener el total de registros
            total_query = construir_count_query(params)
            total_result = ejecutar_query_cloudwatch(total_query, log_group, start_time, end_time)
            total_registros = int(total_result['results'][0][0]['value']) if total_result['status'] == 'Complete' else len(eventos)
            
            return Response(
                json.dumps({
                    'Status': 'Successful request',
                    'Code': '200',
                    'Data': [vars(log) for log in eventos_filtrados],
                    'Pagination': {
                        'pagina': page,
                        'limite': limit,
                        'total': total_registros,
                        'paginas': (total_registros + limit - 1) // limit
                    }
                }),
                status=200,
                mimetype=MIME_TYPE_JSON
            )
        
        return Response(
            json.dumps({
                'Status': 'No logs found',
                'Code': '404',
                'Data': [],
                'Pagination': {
                    'pagina': page,
                    'limite': limit,
                    'total': 0,
                    'paginas': 0
                }
            }),
            status=404,
            mimetype=MIME_TYPE_JSON
        )
        
    except Exception as e:
        print(f"\n=== ERROR EN get_filtered_logs ===")
        print(f"Tipo de error: {type(e)}")
        print(f"Mensaje: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        
        return Response(
            json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}),
            status=500,
            mimetype=MIME_TYPE_JSON
        )

def aplicar_filtros_adicionales(eventos, params):
    """Versión modificada para diagnóstico"""
    if not eventos:
        print("\n=== ADVERTENCIA: eventos vacíos antes de filtrar ===")
        return []
    
    filtered = eventos
    
    print("\n=== PARÁMETROS DE FILTRADO ===")
    print(f"Params recibidos: {params}")
    
    # Filtrar por método si está especificado
    if params.get('tipo_log'):
        print(f"\nFiltrando por tipo_log: {params['tipo_log']}")
        filtered = [log for log in filtered 
                   if params['tipo_log'].lower() in log.tipo_log.lower()]
        print(f"Registros después de filtrar por tipo_log: {len(filtered)}")
    
    # Filtrar por API si está especificado
    if params.get('api'):
        print(f"\nFiltrando por api: {params['api']}")
        filtered = [log for log in filtered 
                   if params['api'].lower() in log.peticion_realizada.lower()]
        print(f"Registros después de filtrar por api: {len(filtered)}")
    
    # Filtrar por endpoint si está especificado
    if params.get('endpoint'):
        print(f"\nFiltrando por endpoint: {params['endpoint']}")
        filtered = [log for log in filtered 
                   if params['endpoint'].lower() in log.peticion_realizada.lower()]
        print(f"Registros después de filtrar por endpoint: {len(filtered)}")
    
    # Filtrar por IP si está especificado
    if params.get('ip'):
        print(f"\nFiltrando por ip: {params['ip']}")
        filtered = [log for log in filtered 
                   if params['ip'] == log.direccion_accion]
        print(f"Registros después de filtrar por ip: {len(filtered)}")
    
    return filtered