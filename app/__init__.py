from datetime import timedelta
import os
import logging
from logging import StreamHandler
import sys
from dotenv import load_dotenv
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO

load_dotenv()

# Создаём socketio-объект



def create_app():
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
    app.config['JWT_TOKEN_LOCATION'] = ['cookies']
    app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False
    app.config['JWT_ACCESS_CSRF_COOKIE_NAME'] = os.getenv('JWT_ACCESS_CSRF_COOKIE_NAME')
    app.config["JWT_COOKIE_SECURE"] = False
    app.config["JWT_COOKIE_HTTPONLY"] = False
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)

    JWTManager(app)
    CORS(app, origins=['http://localhost:3000', 'http://89.223.70.57'], supports_credentials=True)

    if not app.debug:
        stream_handler = StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
    app.logger.info('Flask app started')

    from .routes import bp
    app.register_blueprint(bp)

    return app
