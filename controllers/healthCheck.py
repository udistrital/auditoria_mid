import json
from flask import Response

def health_check(app=None):
    dic_status = {
        'Status': 'ok',
        'Code': '200'
    }
    return Response(json.dumps(dic_status), status=200, mimetype='application/json')
