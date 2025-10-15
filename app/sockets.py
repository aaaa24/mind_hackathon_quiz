from datetime import datetime
from threading import Lock
from time import time
from typing import Dict

from flask_socketio import SocketIO, join_room, leave_room
from flask import request

from . import redis_storage, db
from .models import RoomStatus, Question

socketio = SocketIO()

# key = room_id, value = position of quest
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

def serialize_question(quest: Question, pos: int):
    return {
        "id": quest.id,
        "text": quest.text,
        "options": quest.options,
        "correct_answer" : quest.correct_answer,
        "time_limit": quest.time_limit,
        "category_id": quest.category_id,
        "position" : pos
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
        socketio.emit("Error", {"message": "This room doesn't exist"}, to=request.sid)
        return
    user = room.players.get(user_id)
    if user is None:
        socketio.emit("Error", {"message": "This user is not in room"}, to=request.sid)
        return
    print("Room exists")
    with global_init_lock:
        room_locks.setdefault(room_id, Lock())
        # Инициализируем позицию вопроса в Redis
        if redis_storage.get_quest_position(room_id) is None:
            redis_storage.set_quest_position(room_id, -1)
        question_start_times.setdefault(room_id, 0.0)

    print(f"Received data = {data}")
    join_room(room_id)
    redis_storage.save_request_sid(request.sid, user_id, room_id)
    socketio.emit("message", {"message": "Join room success"}, to=request.sid)
    all_players_in_lobby(data)


@socketio.on("leave_room")
def leave_game_room(data):
    room_id = data['room_id']
    user_id = data['user_id']
    if not user_id or not room_id:
        print(f"Missing user_id or room_id for SID: {request.sid}")
        socketio.emit("Error", {"message": "Session data not found"}, to=request.sid)
        return

    if not room_id:
        print(f"No room_id found for SID: {request.sid}")
        return

    try:
        leave_room(room_id)
        print("Leave room success")
    except Exception as e:
        print(f"Error leaving room: {e}")
        return

    room = redis_storage.get_room(room_id)

    if room is None:
        socketio.emit("Error", {"message": "This room doesn't exist"}, to=request.sid)
        return
    player = room.players.get(user_id)

    if player is None:
        socketio.emit("Error", {"message": "This player doesn't exist"}, to=request.sid)
        return
    room.players.pop(user_id, None)
    print("Player was deleted from room")
    if player.user_id == room.owner.user_id:
        other_players = [p for p in room.players.values()]
        if len(other_players) == 0:
            redis_storage.clear_room_data(room_id)
            room_locks.pop(room_id)
            question_start_times.pop(room_id)
            print("Room was deleted")
        else:
            room.owner = other_players[0]
            redis_storage.save_room(room_id, room)
            all_players_in_lobby({"room_id":room_id})


@socketio.on("room_status")
def status_room(data):
    room_id = data['room_id']
    if room_id is None:
        socketio.emit("Error", {"message": "This room_id doesn't exist"}, to=request.sid)
        return
    room = redis_storage.get_room(room_id)
    pos = redis_storage.get_quest_position(room_id)
    res = {
        "status" : room.status,
        "question" : serialize_question(room.questions[pos], pos+1)
    }
    socketio.emit("room_status", res, to=room_id)


@socketio.on("disconnect")
def disconnect():

    user_id, room_id = redis_storage.get_request_sid_data(request.sid)

    if not user_id or not room_id:
        print(f"Missing user_id or room_id for SID: {request.sid}")
        socketio.emit("Error", {"message": "Session data not found"}, to=request.sid)
        return

    if not room_id:
        print(f"No room_id found for SID: {request.sid}")
        return



    room = redis_storage.get_room(room_id)

    if room is None:
        socketio.emit("Error", {"message": "This room doesn't exist"}, to=request.sid)
        return
    player = room.players.get(user_id)

    if player is None:
        socketio.emit("Error", {"message": "This player doesn't exist"}, to=request.sid)
        return
    if room.status == RoomStatus.WAITING or room.status == RoomStatus.FINISHED:
        try:
            leave_room(room_id)
            redis_storage.delete_request_sid(request.sid)
            print("Leave room success")
        except Exception as e:
            print(f"Error leaving room: {e}")
            return

        room.players.pop(user_id, None)
        if player.user_id == room.owner.user_id:
            other_players = [p for p in room.players.values()]
            if len(other_players) == 0:
                redis_storage.clear_room_data(room_id)
                room_locks.pop(room_id)
                question_start_times.pop(room_id)
                print("Room was deleted")
            else:
                room.owner = other_players[0]
                redis_storage.save_room(room_id, room)
                all_players_in_lobby({"room_id": room_id})
            print("Player was deleted from room")



@socketio.on("start_quiz")
def start_quiz(data):
    room_id = data.get("room_id")
    user_id = data.get("user_id")

    if not room_id:
        socketio.emit("Error", {"message": "missing room_id"}, to=request.sid)
        return
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if room is None:
        socketio.emit("Error", {"message": f"Room {room_id} not found"}, to=request.sid)
        return
    if not getattr(room, "questions", None):
        socketio.emit("Error", {"message": "No questions in this room"}, to=request.sid)
        return

    if user_id != room.owner.user_id:
        socketio.emit("Error", "Not owner try to start game", to=room_id)
        return

    # Устанавливаем позицию вопроса в Redis
    redis_storage.set_quest_position(room_id, 0)
    for player in room.players.values():
        player.score = 0
        player.correct = 0
        player.answer = ""
        player.answered = False
    room.timer_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Сохраняем об новлённую комнату в Redis
    redis_storage.save_room(room_id, room)

    firstQuest = room.questions[0]

    socketio.emit("startGame", serialize_question(firstQuest, 1), to=room_id)
    question_start_times[room_id] = time()
    room.status = RoomStatus.QUESTION
    socketio.start_background_task(question_timer, room_id, firstQuest.time_limit)
    # Сохраняем обновлённую комнату в Redis
    redis_storage.save_room(room_id, room)


@socketio.on("answer")
def answer(data):
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    answer_text = data.get('answer')
    if not room_id or not user_id:
        socketio.emit("Error", {"message": "missing room_id or user_id"}, to=request.sid)
        print("Not room_id or user_id")
        return
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if not room:
        socketio.emit("Error", {"message": "room not found"}, to=request.sid)
        return

    if room.status != RoomStatus.QUESTION:
        print("PIZDA")
        return

    if room_locks.get(room_id) is None:
        print("HYILO")
        socketio.emit("Error", {"message": "room lock not initialized"}, to=request.sid)
        return

    with room_locks[room_id]:
        start_ts = question_start_times.get(room_id)
        # Получаем позицию вопроса из Redis
        pos = redis_storage.get_quest_position(room_id)
        if start_ts is None or pos is None:
            socketio.emit("Error", {"message": "question not started"}, to=request.sid)
            return
        try:
            current_quest = room.questions[pos]
        except (IndexError, TypeError):
            socketio.emit("Error", {"message": "invalid question position"}, to=request.sid)
            return

        user = room.players.get(user_id)
        if not user:
            socketio.emit("Error", {"message": "user not in room"}, to=request.sid)
            return
        if user.answered:
            print("OKAK")
            return
        print("Blat")
        past_time = time() - start_ts
        lim = getattr(current_quest, "time_limit", 0)
        if lim <= 0:
            user.answered = True
            user.answer = answer_text
            # Сохраняем обновлённую комнату в Redis
            redis_storage.save_room(room_id, room)
            return
        print("EBANAT")
        if past_time <= lim:
            user.answered = True
            user.answer = answer_text
            part = lim / 4.0
            print("SUKA")
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
            socketio.emit("answered",
                          {"user_id" : user_id, "correct_answered": int(answer_text == current_quest.correct_answer) }, to=room_id)
            print("New answers was fixed")
    all_answered = all(p.answered for p in room.players.values())
    if all_answered:
        print(f"Все игроки ответили — завершаем вопрос досрочно в комнате {room_id}")
        room.status = RoomStatus.CHECK_CORRECT_ANSWER
        redis_storage.save_room(room_id, room)


def question_timer(room_id, time_limit):
    for _ in range(time_limit):
        socketio.sleep(1)
        room = redis_storage.get_room(room_id)
        if not room:
            return
        if room.status != RoomStatus.QUESTION:
            break

    # Проверяем, не завершён ли вопрос досрочно
    room = redis_storage.get_room(room_id)

    # Получаем позицию вопроса из Redis
    pos = redis_storage.get_quest_position(room_id)
    if pos is None:
        return

    current_question = room.questions[pos]
    correct_answer = current_question.correct_answer

    sleeptime = 5
    room.status = RoomStatus.CHECK_CORRECT_ANSWER
    socketio.emit("show_correct_answer", {"correct_answer": correct_answer, "sleep_timer" : sleeptime}, to=room_id)
    socketio.emit("need_update_leaderboard", to=room_id)
    redis_storage.save_room(room_id,room)

    socketio.sleep(sleeptime)

    with room_locks[room_id]:
        next_question({"room_id": room_id})


def next_question(data):
    room_id = data['room_id']
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)

    if room is None:
        socketio.emit("Error", "This room doesn't exist", to=request.sid)
        return
    questions = room.questions

    for p in room.players.values():
        p.answered=False
        p.answer=""

    redis_storage.save_room(room_id, room)
    # Получаем позицию вопроса из Redis
    pos = redis_storage.get_quest_position(room_id)
    if pos is None:
        socketio.emit("Error", "Quest position not found", to=room_id)
        return

    if pos == len(questions) - 1:
        room.status = RoomStatus.FINISHED
        # Сохраняем обновлённую комнату в Redis
        room.timer_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        redis_storage.save_room(room_id, room)
        print(room)
        db.save_room(room)
        # Удаляем комнату из списка активных
        redis_storage.remove_active_room(room_id)
        socketio.emit("endOfGame", to=room_id)
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
        socketio.emit("get_quest", serialize_question(next_quest, pos+1), to=room_id)
        question_start_times[room_id] = time()
        room.status = RoomStatus.QUESTION
        redis_storage.save_room(room_id, room)
        socketio.start_background_task(question_timer, room_id, next_quest.time_limit)







@socketio.on("show_result")
def show_results(data):
    room_id = data['room_id']
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if not room:
        socketio.emit("Error", "Room not found", to=request.sid)
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
    socketio.emit("result", res, to=room_id)


@socketio.on("update_leaderboard")
def update_leaderboard(data):
    room_id = data['room_id']
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if not room:
        socketio.emit("Error", "Room not found", to=room_id)
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
    res.sort(key=lambda x: [x['score']], reverse=True)
    socketio.emit("update_leaderboard", res, to=room_id)


@socketio.on("all_players_in_lobby")
def all_players_in_lobby(data):
    room_id = data['room_id']
    # Получаем комнату из Redis
    room = redis_storage.get_room(room_id)
    if room is None:
        socketio.emit("Error", {"message": "Room not found"}, to=request.sid)
        return
    players = {"players": serialize_players(room.players.values()),
               "owner": serialize_player(room.owner)}
    print(f"Emitting to room {room_id}, players: {len(players['players'])}")
    socketio.emit("all_players_in_lobby", players, to=room_id)
