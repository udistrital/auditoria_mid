class RespuestaLog:
    """
    Modelo para representar un evento de log en respuesta de la api.
    """
    def __init__(
            self, tipo_log, fecha, rol_responsable, nombre_responsable, documento_responsable,
            direccion_accion, rol, apis_consumen, peticion_realizada, evento_bd, tipo_error, mensaje_error
        ):
        self.tipoLog = tipo_log  
        self.fecha = fecha  
        self.rolResponsable = rol_responsable  
        self.nombreResponsable = nombre_responsable  
        self.documentoResponsable = documento_responsable  
        self.direccionAccion = direccion_accion  
        self.rol = rol  
        self.apisConsumen = apis_consumen  
        self.peticionRealizada = peticion_realizada  
        self.eventoBD = evento_bd  
        self.tipoError = tipo_error  
        self.mensajeError = mensaje_error  

    def to_dict(self):
        return {
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