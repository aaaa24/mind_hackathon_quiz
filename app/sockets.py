from flask import request
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from . import storage
from .models import RoomStatus


socketio = SocketIO()

def init_socketio(app):
    socketio.init_app(app)



@socketio.on("join_room")
def join_room(data):
    pass



@socketio.on("start_quiz")
def start_quiz():
    pass

@socketio.on("answer")
def answer(answer, username):
    pass


@socketio.on("next_question")
def next_question():
    pass

@socketio.on("show_result")
def show_results():
    pass

@socketio.on("update_leaderboard")
def update_leaderboard():
    pass