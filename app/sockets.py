from typing import Dict
from flask_socketio import SocketIO, emit, join_room
from . import redis_storage
from .models import RoomStatus
from threading import Lock
from time import time
from flask import request

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
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)

    if room is None:
        emit("Error", "This room doesn't exist")
        return
    if room.players.get(user_id) is None:
        emit("Error", "This user is not in room", to=request.sid)
        return

    with global_init_lock:
        room_locks.setdefault(room_id, Lock())
        # Инициализируем позицию вопроса в Redis
        if redis_storage.get_quest_position(room_id) is None:
            redis_storage.set_quest_position(room_id, -1)
        question_start_times.setdefault(room_id, 0.0)

    print(f"Received data = {data}")
    join_room(room_id)
    emit("message","Join room success", to=request.sid)


@socketio.on("start_quiz")
def start_quiz(data):
    room_id = data.get("room_id")
    user_id = data.get("user_id")

    if not room_id:
        emit("Error", {"message": "missing room_id"}, to=request.sid)
        return
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if room is None:
        emit("Error", {"message": f"Room {room_id} not found"}, to=request.sid)
        return
    if not getattr(room, "questions", None):
        emit("Error", {"message": "No questions in this room"}, to=request.sid)
        return

    if user_id != room.owner.user_id:
        emit("Error", "Not owner try to start game")
        return

    # Устанавливаем позицию вопроса в Redis
    redis_storage.set_quest_position(room_id, 0)
    for player in room.players.values():
        player.score = 0
        player.correct = 0
        player.answer = ""
        player.answered = False

    # Сохраняем обновлённую комнату в Redis
    redis_storage.save_room(room_id, room)

    firstQuest = room.questions[0]
    # Сохраняем обновлённую комнату в Redis
    redis_storage.save_room(room_id, room)
    emit("startGame", vars(firstQuest), to=room_id)
    question_start_times[room_id] = time()
    socketio.start_background_task(question_timer, room_id, firstQuest.time_limit)
    room.status = RoomStatus.QUESTION



@socketio.on("answer")
def answer(data):
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    answer_text = data.get('answer')
    if not room_id or not user_id:
        emit("Error", {"message": "missing room_id or user_id"}, to=request.sid)
        return
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if not room:
        emit("Error", {"message": "room not found"}, to=request.sid)
        return

    if room.status != RoomStatus.QUESTION:
        return

    if room_locks.get(room_id) is None:
        emit("Error", {"message": "room lock not initialized"}, to=request.sid)
        return

    with room_locks[room_id]:
        start_ts = question_start_times.get(room_id)
        # Получаем позицию вопроса из Redis
        pos = redis_storage.get_quest_position(room_id)
        if start_ts is None or pos is None:
            emit("Error", {"message": "question not started"}, to=request.sid)
            return
        try:
            current_quest = room.questions[pos]
        except (IndexError, TypeError):
            emit("Error", {"message": "invalid question position"}, to=request.sid)
            return

        user = room.players.get(user_id)
        if not user:
            emit("Error", {"message": "user not in room"}, to=request.sid)
            return
        if user.answered:
            return

        past_time = time() - start_ts
        lim = getattr(current_quest, "time_limit", 0)
        if lim <= 0:
            user.answered = True
            user.answer = answer_text
            # Сохраняем обновлённую комнату в Redis
            redis_storage.save_room(room_id, room)
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
            # Сохраняем обновлённую комнату в Redis
            redis_storage.save_room(room_id, room)


def question_timer(room_id, time_limit):
    socketio.sleep(time_limit)

    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if not room or room.status != RoomStatus.QUESTION:
        return

    # Получаем позицию вопроса из Redis
    pos = redis_storage.get_quest_position(room_id)
    if pos is None:
        return

    current_question = room.questions[pos]
    correct_answer = current_question.correct_answer

    emit("show_correct_answer", {"correct_answer": correct_answer}, to=room_id)
    emit("need_update_leaderboard", to=room_id)
    room.status = RoomStatus.CHECK_CORRECT_ANSWER

    socketio.sleep(20)
    with room_locks[room_id]:
        next_question({"room_id": room_id})


def next_question(data):
    room_id = data['room_id']
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)

    if room is None:
        emit("Error", "This room doesn't exist", to=request.sid)
        return
    questions = room.questions

    # Получаем позицию вопроса из Redis
    pos = redis_storage.get_quest_position(room_id)
    if pos is None:
        emit("Error", "Quest position not found", to=room_id)
        return

    if pos == len(questions) - 1:
        room.status = RoomStatus.FINISHED
        # Сохраняем обновлённую комнату в Redis
        redis_storage.save_room(room_id, room)
        # Удаляем комнату из списка активных
        redis_storage.remove_active_room(room_id)
        emit("endOfGame", to=room_id)
        # Удаляем позицию вопроса из Redis
        redis_storage.delete_quest_position(room_id)
        # Убираем локальные данные
        question_start_times.pop(room_id, None)
        room_locks.pop(room_id, None)
        return

    else:
        next_question_position = pos + 1
        next_quest = questions[next_question_position]
        # Обновляем позицию вопроса в Redis
        redis_storage.set_quest_position(room_id, next_question_position)
        emit("get_quest", vars(next_quest), to=room_id)
        question_start_times[room_id] = time()
        socketio.start_background_task(question_timer, room_id, next_quest.time_limit)
        room.status = RoomStatus.QUESTION


@socketio.on("show_result")
def show_results(data):
    room_id = data['room_id']
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if not room:
        emit("Error", "Room not found", to=room_id)
        return

    res = []
    players = room.players.values()
    for i in players:
        r = {
            "user_id": i.user_id,
            "username": i.username,
            "score": i.score
        }
        res.append(r)
    res.sort(key=lambda x: x['score'], reverse=True)
    emit("result", res, to=room_id)


@socketio.on("update_leaderboard")
def update_leaderboard(data):
    room_id = data['room_id']
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if not room:
        emit("Error", "Room not found", to=room_id)
        return

    res = []
    players = room.players.values()
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
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if room is None:
        emit("Error", {"message": "Room not found"}, to=request.sid)
        return
    players = {"players": serialize_players(room.players.values()),
               "owner" : serialize_player(room.owner)}
    emit("all_players_in_lobby", players, to=request.sid)

