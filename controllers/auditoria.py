import os
from services import auditoriaService 
from flask import json
from flask import Response
import boto3, time

def getAll(data):
    """
        Consulta eventos de logs en CloudWatch para un grupo de logs específico en un rango de tiempo
        
        Parameters
        ----------
        ninguno

        Returns
        -------
        json : lista de eventos de logs o información de errores
    """
    return auditoriaService.getAllLogs(data)

def postBuscarLog(data):
    """
        Consulta un log específico en CloudWatch en un rango de tiempo
        
        Parameters
        ----------
        body : json
            json con parametros como fechaInicio (str), fechaFin (str), tipoLog (str), codigoResponsable (int), rolResponsable (str)

        Returns
        -------
        json : información del log a consultar
    """
    """response_array=[]
    try:
        print("Datos recibidos:", data)
        return auditoriaService.getOneLog(data)
    except Exception as e:
        return False"""
    
    try:
        filtros = {
            "logGroupName": "/ecs/polux_crud_test",  
            "startTime": f"{data['fechaInicio']} {data['horaInicio']}",
            "endTime": f"{data['fechaFin']} {data['horaFin']}",
            "filterPattern": data.get('tipoLog', '')
        }

        print("Filtros procesados:", filtros)
        return auditoriaService.getOneLog(filtros)
    except KeyError as e:
        return Response(
            json.dumps({'Status': 'Bad Request', 'Code': '400', 'Error': f"Missing parameter: {str(e)}"}),
            status=400,
            mimetype='application/json'
        )
    except Exception as e:
        return Response(
            json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}),
            status=500,
            mimetype='application/json'
        )

def postFiltroPrueba():
    client = boto3.client(
        'logs',
        region_name='us-east-1',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
    )
    try:
        log_group_name = '/ecs/polux_crud_test'
        #Creación del query
        query_string = """
        fields @timestamp, @message
        | filter @message like /ERROR/
        | sort @timestamp desc
        | limit 20
        """

        # Rango de fechas
        ten_days_ago = int((time.time() - 30 * 24 * 60 * 60))
        now= int((time.time() - 15 * 24 * 60 * 60))
        #now = int(time.time())

        # Inicia la consulta
        response = client.start_query(
            logGroupName=log_group_name,
            startTime=ten_days_ago,
            endTime=now,
            queryString=query_string,
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
                events.append({"timestamp": timestamp, "message": message})

            # Retornar
            return Response(json.dumps({'Status': 'Successful request', 'Code': '200', 'Data': events}), 
                            status=200, mimetype='application/json')
        else:
            # Retorna un error si no hay resultados o la consulta falló
            return Response(json.dumps({'Status': 'No logs found or query failed', 
                                        'Code': '404', 'Data': []}), 
                            status=404, mimetype='application/json')
    except KeyError as e:
        return Response(
            json.dumps({'Status': 'Bad Request', 'Code': '400', 'Error': f"Missing parameter: {str(e)}"}),
            status=400,
            mimetype='application/json'
        )

