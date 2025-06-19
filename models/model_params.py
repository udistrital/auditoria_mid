from flask_restx import fields

def define_parameters(api):

    filtro_log_model = api.model('filtro_log_request', {
        'fechaInicio': fields.String(
            required=True
        ),
        'horaInicio': fields.String(
            required=True
        ),
        'fechaFin': fields.String(
            required=True
        ),
        'horaFin': fields.String(
            required=True
        ),
        'tipo_log': fields.String(
            required=True
        ),
        'codigoResponsable': fields.Integer(
            required=True
        ),
        'nombreApi': fields.String(
            required=True
        ),
        'entornoApi': fields.String(
            required=True
        )
    })

    return {'filtro_log_model': filtro_log_model}
