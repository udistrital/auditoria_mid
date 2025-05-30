
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

MIME_TYPE_JSON = "application/json"
ERROR_WSO2_SIN_USUARIO = "Error WSO2 - Sin usuario"
USUARIO_NO_REGISTRADO ="Usuario no registrado"
NOMBRE_NO_ENCONTRADO = "Nombre no encontrado"

client = boto3.client(
    'logs',
    region_name='us-east-1',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
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
        entorno_api = ''

        filtro_busqueda=params["filterPattern"]
        filtro_email_user=params["emailUser"]
        query_string = ""
        limit = int(params.get("limit", 10))  # Por defecto 10
        page = int(params.get("page", 1))     # Por defecto 1

        if filtro_busqueda and filtro_email_user:
            query_string = """
            fields @timestamp, @message
            | filter @message like /{filtro_busqueda}/ 
                {'and @message like /middleware/' if filtro_busqueda else ''}
                {'and @message like /' + filtro_email_user + '/' if filtro_email_user else ''}
            | sort @timestamp desc
            | limit {}
            """.format(filtro_busqueda, filtro_email_user,limit)
        elif filtro_busqueda:
            query_string = """
            fields @timestamp, @message
            | filter @message like /{}/
            and @message like /middleware/
            | limit {}
            | sort @timestamp desc
            """.format(filtro_busqueda,limit)
        else:
            raise ValueError("El parámetro del método HTTP o el correo del usuario son obligatorios.")
        
        local_tz = timezone('America/Bogota')  
        utc_tz = utc
        if not params.get('startTime') or not params.get('endTime'):
            raise ValueError("startTime y endTime son obligatorios y deben estar en formato 'YYYY-MM-DD HH:MM'")
        try:
            local_start_time = datetime.strptime(params['startTime'], "%Y-%m-%d %H:%M")
            local_end_time = datetime.strptime(params['endTime'], "%Y-%m-%d %H:%M")
        except ValueError as e:
            raise ValueError(f"Formato de fecha inválido: {e}")

        utc_start_time = local_tz.localize(local_start_time).astimezone(utc_tz)
        utc_end_time = local_tz.localize(local_end_time).astimezone(utc_tz)

        start_time = int(utc_start_time.timestamp())
        end_time = int(utc_end_time.timestamp())

        if params['environmentApi'] == 'PRODUCTION':
            entorno_api = 'prod'
        else:
            entorno_api = 'test'

        response = client.start_query(
            logGroupName = f"/ecs/{params['logGroupName']}_{entorno_api}",
            startTime=start_time,
            endTime=end_time,
            queryString=query_string
        )
        query_id = response['queryId']

        while True:
            result = client.get_query_results(queryId=query_id)
            if result['status'] in ['Complete', 'Failed', 'Cancelled']:
                break
            time.sleep(1)

        if result['status'] == 'Complete' and result['results']:
            events = []
            for log in result['results']:
                message = next(item['value'] for item in log if item['field'] == '@message')
                extracted_data = extract_log_data(message)
                fecha_convertida = ""
                usuario_log = ""
                rol_usuario_buscado = ""
                documento_usuario_buscado = ""
                nombre_usuario_buscado = ""

                try:
                    fecha_convertida = datetime.strptime(extracted_data.get("fecha"), "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    fecha_convertida = ""

                usuario_sin_espacio = extracted_data.get("usuario", "").strip()
                if usuario_sin_espacio not in ["N/A", "Error", "Error WSO2", ERROR_WSO2_SIN_USUARIO, ""]:
                    usuario_log = f"{usuario_sin_espacio}@udistrital.edu.co"
                else:
                    usuario_log = ERROR_WSO2_SIN_USUARIO

                if usuario_log not in [ERROR_WSO2_SIN_USUARIO]:
                    resultado = buscar_user_rol(usuario_log)
                    
                    if USUARIO_NO_REGISTRADO in resultado:
                        rol_usuario_buscado = "Rol no encontrado"
                        documento_usuario_buscado = "Documento no encontrado"
                        nombre_usuario_buscado = NOMBRE_NO_ENCONTRADO
                    elif "error" in resultado:
                        rol_usuario_buscado = "Error al obtener roles"
                        documento_usuario_buscado = "Error al obtener documento"
                        nombre_usuario_buscado = "Error al obtener nombre"
                    else:
                        rol_usuario_buscado = resultado.get("roles")
                        documento_usuario_buscado = resultado.get("documento")
                        nombre_usuario_buscado = buscar_nombre_user(documento_usuario_buscado)
                else:
                    rol_usuario_buscado = "Rol no encontrado"
                    documento_usuario_buscado = "Documento no encontrado"
                    nombre_usuario_buscado = NOMBRE_NO_ENCONTRADO

                log_obj = respuesta_log.RespuestaLog(
                    tipo_log=extracted_data.get("tipoLog"),
                    fecha=fecha_convertida,
                    rol_responsable=usuario_log,
                    nombre_responsable=nombre_usuario_buscado,
                    documento_responsable=documento_usuario_buscado,
                    direccion_accion=extracted_data.get("direccionAccion", "N/A"),
                    rol=rol_usuario_buscado,
                    apis_consumen=extracted_data.get("apiConsumen", "N/A"),
                    peticion_realizada=extract_log_json(extracted_data.get("endpoint"),extracted_data.get("api"),extracted_data.get("metodo"),usuario_log,extracted_data.get("data")),
                    evento_bd=reemplazar_valores_log(extracted_data.get("metodo"),extracted_data.get("sql_orm")),
                    tipo_error="N/A",
                    mensaje_error=message
                )
                print(extracted_data)
                print(events)
                events.append(log_obj)
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                paged_logs = events[start_idx:end_idx]
                return Response(
                json.dumps({
                    'Status': 'Successful request',
                    'Code': '200',
                    'Data': [vars(log) for log in paged_logs],
                    'Pagination': {
                        'page': page,
                        'limit': limit,
                        'total': len(events),
                        'pages': (len(events) + limit - 1) // limit
                    }
                }),
                status=200,
                mimetype=MIME_TYPE_JSON
            )
            '''return Response(
                json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': [vars(log) for log in events]}),
                status=200,
                mimetype=MIME_TYPE_JSON
            )'''
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
        return log