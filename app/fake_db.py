import uuid

from .models import Room


def sign_up(login, password):
    return {'success': True}


def sign_in(login, password):
    return {'success': True, 'user_id': uuid.uuid4()}


def get_user(user_id):
    return {'success': True, 'login': 'test_login'}


def create_room(room: Room):
    # Добавление комнаты в базу данных
    return {'success': True}