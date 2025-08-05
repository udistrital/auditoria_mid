class RespuestaLog:
    """
    Modelo para representar un evento de log en respuesta de la api.
    """
    def __init__(self, **kwargs):
        """
        Inicializa la clase con parámetros nombrados para reducir la complejidad.
        Los nombres de campos siguen el snake_case según convenciones de Python.
        """
        self.tipo_log = kwargs.get('tipo_log')
        self.fecha = kwargs.get('fecha')
        self.rol_responsable = kwargs.get('rol_responsable')
        self.nombre_responsable = kwargs.get('nombre_responsable')
        self.documento_responsable = kwargs.get('documento_responsable')
        self.direccion_accion = kwargs.get('direccion_accion')
        self.rol = kwargs.get('rol')
        self.apis_consumen = kwargs.get('apis_consumen')
        self.peticion_realizada = kwargs.get('peticion_realizada')
        self.evento_bd = kwargs.get('evento_bd')
        self.tipo_error = kwargs.get('tipo_error')
        self.mensaje_error = kwargs.get('mensaje_error')

    def to_dict(self):
        return {
            'tipoLog': self.tipo_log,
            'fecha': self.fecha,
            'rolResponsable': self.rol_responsable,
            'nombreResponsable': self.nombre_responsable,
            'documentoResponsable': self.documento_responsable,
            'direccionAccion': self.direccion_accion,
            'rol': self.rol,
            'apisConsumen': self.apis_consumen,
            'peticionRealizada': self.peticion_realizada,
            'eventoBD': self.evento_bd,
            'tipoError': self.tipo_error,
            'mensajeError': self.mensaje_error
        }
    def __str__(self):
        return (f"RespuestaLog(tipo_log={self.tipo_log}, fecha={self.fecha}, "
                f"peticion_realizada={self.peticion_realizada}, "
                f"mensaje_error={self.mensaje_error})")
    
    def __repr__(self):
        return self.__str__()