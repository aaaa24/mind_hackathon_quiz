from flask import Blueprint, jsonify, request, make_response
from flask_jwt_extended import jwt_required, create_access_token, set_access_cookies, unset_jwt_cookies, \
    get_jwt_identity
from .models import Room, Player, Question, RoomStatus

from . import fake_db as db

bp = Blueprint('main', __name__)


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


