
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

client = boto3.client(
    'logs',
    region_name='us-east-1',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
)

def getAllLogs(params):
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
            return Response(json.dumps({'Status': 'No logs found', 'Code': '404', 'Data': []}), status=404, mimetype='application/json')
        
        return Response(json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': events}), status=200, mimetype='application/json')
    
    except Exception as e:
        return Response(json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}), status=500, mimetype='application/json')

def getOneLog(params):
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
        entornoApi = ''

        filtroBusqueda=params["filterPattern"]
        query_string = """
        fields @timestamp, @message
        | filter @message like /{}/ and @message like /middleware/
        | sort @timestamp desc
        """.format(filtroBusqueda)
        
        local_tz = timezone('America/Bogota')  
        utc_tz = utc

        local_start_time = datetime.strptime(params['startTime'], "%Y-%m-%d %H:%M")
        local_end_time = datetime.strptime(params['endTime'], "%Y-%m-%d %H:%M")

        utc_start_time = local_tz.localize(local_start_time).astimezone(utc_tz)
        utc_end_time = local_tz.localize(local_end_time).astimezone(utc_tz)

        start_time = int(utc_start_time.timestamp())
        end_time = int(utc_end_time.timestamp())

        if params['environmentApi'] == 'PRODUCTION':
            entornoApi = 'prod'
        else:
            entornoApi = 'test'

        response = client.start_query(
            logGroupName = f"/ecs/{params['logGroupName']}_{entornoApi}",
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
                timestamp = next(item['value'] for item in log if item['field'] == '@timestamp')
                message = next(item['value'] for item in log if item['field'] == '@message')

                extracted_data = extract_log_data(message)
                fechaConvertida = ""
                usuarioLog = ""
                rolUsuarioBuscado = ""

                try:
                    fechaConvertida = datetime.strptime(extracted_data.get("fecha"), "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    fechaConvertida = ""

                usuarioSinEspacio = extracted_data.get("usuario", "").strip()
                if usuarioSinEspacio not in ["N/A", "Error", "Error WSO2", "Error WSO2 - Sin usuario", ""]:
                    usuarioLog = f"{usuarioSinEspacio}@udistrital.edu.co"
                else:
                    usuarioLog = "Error WSO2 - Sin usuario"

                if usuarioLog not in ["Error WSO2 - Sin usuario"]:
                    rolUsuarioBuscado = buscar_user_rol(usuarioLog)
                else:
                    rolUsuarioBuscado = "Rol no encontrado"

                log_obj = respuesta_log.RespuestaLog(
                    tipoLog=extracted_data.get("tipoLog"),
                    fecha=fechaConvertida,
                    rolResponsable=usuarioLog,
                    nombreResponsable="N/A",
                    documentoResponsable="N/A",
                    direccionAccion=extracted_data.get("direccionAccion", "N/A"),
                    rol=rolUsuarioBuscado,
                    apisConsumen=extracted_data.get("apiConsumen", "N/A"),
                    peticionRealizada=extract_log_json(extracted_data.get("endpoint"),extracted_data.get("api"),extracted_data.get("metodo"),usuarioLog,extracted_data.get("data")),
                    eventoBD=reemplazar_valores_log(extracted_data.get("metodo"),extracted_data.get("sql_orm")),
                    tipoError="N/A",
                    mensajeError=message
                )
                events.append(log_obj)
            return Response(
                json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': [vars(log) for log in events]}),
                status=200,
                mimetype='application/json'
            )
        return Response(
            json.dumps({'Status': 'No logs found or query failed', 'Code': '404', 'Data': []}),
            status=404,
            mimetype='application/json'
        )

    except Exception as e:
        return Response(
            json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}),
            status=500,
            mimetype='application/json'
        )
    
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