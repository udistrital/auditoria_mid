
import os
import boto3
import json
from datetime import datetime
import time
from flask import Response
from models import respuesta_log
import re

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
        """
        start_time = int(time.mktime(datetime.strptime(params.get('start_time', '2024-08-01'), "%Y-%m-%d").timetuple()) * 1000)
        end_time = int(time.mktime(datetime.strptime(params.get('end_time', '2024-08-02'), "%Y-%m-%d").timetuple()) * 1000)
        """
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
        start_time = int(time.mktime(datetime.strptime(params['startTime'], "%Y-%m-%d %H:%M").timetuple()) * 1000)
        end_time = int(time.mktime(datetime.strptime(params['endTime'], "%Y-%m-%d %H:%M").timetuple()) * 1000)

        response = client.filter_log_events(
            logGroupName=params['logGroupName'],
            startTime=start_time,
            endTime=end_time
        )

        eventos = []
        for event in response.get('events', []):
            extracted_data = extract_log_data(event.get('message', ''))
            pruebaPeticion = extract_log_json(event.get('message', ''))

            log = respuesta_log.RespuestaLog(
                idLog=event.get('eventId', 'N/A'),
                tipoLog=extracted_data.get("tipoLog", "N/A"), 
                fecha=extracted_data.get("fecha", datetime.utcfromtimestamp(event['timestamp'] / 1000).strftime("%Y-%m-%d %H:%M:%S")),
                rolResponsable=extracted_data.get("rolResponsable", "N/A"),
                nombreResponsable="N/A",  
                documentoResponsable="N/A", 
                direccionAccion=extracted_data.get("direccionAccion", 'N/A'),
                rol=extracted_data.get("rolResponsable", "N/A"), 
                apisConsumen=extracted_data.get("apiConsumen", 'N/A'),
                peticionRealizada=pruebaPeticion,
                eventoBD=extracted_data.get("queryEvento", "N/A"), 
                tipoError="N/A",  
                #mensajeError="N/A"
                mensajeError=event.get('message', 'N/A')
            )
            eventos.append(log)

        if not eventos:
            return Response(
                json.dumps({'Status': 'No logs found', 'Code': '404', 'Data': []}),
                status=404,
                mimetype='application/json'
            )

        return Response(
            json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': [vars(log) for log in eventos]}),  
            status=200,
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
    data = {}

    patterns = {
        "fecha": r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})",
        #"tipoLog": r"\[([a-zA-Z0-9\._-]+:\d+)\]",
        "tipoLog": r"\[([a-zA-Z0-9\._-]+)(?=\.\w+:)",
        "rolResponsable": r"@&[\w\.-]+@&([\w]+)@&",
        "apiConsumen": r"@&([\w\.:/-]+)@&",
        "direccionAccion": r"@&(\d+\.\d+\.\d+\.\d+)@&",
        "eventoBD": r"/v1/([\w_]+)\?([^\@]+)"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, log_entry)
        if match:
            if key == "tipoLog":
                data["tipoLog"] = match.group(1)
            if key == "eventoBD":
                data["nombreEvento"] = match.group(1)
                data["queryEvento"] = match.group(2)
            else:
                data[key] = match.group(1)
    return data

def extract_log_json(log_entry):

    patterns = {
        "endpoint": r"@&([\w\.:/-]+@&/v1/[\w_]+\?[^@]+)@&",
        "api": r"@&([\w_]+)@&[\w\.:/-]+@&",
        "metodo": r"@&([A-Z]+)@&",
        "usuario": r"@&([\w]+)@&map\[RouterPattern:"
    }
    dataGet=r"json:map\[Data:\[(.*)Message:"
    
    endpointPost=r"@&([\w\.:/-]+@&/v1/[\w_]+)@&"
    dataPost=r"json:map\[Data:\{(.*?)\} Message:"

    data = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, log_entry)
        if match:
            if key == "metodo":
                data["metodo"] = match.group(1)
                if match.group(1) == "POST":
                    print("Encontró un POST en el log")
                    matchPost = re.search(endpointPost, log_entry)
                    if matchPost:
                        data["endpoint"] = clean_data(matchPost.group(1))
                    matchPost = re.search(dataPost, log_entry)
                    if matchPost:
                        data["data"] = clean_data(matchPost.group(1))
                elif match.group(1) == "GET":  
                    matchGet = re.search(dataGet, log_entry)
                    if matchGet:
                        data["data"] = clean_data(matchGet.group(1))

            else:
                data[key] = clean_data(match.group(1))

    json_result = json.dumps(data, indent=4)
    return json_result

def clean_data(data_str):
    """
    Limpia caracteres no deseados y secuencias específicas del string.
    """
    cleaned_data = data_str
    cleaned_data = re.sub(r"%!s", "", cleaned_data)  
    cleaned_data = re.sub(r"<nil>", "", cleaned_data)  
    cleaned_data = (
        cleaned_data
        .replace("@", "")
        .replace("&", "")
        .replace("{", "")
        .replace("}", "")
        .replace("(", "")
        .replace(")", "")
        .replace("*", "")
    )
    cleaned_data = re.sub(r'\\', "", cleaned_data) 
    cleaned_data = re.sub(r'\\\"', "", cleaned_data)
    cleaned_data = re.sub(r'["\n]', " ", cleaned_data) 
    cleaned_data = re.sub(r'\s+', ' ', cleaned_data).strip()
    
    return cleaned_data