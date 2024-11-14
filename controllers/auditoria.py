from services.auditoriaService import getAllLogs

def getAll(params):
    """
        Consulta eventos de logs en CloudWatch para un grupo de logs específico en un rango de tiempo
        
        Parameters
        ----------
        ninguno

        Returns
        -------
        json : lista de eventos de logs o información de errores
    """
    return getAllLogs(params)

