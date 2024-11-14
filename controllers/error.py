import json
from flask import Response

def add_error_handler(app):
    
    @app.errorhandler(404)
    def not_found_resource(e):
        DicStatus = {
            'Status':'Not found resource',
            'Code':'404'
        }
        return Response(json.dumps(DicStatus), status=404, mimetype='application/json')

    @app.errorhandler(400)
    def invalid_parameter(e):
        DicStatus = {
            'Status':'invalid parameter',
            'Code':'400'
        }
        return Response(json.dumps(DicStatus), status=400, mimetype='application/json')