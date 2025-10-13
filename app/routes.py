import secrets
from typing import Dict
import uuid

from flask import Blueprint, jsonify, request, make_response
from flask_jwt_extended import jwt_required, create_access_token, set_access_cookies, unset_jwt_cookies, \
    get_jwt_identity
from .models import Room, Player, Question, RoomStatus

from . import fake_db as db
from . import storage

bp = Blueprint('main', __name__)


def generate_code(length: int = 6) -> str:
    return secrets.token_urlsafe(length)[:length].upper()


@bp.route('/user/signup', methods=['POST'])
def signup():
    data = request.json
    login = data.get('login')
    password = data.get('password')

    if not (login and password):
        return jsonify({'message': 'Login and password are required'}), 400

    result = db.sign_up(login, password)

    if not result['success']:
        return jsonify({'message': 'User already exists'}), 400

    return jsonify({'message': 'User signed up successfully'}), 201


@bp.route('/user/signin', methods=['POST'])
def signin():
    data = request.json
    login = data.get('login')
    password = data.get('password')

    if not (login and password):
        return jsonify({'message': 'Login and password are required'}), 400

    result = db.sign_in(login, password)

    if not result['success']:
        return jsonify({'message': 'Invalid login or password'}), 401

    access_token = create_access_token(identity=result['user_id'])
    resp = make_response(jsonify({'message': 'User signed in successfully'}), 200)
    set_access_cookies(resp, access_token)

    return resp


@bp.route('/user/logout', methods=['POST'])
@jwt_required()
def logout():
    resp = make_response(jsonify({'message': 'User logged out successfully'}), 200)
    unset_jwt_cookies(resp)

    return resp


@bp.route('/user/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()

    user = db.get_user(user_id)

    if not user['success']:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({'login': user['login']}), 200


@bp.route('/rooms/create', methods=['POST'])
@jwt_required()
def create_room():
    user_id = get_jwt_identity()

    user = db.get_user(user_id)
    if not user['success']:
        return jsonify({'message': 'User not found'}), 404

    username = user['login']

    # Генерация уникального ID комнаты
    room_id = str(uuid.uuid4())
    new_room = Room(room_id=room_id)

    # Добавляем создателя
    player = Player(user_id=user_id, username=username)
    new_room.players[user_id] = player
    new_room.owner = player

    # Сохраняем комнату в БД
    storage.rooms[room_id] = new_room

    # Генерируем код и сохраняем сопоставление
    code = generate_code()
    storage.room_codes[code] = room_id

    return jsonify({'room_code': code}), 201


@bp.route('/rooms/join', methods=['POST'])
@jwt_required()
def join_room_by_code():
    data = request.json
    code = data.get('code')

    if not code:
        return jsonify({'message': 'Room code is required'}), 400

    room_id = storage.room_codes.get(code)
    if not room_id:
        return jsonify({'message': 'Room not found'}), 404

    user_id = get_jwt_identity()

    user = db.get_user(user_id)
    if not user['success']:
        return jsonify({'message': 'User not found'}), 404

    username = user['login']

    # Получаем комнату из памяти
    room = storage.rooms.get(room_id)
    if not room:
        return jsonify({'message': 'Room not found'}), 404

    # Проверки
    if user_id in room.players:
        return jsonify({'message': 'Player already in room'}), 400

    if room.status != RoomStatus.WAITING:
        return jsonify({'message': 'Quiz has already started'}), 400

    # Добавляем игрока в память
    player = Player(user_id=user_id, username=username)
    room.players[user_id] = player

    return jsonify({'message': 'Joined room successfully', 'room_id': room_id}), 200


@bp.route('/rooms/<room_id>/start', methods=['POST'])
@jwt_required()
def start_room(room_id: str):
    user_id = get_jwt_identity()

    # Получаем комнату из памяти
    room = storage.rooms.get(room_id)
    if not room:
        return jsonify({'message': 'Room not found'}), 404

    # Проверяем, что пользователь — владелец комнаты
    if room.owner.user_id != user_id:
        return jsonify({'message': 'Only the room owner can start the quiz'}), 403

    # Проверяем, что викторина ещё не начата
    if room.status != RoomStatus.WAITING:
        return jsonify({'message': 'Quiz has already started or is finished'}), 400

    # Проверяем, что в комнате есть хотя бы 1 игрок
    if len(room.players) < 1:
        return jsonify({'message': 'Not enough players to start the quiz'}), 400

    # Меняем статус комнаты
    room.status = RoomStatus.QUESTION

    # Загружаем вопросы
    questions = db.get_questions()
    if not questions:
        return jsonify({'message': 'No questions available'}), 500

    room.questions = questions
    room.current_question_index = 0

    # Устанавливаем таймер для первого вопроса
    import datetime
    question_time_limit = room.questions[0].time_limit  # предположим, у Question есть time_limit
    room.timer_end = datetime.datetime.utcnow() + datetime.timedelta(seconds=question_time_limit)

    # Сбрасываем флаги answered для всех игроков
    for player in room.players.values():
        player.answered = False
        player.answer = None

    # Возвращаем ответ
    return jsonify({
        'message': 'Quiz started successfully',
        'current_question': room.questions[0],
        'timer_end': room.timer_end.isoformat()
    }), 200
