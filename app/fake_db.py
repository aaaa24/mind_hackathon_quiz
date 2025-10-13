import uuid

from .models import Room, Question


def sign_up(login, password):
    return {'success': True}


def sign_in(login, password):
    return {'success': True, 'user_id': str(uuid.uuid4())}


def get_user(user_id):
    return {'success': True, 'login': 'test_login'}


def create_room(room: Room):
    # Добавление комнаты в базу данных
    return {'success': True}


def get_questions(count_questions, category_ids):
    questions = [
        Question(
            id=str(uuid.uuid4()),
            text='Question 1',
            options=['Option 1', 'Option 2', 'Option 3'],
            correct_answer='Option 1',
            time_limit=10,
            category_id='Что-то'
        ),
        Question(
            id=str(uuid.uuid4()),
            text='Question 2',
            options=['Option 4', 'Option 5', 'Option 6'],
            correct_answer='Option 4',
            time_limit=10,
            category_id='Что-то'
        ),
    ]
    return {'success': True, 'questions': questions}


def get_categories():
    result = {
        'success': True,
        'categories': [
            {'id': str(uuid.uuid4()), 'name': 'Category 1'},
            {'id': str(uuid.uuid4()), 'name': 'Category 2'}
        ]
    }
    return result