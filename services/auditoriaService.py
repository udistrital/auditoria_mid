
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

        #Creación del query
        filtroBusqueda=params["filterPattern"]
        if filtroBusqueda=="MIDDLEWARE":
            filtroBusqueda=filtroBusqueda.lower()
        query_string = """
        fields @timestamp, @message
        | filter @message like /{}/
        | sort @timestamp desc
        | limit 20
        """.format(filtroBusqueda)
        
        # Rango de fechas
        print("START TIME:" + params['startTime'])
        print("END TIME:" + params['endTime'])
        start_time = int(time.mktime(datetime.strptime(params['startTime'], "%Y-%m-%d %H:%M").timetuple()))
        end_time = int(time.mktime(datetime.strptime(params['endTime'], "%Y-%m-%d %H:%M").timetuple()))
        
        # Inicia la consulta
        response = client.start_query(
            logGroupName=params['logGroupName'],
            startTime=start_time,
            endTime=end_time,
            queryString=query_string
        )
        query_id = response['queryId']
        # Espera a que la consulta termine
        while True:
            result = client.get_query_results(queryId=query_id)
            if result['status'] in ['Complete', 'Failed', 'Cancelled']:
                break
            time.sleep(1)
        # Procesa los resultados si están disponibles
        if result['status'] == 'Complete' and result['results']:
            # Extrae los resultados y formatea
            events = []
            for log in result['results']:
                timestamp = next(item['value'] for item in log if item['field'] == '@timestamp')
                message = next(item['value'] for item in log if item['field'] == '@message')
                print("\n\n\n\n\n"+str(message)+"\n\n\n\n\n")
                extracted_data = extract_log_data(message)
                print("\n\n\n\n\n"+str(extracted_data)+"\n\n\n\n\n")
                # Crear instancia de RespuestaLog
                log_obj = respuesta_log.RespuestaLog(
                    idLog=extracted_data.get("eventId", "N/A"),
                    tipoLog=extracted_data.get("tipoLog", "N/A"),
                    fecha=datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M:%S.%f"),
                    rolResponsable=extracted_data.get("rolResponsable", "N/A"),
                    nombreResponsable="N/A",
                    documentoResponsable="N/A",
                    direccionAccion=extracted_data.get("direccionAccion", "N/A"),
                    rol=extracted_data.get("rolResponsable", "N/A"),
                    apisConsumen=extracted_data.get("apiConsumen", "N/A"),
                    peticionRealizada=message,
                    eventoBD=extracted_data.get("queryEvento", "N/A"),
                    tipoError="N/A",
                    mensajeError="N/A"
                )
                events.append(log_obj)
            # Retornar respuesta en el formato esperado
            return Response(
                json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': [vars(log) for log in events]}),
                status=200,
                mimetype='application/json'
            )
        # Si no se encontraron logs o la consulta falló
        return Response(
            json.dumps({'Status': 'No logs found or query failed', 'Code': '404', 'Data': []}),
            status=404,
            mimetype='application/json'
        )

    except Exception as e:
        print("AWS Error:", str(e))
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