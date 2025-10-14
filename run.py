from app import create_app
from app.sockets import init_socketio

app = create_app()
init_socketio(app)

if __name__ == '__main__':
    from app import socketio
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)