import os
from flask import Flask
from flask_cors import cross_origin
from flask_cors import CORS
from conf import conf
from routers import router
from controllers import error
import logging
conf.check_env()

app = Flask(__name__)
cors_config = {
    "resources": {
        r"/v1/*": {
            "origins": os.getenv('ALLOWED_ORIGINS', 'http://localhost:4200,https://*.udistrital.edu.co').split(','),
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Authorization", "Content-Type"],
            "expose_headers": ["X-Total-Count"],
            "max_age": 600,
            "supports_credentials": False
        }
    }
}

CORS(app, **cors_config)
# Justificación para deshabilitar CSRF:
# Este servicio actúa como una API RESTful y no sirve contenido HTML con formularios.
# Todas las solicitudes se esperan con JSON y requieren autenticación por token (JWT).
# CSRF no aplica a APIs RESTful que usan Authorization: Bearer tokens, ya que los navegadores no incluyen estos tokens automáticamente.
# Ver OWASP REST Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html#csrf-considerations
# Por lo tanto, CSRF se deshabilita de forma explícita y consciente.
router.add_routing(app)
error.add_error_handler(app)

if __name__ == '__main__':
    
    app.run(host='0.0.0.0', port=int(os.environ['API_PORT']))
