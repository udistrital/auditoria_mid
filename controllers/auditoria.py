from services import auditoriaService, auditoriaServiceLog
from flask import json
from flask import Response
from datetime import datetime

def get_all(data):
    """
        Consulta eventos de logs en CloudWatch para un grupo de logs específico en un rango de tiempo

        Parameters
        ----------
        ninguno

        Returns
        -------
        json : lista de eventos de logs o información de errores
    """
    return auditoriaService.get_all_logs(data)

def post_buscar_log(data):
    """
        Consulta un log específico en CloudWatch en un rango de tiempo

        Parameters
        ----------
        body : json
            json con parametros como fechaInicio (str), fechaFin (str), tipo_log (str), codigoResponsable (int), rolResponsable (str)

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
            "logGroupName": data.get('nombreApi'),
            "environmentApi": data.get('entornoApi'),
            "startTime": f"{data['fechaInicio']} {data['horaInicio']}",
            "endTime": f"{data['fechaFin']} {data['horaFin']}",
            "filterPattern": data.get('tipo_log'),
            "emailUser": data.get('codigoResponsable'),
            "palabraClave": data.get('palabraClave'),
            "page": data.get('pagina'),
            "limit": data.get('limite', 5000),
        }

        return auditoriaServiceLog.get_one_log(filtros)
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

def get_logs_filtrados(data):
    """
    Consulta logs con filtros y paginación
    
    Parameters
    ----------
    data : MultiDict
        Parámetros de filtrado y paginación:
        - nombreApi: Nombre del API (ej: polux_crud)
        - entornoApi: Entorno (SANDBOX, PRODUCTION, TEST)
        - fechaInicio: Fecha de inicio (YYYY-MM-DD)
        - horaInicio: Hora de inicio (HH:MM)
        - fechaFin: Fecha de fin (YYYY-MM-DD)
        - horaFin: Hora de fin (HH:MM)
        - pagina: Número de página (default: 1)
        - limite: Registros por página (default: 10)
        - tipo_log: Tipo de log (GET, POST, etc.)
        - codigoResponsable: Email del usuario responsable
        - apiConsumen: API específica que consume el servicio
        - endpoint: Endpoint específico
        - direccionIp: Dirección IP del solicitante
        
    Returns
    -------
    Response
        Respuesta JSON con logs paginados y metadatos de paginación
    """
    try:
        # Validar parámetros requeridos
        required_params = ['nombreApi', 'entornoApi', 'fechaInicio', 'horaInicio', 'fechaFin', 'horaFin']
        fecha_inicio = datetime.fromtimestamp(int(data['fechaInicio'])).strftime('%Y-%m-%d')
        hora_inicio = datetime.fromtimestamp(int(data['fechaInicio'])).strftime('%H:%M')
        fecha_fin = datetime.fromtimestamp(int(data['fechaFin'])).strftime('%Y-%m-%d')
        hora_fin = datetime.fromtimestamp(int(data['fechaFin'])).strftime('%H:%M')
        for param in required_params:
            if param not in data:
                return Response(
                    json.dumps({'Status': 'Bad Request', 'Code': '400', 
                              'Error': f"Falta el parámetro requerido: {param}"}),
                    status=400,
                    mimetype='application/json'
                )
        
        # Convertir parámetros de paginación
        pagina = int(data.get('pagina', 1))
        limite = int(data.get('limite', 5000))  # Valor por defecto de 5000 registros
        
        # Construir filtros para la consulta
        filtros = {
            "logGroupName": data['nombreApi'],
            "nombreApi": data['nombreApi'],
            "fechaInicio": fecha_inicio,
            "horaInicio": hora_inicio,
            "fechaFin": fecha_fin,
            "horaFin": hora_fin,
            "environmentApi": data['entornoApi'],
            "entornoApi": data['entornoApi'],
            "startTime": f"{data['fechaInicio']} {data['horaInicio']}",
            "endTime": f"{data['fechaFin']} {data['horaFin']}",
            "filterPattern": data.get('tipo_log', ''),
            "emailUser": data.get('codigoResponsable', ''),
            "api": data.get('apiConsumen', ''),
            "endpoint": data.get('endpoint', ''),
            "ip": data.get('direccionIp', ''),
            "palabraClave": data.get('palabraClave', ''),
            "page": pagina,
            "limit": limite
        }
        type_search = data.get('typeSearch')
        if (type_search== 'flexible'):
            return auditoriaService.get_processed_filtered_logs(filtros)
        else:
            return auditoriaService.get_filtered_logs(filtros)
    except ValueError as e:
        return Response(
            json.dumps({'Status': 'Bad Request', 'Code': '400', 'Error': str(e)}),
            status=400,
            mimetype='application/json'
        )
    except Exception as e:
        return Response(
            json.dumps({'Status': 'Internal Error', 'Code': '500', 'Error': str(e)}),
            status=500,
            mimetype='application/json'
        )