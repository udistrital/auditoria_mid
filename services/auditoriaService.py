import os
import boto3
import json
from datetime import datetime
from flask import Response
from models import respuesta_log
import re
import requests
from pytz import timezone, utc
from datetime import datetime
from botocore.config import Config
import time
from threading import Thread
from threading import Event
from functools import wraps

MIME_TYPE_JSON = "application/json"
STATUS_BAD_REQUEST = "Bad Request"
STATUS_SUCCESS = "Successful request"
PATRON = re.compile(r"\[(.*?)\] - (.+)", re.UNICODE)
# Expresión regular precompilada para mejor rendimiento
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
ERROR_WSO2_SIN_USUARIO = "Error WSO2 - Sin usuario"
USUARIO_NO_REGISTRADO = "Usuario no registrado"
NOMBRE_NO_ENCONTRADO = "Nombre no encontrado"
LIMIT = 10000
REQUIRE_PARAMS = ["nombreApi","entornoApi","fechaInicio","horaInicio","fechaFin","horaFin",]
# Tiempo máximo de ejecución para regex (en segundos)
REGEX_TIMEOUT = 2  # Ajusta según necesidades
MAX_TEXT_LENGTH = 10_000  # Longitud máxima de texto para evitar DoS

def safe_regex(timeout):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            if time.time() - start_time > timeout:
                raise ValueError("Regex operation timed out")
            return result
        return wrapper
    return decorator
client = boto3.client(
    "logs",
    region_name="us-east-1",
    config=Config(
        retries={"max_attempts": 3, "mode": "adaptive"},
        connect_timeout=5,
        read_timeout=8,
    ),
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)

def validate_params(params):
    for param in REQUIRE_PARAMS:
        if param not in params:
            return Response(
                json.dumps(
                    {
                        "Status": STATUS_BAD_REQUEST,
                        "Code": "400",
                        "Error": f"Falta el parámetro requerido: {param}",
                    }
                ),
                status=400,
                mimetype=MIME_TYPE_JSON,
            )

def calcular_paginacion(params):
    # Obtener página con valor por defecto 1 y asegurar que sea mínimo 1
    page = max(1, int(params.get("page", params.get("pagina", 1))))
    # Obtener límite con valor por defecto 100, asegurar que esté entre 1 y 10000
    limit = min(max(1, int(params.get("limit", params.get("limite", 100)))), 10000)
    # Calcular offset
    offset = (page - 1) * limit
    # Retornar los tres valores
    return page, limit, offset

def determiar_entorno(params):
    entorno_api = "prod" if params["entornoApi"].upper() == "PRODUCTION" else "test"
    log_group = f"/ecs/{params['nombreApi']}_{entorno_api}"
    return log_group

def formato_rango_fecha(params):
    start_time, end_time = convertir_tiempo_a_utc(
        f"{params['fechaInicio']} {params['horaInicio']}",
        f"{params['fechaFin']} {params['horaFin']}",
    )
    return start_time, end_time

def procesamiento_respuesta(data,total_registros,page,limit):
    return Response(
            json.dumps(
                {
                    "Status": STATUS_SUCCESS,
                    "Code": "200",
                    "Data": data,
                    "Pagination": {
                        "pagina": page,
                        "limite": total_registros if limit < LIMIT else LIMIT,
                        "total registros": total_registros,
                        "paginas": (total_registros + limit - 1) // limit,
                    },
                }
            ),
            status=200,
            mimetype=MIME_TYPE_JSON,
        )

def no_logs_found(page,limit):
    return Response(
                json.dumps(
                    {
                        "Status": "No logs found",
                        "Code": "404",
                        "Data": [],
                        "Pagination": {
                            "pagina": page,
                            "limite": limit,
                            "total": 0,
                            "paginas": 0,
                        },
                    }
                ),
                status=404,
                mimetype=MIME_TYPE_JSON,
            )
def bad_request(e):
    return Response(
        json.dumps(
            {
                "Status": STATUS_BAD_REQUEST,
                "Code": "400",
                "Error": f"Parámetros inválidos: {str(e)}",
            }
        ),
        status=400,
        mimetype=MIME_TYPE_JSON,
    )
def internal_error(e):
    import traceback
    print(f"Error en get_filtered_logs: {str(e)}")
    print(traceback.format_exc())

    return Response(
        json.dumps(
            {
                "Status": "Internal Error",
                "Code": "500",
                "Error": str(e),
                "Details": (
                    traceback.format_exc()
                    if os.environ.get("FLASK_ENV") == "development"
                    else None
                ),
            }
        ),
        status=500,
        mimetype=MIME_TYPE_JSON,
    )

