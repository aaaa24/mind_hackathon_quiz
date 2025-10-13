import mysql.connector
import bcrypt
import os
from dotenv import load_dotenv
from app.models import Room

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
    if get_from_bd('SELECT id FROM users WHERE username = (%s)', (username,)):
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


def save_room(room: Room):
    room_id = room.room_id
    owner = room.owner
    end = room.timer_end
    amount = len(room.questions)
    put_room = put_to_bd("INSERT INTO rooms (id, owner, end, amount) VALUES (%s,%s,%s,%s)",
                         (room_id, owner, end, amount))
    players = room.players
    sql = 'INSERT INTO rooms_users (id, owner, end) VALUES'
    params = []
    for player in players:
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


print(sign_in("Danil", "12345"))
