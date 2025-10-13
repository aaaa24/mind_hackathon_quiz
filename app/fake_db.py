import uuid


def sign_up(login, password):
    return {'success': True}


def sign_in(login, password):
    return {'success': True, 'user_id': uuid.uuid4()}


def get_user(user_id):
    return {'success': True, 'user_id': user_id}