def get_processed_filtered_logs(params):
    """Obtiene logs filtrados con paginación real desde CloudWatch

    Args:
        params (dict): Parámetros de filtrado y paginación

    Returns:
        Response: Respuesta Flask con los logs y metadatos de paginación
    """
    try:
        # Validar parámetros requeridos
        validate_params(params)
        # Configurar paginación
        page, limit, offset = calcular_paginacion(params)

        # Determinar entorno y grupo de logs
        log_group = determiar_entorno(params)

        # Convertir tiempos a UTC
        start_time, end_time = formato_rango_fecha(params)
        # 1. Obtener datos paginados
        data_query = construir_data_query(params, offset, limit)
        data_result = ejecutar_query_cloudwatch(
            data_query, log_group, start_time, end_time
        )
        # Procesar resultados
        if data_result["status"] == "Complete" and data_result["results"]:
            # Obtener total de registros
            total_registros = len(data_result["results"])
            data = [limpiar_caracteres_ansi(log[1]["value"]) for log in data_result["results"]]
            return procesamiento_respuesta(data,total_registros,page,limit)
        else:
            return no_logs_found(page,limit)
    except ValueError as e:
        return bad_request(e)
    except Exception as e:
        return internal_error(e)

def get_filtered_logs(params):
    """Obtiene logs filtrados con paginación real desde CloudWatch

    Args:
        params (dict): Parámetros de filtrado y paginación

    Returns:
        Response: Respuesta Flask con los logs y metadatos de paginación
    """
    try:
        # Validar parámetros requeridos
        validate_params(params)
        # Configurar paginación
        page, limit, offset = calcular_paginacion(params)

        # Determinar entorno y grupo de logs
        log_group = determiar_entorno(params)

        # Convertir tiempos a UTC
        start_time, end_time = convertir_tiempo_a_utc(
            f"{params['fechaInicio']} {params['horaInicio']}",
            f"{params['fechaFin']} {params['horaFin']}"
        )#formato_rango_fecha(params)

        # 1. Obtener datos paginados
        data_query = construir_data_query(params, offset, limit)
        data_result = ejecutar_query_cloudwatch(
            data_query, log_group, start_time, end_time
        )
        # Procesar resultados
        if data_result["status"] == "Complete" and data_result["results"]:
            eventos = procesar_logs(data_result["results"])
            eventos_filtrados = aplicar_filtros_adicionales(eventos, params)
            total_registros = len(eventos_filtrados)
            # Obtener total de registros
            data = [vars(log) for log in eventos_filtrados]
            return procesamiento_respuesta(data,total_registros,page,limit)
        else:
            return no_logs_found(page,limit)

    except ValueError as e:
        return bad_request(e)
    except Exception as e:
        return internal_error(e)

def convertir_tiempo_a_utc(start_str, end_str, timezone_str="America/Bogota"):
    """
    Convierte una fecha y hora en formato local (por ejemplo, hora de Bogotá) al formato UTC requerido por AWS CloudWatch.
    Esto es necesario porque CloudWatch Logs opera en UTC.

    Parameters
    ----------
        datetime en hora local (ej. "2025-04-12 00:00").
        Zona horaria local (America/Bogota).

    Return
    ------
        Timestamp en formato UTC (epoch seconds) para consultas en AWS.
    """
    date_format = "%Y-%m-%d %H:%M"
    try:
        datetime.strptime(start_str, date_format)
        datetime.strptime(end_str, date_format)
    except ValueError as e:
        raise ValueError(
            f"Formato de fecha inválido. Use 'YYYY-MM-DD HH:MM'. Error: {str(e)}"
        )
    local_tz = timezone(timezone_str)
    start = datetime.strptime(start_str, date_format)
    end = datetime.strptime(end_str, date_format)
    return int(local_tz.localize(start).astimezone(utc).timestamp()), int(
        local_tz.localize(end).astimezone(utc).timestamp()
    )

