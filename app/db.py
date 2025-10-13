import json
import mysql.connector
import bcrypt
import os
from dotenv import load_dotenv
from app.models import Room, Question

load_dotenv()


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
    owner = room.owner
    end = room.timer_end
    amount = len(room.questions)
    put_room = put_to_bd("INSERT INTO rooms (id, owner, end, amount) VALUES (%s,%s,%s,%s)",
                         (room_id, owner, end, amount))
    sql = 'INSERT INTO rooms_users (id, owner, end) VALUES'
    params = []
    for player in room.players:
        params.append(room_id, player.user_id, player.score, player.correct)
        sql += ' (%s,%s,%s,%s), '
    sql = sql[:-2]
    sql += ';'
    put_players = put_to_bd("INSERT INTO rooms_users (id, user_id, score, correct) VALUES (%s,%s,%s)",
                            (room_id, owner, end))
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
        return {"success": True, "categories": [categories]}
    else:
        return {"success": False, "categories": None}


def get_questions(count_questions, category_ids):
    if not count_questions: count_questions = 10
    sql = "SELECT * FROM questions "
    if category_ids:
        placeholders = ', '.join(['%s'] * len(category_ids))
        sql += f'WHERE category_id in ({placeholders}) '
    sql += 'ORDER BY RAND() LIMIT %s;'
    data = get_from_bd(sql, (*category_ids, count_questions))
    if data:
        questions = []
        for question in data:
            questions.append(
                Question(id=question['id'],
                         text=question['text'],
                         options=json.loads(question['options'])["list"],
                         correct_answer=question['correct_answer'],
                         time_limit=question['time_limit']))
        return {'success': True, 'questions': questions}
    else:
        return {'success': True, 'questions': None}


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
                host=os.getenv('DB_HOST'),
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

# print(sign_in("Danil", "12345"))
# id1 = '572d2207-a841-11f0-8d77-cc28aa8d5d25'
# id2 = '1a4350d1-a841-11f0-8d77-cc28aa8d5d25'
# for i in range(15):
#     print(create_question(id1, f"Test_Кино_{i} Какой фильм называют «самым известным ужастиком о душе, которая живёт в воде»?", ["«Сияние»", "«Пила»", "«Звонок»", "«Чужой»"], "Звонок", 10+i))
#     print(create_question(id2, f"Test_Программирование_{i} Как вывести текст в консоль в python?", ["print()", "write()", "save()", "foo()", "bar()"], "print()", 10+i))
# print(get_categories())
# print(get_questions(5, [id1]))
# print(get_questions(7, [id1, id2]))
