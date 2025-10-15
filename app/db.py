import json
import mysql.connector
import bcrypt
import os
from typing import List
from app.models import Room, Question, Player
import random
from app.gpt import get_gpt_questions


def create_hash(password):
    salt = bcrypt.gensalt(rounds=12)
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    hash_str = password_hash.decode('utf-8')
    return hash_str


def is_password_true(password, password_hash):
    return bcrypt.checkpw(
        password.encode('utf-8'),
        password_hash.encode('utf-8')
    )


def sign_up(username, password):
    if username == '' or password == '': return {'success': False}
    password_hash = create_hash(password)
    if get_from_bd('SELECT id FROM users WHERE username = (%s)', (username,), one_row=True):
        return {'success': False}
    else:
        if put_to_bd('INSERT INTO users (username, password_hash) VALUES (%s,%s)', (username, password_hash)):
            return {'success': True}
        else:
            return {'success': False}


def sign_in(username, password):
    if username == '' or password == '': return {'success': False}
    data = get_from_bd('SELECT id, password_hash FROM users WHERE username = (%s)', [username], one_row=True)
    if not data:
        return {'success': False, 'user_id': None}
    password_hash = data['password_hash']
    user_id = data['id']
    if is_password_true(password, password_hash):
        return {'success': True, 'user_id': user_id}
    else:
        return {'success': False, 'user_id': None}


def get_user(user_id):
    data = get_from_bd('SELECT username FROM users WHERE id = (%s)', (user_id,), one_row=True)
    if data:
        return {"success": True, "login": data['username']}
    else:
        return {"success": False, "login": None}


def create_question(category_id, text, options, correct_answer, time_limit=30):
    options = json.dumps({"list": options})
    if put_to_bd(
            "INSERT INTO questions (category_id, text, options, correct_answer, time_limit) VALUES (%s,%s,%s,%s,%s)",
            (category_id, text, options, correct_answer, time_limit)):
        return {"success": True}
    return {"success": False}


def save_room(room: Room):
    room_id = room.room_id
    owner_user_id = room.owner.user_id
    end = room.timer_end
    amount = len(room.questions)
    put_room = put_to_bd("INSERT INTO rooms (id, owner, end, amount) VALUES (%s,%s,%s,%s)",
                         (room_id, owner_user_id, end, amount))
    sql = 'INSERT INTO rooms_users (id, owner, end) VALUES'
    params = []
    players: List[Player] = list(room.players.values())
    players.sort(key=lambda x: x.score)
    place = 1
    for player in players:
        params.append((room_id, player.user_id, player.score, player.correct, place))
        sql += ' (%s,%s,%s,%s,%s), '
        place += 1
    sql = sql[:-2]
    sql += ';'
    put_players = put_to_bd("INSERT INTO rooms_users (id, user_id, score, correct, place) VALUES ", params)
    if put_room and put_players:
        return {'success': True}
    else:
        return {'success': False}


def get_categories():
    data = get_from_bd("SELECT * FROM categories")
    if data:
        categories = []
        for category in data:
            categories.append({"id": category["id"], "name": category["name"]})
        return {"success": True, "categories": categories}
    else:
        return {"success": False, "categories": None}


def get_questions(count_questions, category_ids):
    if not count_questions or count_questions < 1: count_questions = 10
    count_questions = min(count_questions, 50)
    if os.getenv('GPT_CATEGORY_ID') in category_ids:
        category_ids.remove(os.getenv('GPT_CATEGORY_ID'))
        categories = get_categories()
        for k in categories['categories']:
            if k['id'] in category_ids:
                category_ids.remove(k['id'])
                category_ids.append(k['name'])
        return get_gpt_questions(count_questions, category_ids)
    sql = "SELECT * FROM questions "
    if category_ids:
        placeholders = ', '.join(['%s'] * len(category_ids))
        sql += f'WHERE category_id in ({placeholders}) '
    sql += 'ORDER BY RAND() LIMIT %s;'
    data = get_from_bd(sql, (*category_ids, count_questions))
    if data:
        questions = []
        for question in data:
            options = json.loads(question['options'])["list"]
            random.shuffle(options)
            questions.append(
                Question(id=question['id'],
                         text=question['text'],
                         options=options,
                         correct_answer=question['correct_answer'],
                         time_limit=question['time_limit'],
                         category_id=question['category_id']))
        return {'success': True, 'questions': questions}
    else:
        return {'success': True, 'questions': None}


def get_past_games(user_id):
    sql = """
    SELECT
        ru.room_id,
        ru.score,
        ru.correct,
        ru.place,
        r.amount,
        r.creation,
        r.end,
        u.id AS owner_id,
        u.username AS owner_username
    FROM rooms_users ru
    JOIN rooms r ON ru.room_id = r.id
    JOIN users u ON r.owner = u.id
    WHERE ru.user_id = %s
    """
    data = get_from_bd(sql, (user_id,))
    if data:
        games = []
        for row in data:
            owner = Player(user_id=row["owner_id"], username=row["owner_username"])

            game = {
                "score": row["score"],
                "correct": row["correct"],
                "owner_id": owner.user_id,
                "owner_username": owner.username,
                "amount": row["amount"],
                "creation": row["creation"],
                "end": row["end"],
                "place": row["place"]
            }
            games.append(game)
        return {"success": True, "games": games}
    return {"success": False, "games": None}


def put_to_bd(sql, params=None):
    try:
        mydb = bd_connect()
        cursor = mydb.cursor(dictionary=True)
        cursor.execute(sql, params)
        mydb.commit()
        cursor.close()
        mydb.close()
        return True
    except Exception as e:
        print(f'Ошибка: {e}')
        return False


def get_from_bd(sql, params=None, one_row=False):
    try:
        mydb = bd_connect()
        cursor = mydb.cursor(dictionary=True)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        mydb.commit()
        cursor.close()
        mydb.close()
    except Exception as e:
        print(f'Ошибка: {e}')
    else:
        if rows:
            if one_row:
                return rows[0]
            return rows
        else:
            return None


def bd_connect():
    k = 0
    while k <= 5:
        try:
            mydb = mysql.connector.connect(
                host=os.getenv('DB_HOST', "host.docker.internal"),
                user=os.getenv('DB_USER'),
                port=os.getenv('DB_PORT'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_DATABASE')
            )
        except mysql.connector.Error as err:
            print(f"Ошибка подключения к базе данных: {err}")
            k += 1
        else:
            return mydb
    return None

# list_cinema = []

# for i in list_cinema:
#   print(create_question('d82480da-a911-11f0-84fc-a22ec9dbc93e', i['text'], i['options'], i['correct_answer'], i['time_limit']))


# print(sign_in("Danil", "12345"))
# id1 = '5436c61a-a8f1-11f0-84fc-a22ec9dbc93e'
# id2 = '544e081f-a8f1-11f0-84fc-a22ec9dbc93e'
# for i in range(15):
#    print(create_question(id1, f"Test_Кино_{i} Какой фильм называют «самым известным ужастиком о душе, которая живёт в воде»?", ["«Сияние»", "«Пила»", "«Звонок»", "«Чужой»"], "Звонок", 10+i))
#    print(create_question(id2, f"Test_Программирование_{i} Как вывести текст в консоль в python?", ["print()", "write()", "save()", "foo()", "bar()"], "print()", 10+i))
# print(get_categories())
# print(get_questions(5, [id1]))
# print(get_questions(7, [id1, id2]))
# print(get_questions(5, [os.getenv('GPT_CATEGORY_ID'), id1]))