def ejecutar_query_cloudwatch(query_string, log_group, start_time, end_time):
    """
    Lanza una consulta a CloudWatch Logs Insights con timeout de 60 segundos.
    Muestra contador en tiempo real y se detiene exactamente al llegar al límite.
    """
    def print_timer(stop_event, start_time, timeout):
        """Hilo que imprime el tiempo y verifica timeout"""
        while not stop_event.is_set():
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                stop_event.set()
                break
            time.sleep(0.1)

    def should_stop_processing(result, stop_event):
        """Determina si el procesamiento debe detenerse"""
        if isinstance(result, dict) and len(result.get('results', [])) >= 10000:
            return True
        if result.get("status") in ["Complete", "Failed", "Cancelled"]:
            return True
        return False

    try:
        timeout = 60
        stop_event = Event()
        start_total_time = time.time()

        timer_thread = Thread(target=print_timer, args=(stop_event, start_total_time, timeout))
        timer_thread.daemon = True
        timer_thread.start()

        response = client.start_query(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            queryString=query_string,
        )
        query_id = response["queryId"]

        result = []
        while not stop_event.is_set():
            result = client.get_query_results(queryId=query_id)
            
            if should_stop_processing(result, stop_event):
                stop_event.set()
                break

            time.sleep(2)

        if isinstance(result, dict):
            result["status"] = "Complete" if result.get("status") != "Failed" else "Failed"

        return result

    except Exception as e:
        stop_event.set()
        print(f"\nError en la consulta: {str(e)}")
        raise
    finally:
        stop_event.set()
        if 'timer_thread' in locals():
            timer_thread.join(timeout=1)

def construir_data_query(params, page, limit):
    """Construye y loguea la query de datos con paginación adecuada"""
    filtro_busqueda = re.escape(params["filterPattern"])
    filtro_email_user = re.escape(params["emailUser"])
    filtro_palabra_clave = re.escape(params.get('palabraClave'))
    query_parts = ["fields @timestamp, @message", "| filter @message like /middleware/"]
    if filtro_busqueda and filtro_email_user:
        query_parts.append(f"| filter @message like /{filtro_email_user}/")
    if filtro_busqueda:
        query_parts.append(f"| filter @message like /{filtro_busqueda}/")
    if re.escape(params.get('api')):
        query_parts.append(f"| filter @message like /{params['api']}/")
    if re.escape(params.get('endpoint')):
        query_parts.append(f"| filter @message like /{params['endpoint']}/")
    if re.escape(params.get('ip')):
        query_parts.append(f"| filter @message like /{params['ip']}/")
    if filtro_palabra_clave:
        query_parts.append(f"| filter @message like /{filtro_palabra_clave}/")
    # Paginación correcta en CloudWatch Insights
    query_parts.extend(["| sort @timestamp desc",f"| limit {LIMIT}",])

    query = "\n".join(query_parts)
    return query

def procesar_logs(results):
    """
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
    """
    eventos = []
    for log in results:
        try:
            message = next(item["value"] for item in log if item["field"] == "@message")
            extracted_data = extract_log_data(message)

            fecha_convertida = convert_fecha(extracted_data.get("fecha", ""))
            usuario_log = process_usuario_log(extracted_data.get("usuario", "").strip())
            nombre, doc, rol = get_user_info(usuario_log)

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
                    extracted_data.get("data"),
                ),
                evento_bd=reemplazar_valores_log(
                    extracted_data.get("metodo"), extracted_data.get("sql_orm")
                ),
                tipo_error="N/A",
                mensaje_error=limpiar_caracteres_ansi(message),
            )
            eventos.append(log_obj)
        except Exception as e:
            print(f"Error procesando log: {e}")
    return eventos

