
import os
import boto3
import json
from datetime import datetime
import time
from flask import Response

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
