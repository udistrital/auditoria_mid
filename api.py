import os
from flask import Flask, request
from flask_cors import CORS
from conf import conf
from routers import router
from controllers import error
from security import csrf, generate_csrf
conf.check_env()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
csrf.init_app(app)
env = os.getenv('ENV', 'DEV').upper()  # Por defecto asumimos desarrollo
def get_allowed_origins():
    if env == 'PROD':
        # Configuración para producción - solo HTTPS
        return ['https://*.udistrital.edu.co', 'https://udistrital.edu.co']
    else:
        # Configuración para desarrollo - permite HTTP local
        return ['http://localhost:4200', 'http://127.0.0.1:4200']

cors_config = {
    "resources": {
        r"/v1/*": {
            "origins": get_allowed_origins(),
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Authorization", "Content-Type", "X-XSRF-TOKEN"],
            "expose_headers": ["Authorization", "Content-Type", "X-Total-Count", "X-XSRF-TOKEN"],
            "max_age": 600,
            "supports_credentials": True
        }
    }
}

CORS(app, **cors_config)

@app.after_request
def set_csrf_cookie(response):
    # Esto asegura que haya un token CSRF en la sesión para la primera solicitud.
    is_secure = False
    if env == 'PROD':
        is_secure=True
    if not request.cookies.get('XSRF-TOKEN'):
        token = generate_csrf()
        response.set_cookie(
            'XSRF-TOKEN', token,
            secure= is_secure ,  # True en producción con HTTPS
            httponly=False,  # Angular debe leerlo en el navegador
            samesite='Lax'
        )
    return response

router.add_routing(app)
error.add_error_handler(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ['API_PORT']))
