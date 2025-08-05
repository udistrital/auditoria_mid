
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
from datetime import datetime
import time

APPLICATION_JSON = 'application/json'
ERROR_NO_USER = "Error WSO2 - Sin usuario"
DEFAULT_LOG_GROUP = '/ecs/polux_crud_test'

client = boto3.client(
    'logs',
    region_name='us-east-1'
)

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
        log_group_name = params.get('log_group_name', DEFAULT_LOG_GROUP)
        start_time = int(time.mktime(datetime(2024, 8, 1, 0, 0).timetuple()) * 1000)
        end_time = int(time.mktime(datetime(2024, 8, 2, 0, 0).timetuple()) * 1000)

        response = client.filter_log_events(
            logGroupName=log_group_name,
            startTime=start_time,
            endTime=end_time
        )

        events = [{"timestamp": event['timestamp'], "message": event['message']} for event in response.get('events', [])]
        
        if not events:
            return Response(json.dumps({'Status': 'No logs found', 'Code': '404', 'Data': []}), status=404, mimetype=APPLICATION_JSON)
        
        return Response(json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': events}), status=200, mimetype=APPLICATION_JSON)
    
    except Exception as e:
        return Response(json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}), status=500, mimetype=APPLICATION_JSON)

def get_one_log(params):
    """
    Consulta un solo evento de logs en CloudWatch para un grupo de logs específico con filtros adicionales.
    """
    try:
        entorno_api = ''
        filtro_busqueda = params["filterPattern"]
        filtro_email_user = params["emailUser"]
        query_string = ""

        query_string = build_query_string(filtro_busqueda, filtro_email_user)
        
        local_tz = timezone('America/Bogota')  
        utc_tz = utc

        local_start_time = datetime.strptime(params['startTime'], "%Y-%m-%d %H:%M")
        local_end_time = datetime.strptime(params['endTime'], "%Y-%m-%d %H:%M")

        utc_start_time = local_tz.localize(local_start_time).astimezone(utc_tz)
        utc_end_time = local_tz.localize(local_end_time).astimezone(utc_tz)

        start_time = int(utc_start_time.timestamp())
        end_time = int(utc_end_time.timestamp())

        entorno_api = 'prod' if params['environmentApi'] == 'PRODUCTION' else 'test'

        response = client.start_query(
            logGroupName=f"/ecs/{params['logGroupName']}_{entorno_api}",
            startTime=start_time,
            endTime=end_time,
            queryString=query_string
        )
        query_id = response['queryId']

        result = wait_for_query_completion(query_id)

        return process_query_results(result)

    except Exception as e:
        return Response(
            json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}),
            status=500,
            mimetype=APPLICATION_JSON
        )

def build_query_string(filtro_busqueda, filtro_email_user):
    """Construye la cadena de consulta para CloudWatch"""
    if not filtro_busqueda and not filtro_email_user:
        raise ValueError("El parámetro del método HTTP o el correo del usuario son obligatorios.")
    
    base_query = """
    fields @timestamp, @message
    | filter @message like /{}/ 
    and @message like /middleware/
    """
    
    if filtro_email_user:
        base_query += "and @message like /{}/\n"
        return base_query.format(filtro_busqueda, filtro_email_user)
    
    return base_query.format(filtro_busqueda) + "| sort @timestamp desc"

def wait_for_query_completion(query_id):
    """Espera a que la consulta de CloudWatch se complete"""
    while True:
        result = client.get_query_results(queryId=query_id)
        if result['status'] in ['Complete', 'Failed', 'Cancelled']:
            return result
        time.sleep(1)

def process_query_results(result):
    """Procesa los resultados de la consulta de CloudWatch"""
    if result['status'] != 'Complete' or not result['results']:
        return Response(
            json.dumps({'Status': 'No logs found or query failed', 'Code': '404', 'Data': []}),
            status=404,
            mimetype=APPLICATION_JSON
        )

    events = []
    for log in result['results']:
        message = next(item['value'] for item in log if item['field'] == '@message')
        extracted_data = extract_log_data(message)
        
        fecha_convertida = convert_date(extracted_data.get("fecha"))
        usuario_log = process_user(extracted_data.get("usuario", "").strip())
        rol_usuario = get_user_role(usuario_log)
        
        tipo_error, mensaje_error = extraer_error(message)
        log_obj = create_log_object(extracted_data, fecha_convertida, usuario_log, rol_usuario, tipo_error, mensaje_error)
        events.append(log_obj)
    
    return Response(
        json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': [vars(log) for log in events]}),
        status=200,
        mimetype=APPLICATION_JSON
    )

def convert_date(date_str):
    """Convierte una cadena de fecha al formato deseado"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""

def process_user(usuario):
    """Procesa el nombre de usuario del log"""
    if usuario not in ["N/A", "Error", "Error WSO2", ERROR_NO_USER, ""]:
        return f"{usuario}@udistrital.edu.co"
    return ERROR_NO_USER

def get_user_role(usuario_log):
    """Obtiene el rol del usuario"""
    if usuario_log != ERROR_NO_USER:
        return buscar_user_rol(usuario_log)
    return "Rol no encontrado"

def create_log_object(extracted_data, fecha_convertida, usuario_log, rol_usuario, tipo_error, mensaje_error):
    """Crea un objeto de log estructurado"""
    return respuesta_log.RespuestaLog(
        tipoLog=extracted_data.get("tipoLog"),
        fecha=fecha_convertida,
        rolResponsable=usuario_log,
        nombreResponsable="N/A",
        documentoResponsable="N/A",
        direccionAccion=extracted_data.get("direccionAccion", "N/A"),
        rol=rol_usuario,
        apisConsumen=extracted_data.get("apiConsumen", "N/A"),
        peticionRealizada=extract_log_json(
            extracted_data.get("endpoint"),
            extracted_data.get("api"),
            extracted_data.get("metodo"),
            usuario_log,
            extracted_data.get("data")
        ),
        eventoBD=reemplazar_valores_log(extracted_data.get("metodo"), extracted_data.get("sql_orm")),
        tipoError=tipo_error,
        mensajeError=mensaje_error
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
        "tipoLog": r"\[([a-zA-Z0-9\._-]+)(?=\.\w+:)",
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

def extract_log_json(endpoint,api,metodo,usuario,dataJson):
    data = {}
    data["endpoint"] = endpoint
    data["api"] = api
    data["metodo"] = metodo
    data["usuario"] = usuario
    data["data"] = dataJson
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
    headers = {"Content-Type": "application/json"}
    
    payload = {"user": user_email}
    
    try:
        roles_a_excluir = ["Internal/everyone"] 

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  

        data = response.json()
        roles = data.get("role", [])
        
        filtered_roles = [role for role in roles if role not in roles_a_excluir]

        return ", ".join(filtered_roles)
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
        if match:
            consulta = match.group(1)
            valores = re.findall(r'`([^`]*)`', match.group(2))

            for i, valor in enumerate(valores, start=1):
                consulta = consulta.replace(f"${i}", valor.strip())
            return consulta
        else:
            return "El formato del log PUT no es válido: " + log
        
    else:
        return log