def convert_fecha(fecha):
    """Convert date format if possible"""
    try:
        return datetime.strptime(fecha, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""

def process_usuario_log(usuario_log):
    """Process usuario log and add domain if needed"""
    if usuario_log not in ["N/A", "Error", "Error WSO2", ERROR_WSO2_SIN_USUARIO, ""]:
        return usuario_log + "@udistrital.edu.co"
    return ERROR_WSO2_SIN_USUARIO

def get_user_info(usuario_log):
    """Get user information (nombre, documento, rol)"""
    if usuario_log == ERROR_WSO2_SIN_USUARIO:
        return NOMBRE_NO_ENCONTRADO, "Documento no encontrado", "Rol no encontrado"

    resultado = buscar_user_rol(usuario_log)
    if USUARIO_NO_REGISTRADO in resultado:
        return NOMBRE_NO_ENCONTRADO, "Documento no encontrado", "Rol no encontrado"
    elif "error" in resultado:
        return "Error", "Error", "Error"

    rol = resultado.get("roles")
    doc = resultado.get("documento")
    nombre = buscar_nombre_user(doc)
    return nombre, doc, rol

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
        "sql_orm": r"sql_orm:\s\{(.*?)\},\s+ip_user:",
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

def buscar_nombre_user(documento):
    url = f"{os.environ['API_TERCEROS_CRUD']}/v1/datos_identificacion?query=numero:{documento}"
    headers = {"Content-Type": MIME_TYPE_JSON}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            nombre_completo = (
                data[0].get("TerceroId", {}).get("NombreCompleto", NOMBRE_NO_ENCONTRADO)
            )
            return nombre_completo
        else:
            return NOMBRE_NO_ENCONTRADO
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

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

        if (
            response.status_code == 400
            and "System" in response_data
            and "Error" in response_data["System"]
        ):
            return {USUARIO_NO_REGISTRADO}
        else:
            response.raise_for_status()

            roles_a_excluir = ["Internal/everyone"]
            filtered_roles = [ role for role in response_data.get("role", []) if role not in roles_a_excluir ]

            return {
                "roles": ", ".join(filtered_roles),
                "documento": response_data.get("documento"),
            }

    except requests.exceptions.RequestException:
        return {USUARIO_NO_REGISTRADO}

def extract_log_json(endpoint, api, metodo, usuario, data_json):
    data = {}
    data["endpoint"] = endpoint
    data["api"] = api
    data["metodo"] = metodo
    data["usuario"] = usuario
    data["data"] = data_json
    json_result = json.dumps(data, indent=4)
    return json_result

def aplicar_filtros_adicionales(eventos, params):
    """Versión modificada para diagnóstico"""
    if not eventos:
        return []
    filtered = eventos

    # Filtrar por método si está especificado
    if params.get("tipo_log"):
        filtered = [ log for log in filtered if params["tipo_log"].lower() in log.tipo_log.lower() ]

    # Filtrar por API si está especificado
    if params.get("api"):
        filtered = [ log for log in filtered if params["api"].lower() in log.peticion_realizada.lower() ]

    # Filtrar por endpoint si está especificado
    if params.get("endpoint"):
        filtered = [ log for log in filtered if params["endpoint"].lower() in log.peticion_realizada.lower() ]

    # Filtrar por IP si está especificado
    if params.get("ip"):
        filtered = [log for log in filtered if params["ip"] == log.direccion_accion]
    # Filtrar por IP si está especificado
    if params.get("ip"):
        filtered = [log for log in filtered if params["palabraClave"] in log.data_error]

    return filtered

def reemplazar_valores_log(metodo, log):
    """
    Procesa un log, extrae los valores de una consulta SQL y los reemplaza en su lugar correspondiente.

    Args:
        log (str): Parte del log con la consulta SQL y los valores a reemplazar.

    Returns:
        str: Consulta SQL con los valores reemplazados.
    """
    # Limitar la longitud de la entrada para prevenir DoS
    MAX_LOG_LENGTH = 10000  # Ajusta según necesidades
    if len(log) > MAX_LOG_LENGTH:
        raise ValueError("El log es demasiado largo para procesar")
    
    if metodo.upper() == "POST":
        match = re.search(PATRON, log)
        if match:
            consulta = match.group(1)
            valores = match.group(2).split(", ")

            for i, valor in enumerate(valores, start=1):
                consulta = consulta.replace(f"${i}", valor.strip())

            return consulta
        else:
            return "El formato del log POST no es válido: " + log

    elif metodo.upper() in ["PUT", "GET", "DELETE"]:
        try:
            match = re.search(PATRON, log)
            if match:
                consulta = match.group(1)
                valores = re.findall(r"`([^`]*)`", match.group(2))

                for i, valor in enumerate(valores, start=1):
                    consulta = consulta.replace(f"${i}", valor.strip())
                return consulta
            else:
                return f"El formato del log {metodo.upper()} no es válido: {log}"
        except re.error:
            return f"Error al procesar el log {metodo.upper()} con expresión regular"
    else:
        return

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

def limpiar_caracteres_ansi(texto):
    """
    Función que elimina los códigos de escape ANSI de un texto
    """
    if not texto:
        return texto

    # Verificar longitud máxima
    if len(texto) > MAX_TEXT_LENGTH:
        raise ValueError(f"El texto excede la longitud máxima permitida ({MAX_TEXT_LENGTH} caracteres)")
    try:
        # Python 3.11+ permite timeout en regex
        if hasattr(re, 'Pattern') and hasattr(ANSI_ESCAPE, 'sub'):
            return ANSI_ESCAPE.sub('', texto, timeout=1.0)  # Timeout de 1 segundo
        else:
            return ANSI_ESCAPE.sub('', texto)
    except (re.error, TimeoutError):
        # En caso de error, retornar el texto sin modificar (o podrías lanzar una excepción)
        return texto