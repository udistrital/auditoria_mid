import logging
import json
from flask import Response
import yaml


def healthCheck(app):
    try:
        data = json.loads(json.dumps(app.__schema__))            
        with open('swagger/swagger.json', 'w') as jsonf:
            jsonf.write(json.dumps(app.__schema__,indent=4))

        with open('swagger/swagger.yml', 'w') as yamlf:
            yaml.dump(data, yamlf, allow_unicode=True, default_flow_style=False)
        DicStatus = {
                'Status':'ok',
                'Code':'200'
            }
        return Response(json.dumps(DicStatus),status=200,mimetype='application/json')
    except Exception as e:
        logging.error("type error: " + str(e))
        return Response(json.dumps({'Status':'500'}), status=500, mimetype='application/json')
