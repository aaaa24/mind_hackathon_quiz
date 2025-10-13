from typing import Dict
from flask import request
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from . import storage
from .models import RoomStatus, Question, Player
from threading import Lock

socketio = SocketIO()


def init_socketio(app):
    socketio.init_app(app)


# key = room_id, value = position of quest
questPosition: Dict[str, int] = {}
room_locks: Dict[str, Lock] = {}


def serialize_player(player):
    return {
        "user_id": player.user_id,
        "username": player.username,
        "score": player.score,
        "correct": player.correct,
        "answered": player.answered,
        "answer": player.answer,
        "joined_at": player.joined_at.isoformat() if player.joined_at else None
    }

def serialize_players(players):
    return [serialize_player(player) for player in players]

def question_timer(room_id, time_limit):
    socketio.sleep(time_limit)

    room = storage.rooms.get(room_id)
    if not room or room.status != RoomStatus.QUESTION:
        return

    current_question = room.questions[questPosition[room_id]]
    correct_answer = current_question.correct_answer

    emit("show_correct_answer", {"correct_answer": correct_answer}, to=room_id)

    socketio.sleep(15)
    with room_locks[room_id]:
        next_question({"room_id": room_id})



@socketio.on("join_room")
def join_game_room(data):
    room_id = data['room_id']

    user_id = data['user_id']
    room = storage.rooms.get(room_id, None)
    if(room.players.get(user_id) is None):
        emit("Error", "This user is not in room")
    else:
        print(f"Received data = {data}")
        join_room(room_id)


@socketio.on("start_quiz")
def start_quiz(data):
    room_id = data["room_id"]
    print(data)
    room = storage.rooms.get(room_id)

    if room is None:
        emit("error", {"message": f"Room {room_id} not found"})
        print("Vse huina")
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
    emit("startGame", vars(firstQuest), to=room_id)




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



def next_question(data):
    room_id = data['room_id']
    room = storage.rooms.get(room_id)

    if room is None:
        emit("error", "This room doesn't exist", to=room_id)

    questions = room.questions
    lastAnswer = questions[questPosition[room_id]].correct_answer
    players = room.players.values()
    for p in players:
        if(p.answered and p.answer == lastAnswer):
            p.score += 10
            p.correct += 1
        p.answered = False
        p.answer = ""

    if (questPosition.get(room_id) == len(questions)-1):
        room.status = RoomStatus.FINISHED
        emit("EndOfGame", to=room_id)
    else:
        next_question_position = questPosition.get(room_id) + 1
        next_quest = questions[next_question_position]
        questPosition[room_id] = next_question_position
        emit("next_quest", vars(next_quest), to=room_id)
        socketio.start_background_task(question_timer, room_id, next_quest.time_limit)


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
    emit("result", vars(res), to=room_id)




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
    emit("update_leaderboard", vars(res), to=room_id)


@socketio.on("all_players_in_lobby")
def all_players_in_lobby(data):
    room_id = data['room_id']
    room = storage.rooms.get(room_id)
    if room is None:
        emit("error", {"message": "Room not found"}, to=room_id)
        return
    players = {"players": serialize_players(room.players.values())}
    emit("all_players_in_lobby", players, to=room_id)

