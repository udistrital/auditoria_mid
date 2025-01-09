class RespuestaLog:
    """
    Modelo para representar un evento de log en respuesta de la api.
    """
    def __init__(
            self, tipoLog, fecha, rolResponsable, nombreResponsable, documentoResponsable,
            direccionAccion, rol, apisConsumen, peticionRealizada, eventoBD, tipoError, mensajeError
        ):
        #self.idLog = idLog  
        self.tipoLog = tipoLog  
        self.fecha = fecha  
        self.rolResponsable = rolResponsable  
        self.nombreResponsable = nombreResponsable  
        self.documentoResponsable = documentoResponsable  
        self.direccionAccion = direccionAccion  
        self.rol = rol  
        self.apisConsumen = apisConsumen  
        self.peticionRealizada = peticionRealizada  
        self.eventoBD = eventoBD  
        self.tipoError = tipoError  
        self.mensajeError = mensajeError  

    def to_dict(self):
        return {
            #'idLog': self.idLog,
            'tipoLog': self.tipoLog,
            'fecha': self.fecha,
            'rolResponsable': self.rolResponsable,
            'nombreResponsable': self.nombreResponsable,
            'documentoResponsable': self.documentoResponsable,
            'direccionAccion': self.direccionAccion,
            'rol': self.rol,
            'apisConsumen': self.apisConsumen,
            'peticionRealizada': self.peticionRealizada,
            'eventoBD': self.eventoBD,
            'tipoError': self.tipoError,
            'mensajeError': self.mensajeError
        }