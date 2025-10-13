import secrets
from typing import Dict
import uuid

from flask import Blueprint, jsonify, request, make_response
from flask_jwt_extended import jwt_required, create_access_token, set_access_cookies, unset_jwt_cookies, \
    get_jwt_identity
from .models import Room, Player, Question, RoomStatus

from . import fake_db as db

bp = Blueprint('main', __name__)

room_codes: Dict[str, str] = {}


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

    # Сохраняем комнату в БД
    result_creation = db.create_room(new_room)
    if not result_creation['success']:
        return jsonify({'message': 'Room creation failed'}), 500

    # Генерируем код и сохраняем сопоставление
    code = generate_code()
    room_codes[code] = room_id

    return jsonify({'room_code': code}), 201


@bp.route('/rooms/join', methods=['POST'])
@jwt_required()
def join_room_by_code():
    data = request.json
    code = data.get('code')

    if not code:
        return jsonify({'message': 'Room code is required'}), 400

    room_id = room_codes.get(code)
    if not room_id:
        return jsonify({'message': 'Room not found'}), 404

    user_id = get_jwt_identity()

    user = db.get_user(user_id)
    if not user['success']:
        return jsonify({'message': 'User not found'}), 404

    username = user['login']

    # Получаем комнату из БД
    room_data = db.get_room(room_id)
    if not room_data['success']:
        return jsonify({'message': 'Room not found'}), 404

    room = room_data['room']

    # Проверки
    if user_id in room.players:
        return jsonify({'message': 'Player already in room'}), 400

    if room.status != RoomStatus.WAITING:
        return jsonify({'message': 'Quiz has already started'}), 400

    # Добавляем игрока
    player = Player(user_id=user_id, username=username)
    room.players[user_id] = player

    # Обновляем комнату в БД
    db.update_room(room)

    return jsonify({'message': 'Joined room successfully', 'room_id': room_id}), 200