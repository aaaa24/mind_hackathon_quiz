from logging import Logger
from typing import Dict
from flask import request
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from . import storage
from .models import RoomStatus, Question

socketio = SocketIO()


def init_socketio(app):
    socketio.init_app(app)


# key = room_id, value = position of quest
questPosition: Dict[str, int] = {}


@socketio.on("join_room")
def join_room(data):
    room_id = data['room_id']
    Logger.debug(msg=f"Received data = {data}")
    join_room(room_id)


@socketio.on("start_quiz")
def start_quiz(data):
    room_id = data["room_id"]

    room = storage.rooms.get(room_id)

    if room is None:
        emit("error", {"message": f"Room {room_id} not found"})
        return

    if not room.questions or len(room.questions) == 0:
        emit("error", {"message": "No questions in this room"})
        return

    questPosition[room_id] = 0
    for player in room.players.values():
        player.score = 0
        player.correct = 0
        player.answer = ""
        player.answered = False

    firstQuest = room.questions[questPosition[room_id]]
    room.status = RoomStatus.QUESTION
    emit("startGame", firstQuest, to=room_id)



@socketio.on("answer")
def answer(data):
    room_id = data['room_id']
    user_id = data['user_id']
    answer = data['answer']

    room = storage.rooms.get(room_id)

    if room is None:
        return
    user = room.players.get(user_id)
    user.answer = answer
    user.answered = True


@socketio.on("next_question")
def next_question(data):
    room_id = data['room_id']
    room = storage.rooms.get(room_id)

    if room is None:
        emit("error", "This room doesn't exist", to=room_id)

    questions = room.questions
    lastAnswer = questions[questPosition[room_id]].correct_answer
    players = room.players.values()
    for i in players:
        if(i.answered and i.answer == lastAnswer):
            i.score += 10
            i.correct += 1
        i.answered = False
        i.answer = ""

    if (questPosition.get(room_id) == len(questions)-1):
        room.status = RoomStatus.FINISHED
        emit("EndOfGame", to=room_id)
    else:
        next_question_position = questPosition.get(room_id) + 1
        next_quest = questions[next_question_position]
        questPosition[room_id] = next_question_position
        emit("next_quest", next_quest, to=room_id)


@socketio.on("show_result")
def show_results(data):
    room_id = data['room_id']
    res = []
    players = storage.rooms.get(room_id).players.values()
    for i in players:
        r = {
            "username" : i.username,
            "score": i.score
        }
        res.append(r)
    res.sort(key = lambda x : [x['score']], reverse=True)
    emit("result", res, to=room_id)




@socketio.on("update_leaderboard")
def update_leaderboard(data):
    room_id = data['room_id']
    res = []
    players = storage.rooms.get(room_id).players.values()
    for i in players:
        r = {
            "username": i.username,
            "score": i.score
        }
        res.append(r)
    res.sort(key=lambda x: [x['score']], reverse=True)
    emit("update_leaderboard", res, to=room_id)
