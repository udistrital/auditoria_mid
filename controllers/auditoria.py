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
            # "logGroupName": "/ecs/polux_crud_test",
            "logGroupName": data.get('nombreApi'), 
            "environmentApi": data.get('entornoApi'), 
            "startTime": f"{data['fechaInicio']} {data['horaInicio']}",
            "endTime": f"{data['fechaFin']} {data['horaFin']}",
            "filterPattern": data.get('tipoLog')
        }

        #user_email = "pruebasoaspolux4@udistrital.edu.co"
        #resultado = auditoriaService.buscar_user_rol(user_email)
        #print(resultado)
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
