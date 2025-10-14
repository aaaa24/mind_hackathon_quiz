from typing import Dict
from flask import request
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from . import storage
from .models import RoomStatus, Question, Player
from threading import Lock
from time import time

socketio = SocketIO()

def init_socketio(app):
    socketio.init_app(app)


# key = room_id, value = position of quest
questPosition: Dict[str, int] = {}
room_locks: Dict[str, Lock] = {}
question_start_times: Dict[str, float] = {}
global_init_lock = Lock()

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

@socketio.on("join_room")
def join_game_room(data):
    room_id = data['room_id']

    user_id = data['user_id']
    room = storage.rooms.get(room_id, None)

    if room is None:
        emit("Error", "This room doesn't exist")
        return
    if room.players.get(user_id) is None:
        emit("Error", "This user is not in room")
        return

    with global_init_lock:
        room_locks.setdefault(room_id, Lock())
        questPosition.setdefault(room_id, -1)
        question_start_times.setdefault(room_id, 0.0)

    print(f"Received data = {data}")
    join_room(room_id)
    emit("message","Join room success", to=room_id)


@socketio.on("start_quiz")
def start_quiz(data):
    room_id = data.get("room_id")
    if not room_id:
        emit("error", {"message": "missing room_id"})
        return
    room = storage.rooms.get(room_id)
    if room is None:
        emit("error", {"message": f"Room {room_id} not found"})
        return
    if not getattr(room, "questions", None):
        emit("error", {"message": "No questions in this room"})
        return

    questPosition[room_id] = 0
    for player in room.players.values():
        player.score = 0
        player.correct = 0
        player.answer = ""
        player.answered = False

    firstQuest = room.questions[0]
    room.status = RoomStatus.QUESTION
    emit("startGame", vars(firstQuest), to=room_id)
    socketio.start_background_task(question_timer, room_id, firstQuest.time_limit)



@socketio.on("answer")
def answer(data):
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    answer_text = data.get('answer')
    if not room_id or not user_id:
        emit("error", {"message": "missing room_id or user_id"})
        return
    room = storage.rooms.get(room_id)
    if not room:
        emit("error", {"message": "room not found"})
        return
    if room_locks.get(room_id) is None:
        emit("error", {"message": "room lock not initialized"})
        return

    with room_locks[room_id]:
        start_ts = question_start_times.get(room_id)
        pos = questPosition.get(room_id)
        if start_ts is None or pos is None:
            emit("error", {"message": "question not started"})
            return
        try:
            current_quest = room.questions[pos]
        except (IndexError, TypeError):
            emit("error", {"message": "invalid question position"})
            return

        user = room.players.get(user_id)
        if not user:
            emit("error", {"message": "user not in room"})
            return
        if user.answered:
            return

        past_time = time() - start_ts
        lim = getattr(current_quest, "time_limit", 0)
        if lim <= 0:
            user.answered = True
            user.answer = answer_text
            return

        if past_time <= lim:
            user.answered = True
            user.answer = answer_text
            part = lim / 4.0
            if answer_text == current_quest.correct_answer:
                user.correct += 1
                if 0 <= past_time < part:
                    user.score += 60  # 10 + 50
                elif part <= past_time < 2 * part:
                    user.score += 35
                elif 2 * part <= past_time < 3 * part:
                    user.score += 20
                else:
                    user.score += 10



def question_timer(room_id, time_limit):
    socketio.sleep(time_limit)

    room = storage.rooms.get(room_id)
    if not room or room.status != RoomStatus.QUESTION:
        return

    current_question = room.questions[questPosition[room_id]]
    correct_answer = current_question.correct_answer
    emit("show_correct_answer", {"correct_answer": correct_answer}, to=room_id)
    emit("need_update_leaderboard", to=room_id)

    socketio.sleep(20)
    with room_locks[room_id]:
        next_question({"room_id": room_id})

def next_question(data):
    room_id = data['room_id']
    room = storage.rooms.get(room_id)

    if room is None:
        emit("Error", "This room doesn't exist", to=room_id)

    questions = room.questions

    if (questPosition.get(room_id) == len(questions)-1):
        room.status = RoomStatus.FINISHED
        emit("EndOfGame", to=room_id)
        questPosition.pop(room_id, None)
        question_start_times.pop(room_id, None)
        room_locks.pop(room_id, None)
        return

    else:
        next_question_position = questPosition.get(room_id) + 1
        next_quest = questions[next_question_position]
        questPosition[room_id] = next_question_position
        emit("get_quest", vars(next_quest), to=room_id)
        question_start_times[room_id] = time()
        socketio.start_background_task(question_timer, room_id, next_quest.time_limit)


@socketio.on("show_result")
def show_results(data):
    room_id = data['room_id']
    res = []
    players = storage.rooms.get(room_id).players.values()
    for i in players:
        r = {
            "user_id" : i.user_id,
            "username" : i.username,
            "score": i.score
        }
        res.append(r)
    res.sort(key=lambda x: x['score'], reverse=True)
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


@socketio.on("all_players_in_lobby")
def all_players_in_lobby(data):
    room_id = data['room_id']
    room = storage.rooms.get(room_id)
    if room is None:
        emit("Error", {"message": "Room not found"}, to=room_id)
        return
    players = {"players": serialize_players(room.players.values()),
               "owner" : serialize_player(room.owner)}
    emit("all_players_in_lobby", players, to=room_id)

