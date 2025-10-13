from app import create_app
from app.sockets import init_socketio

app = create_app()
init_socketio(app)

if __name__ == '__main__':
    app.run(debug=True)
