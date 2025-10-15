import redis
import pickle
import os

# Подключение к Redis
r = redis.Redis(host=os.getenv('REDIS_HOST'), port=int(os.getenv('REDIS_PORT')), db=0, decode_responses=False)


def save_request_sid(request_sid, user_id, room_id):
    r.set(f"sid_user:{request_sid}", user_id.encode('utf-8'))
    r.set(f"sid_room:{request_sid}", room_id.encode('utf-8'))


def delete_request_sid(request_sid):
    r.delete(f"sid_user:{request_sid}")
    r.delete(f"sid_room:{request_sid}")


def get_request_sid_data(request_sid):
    user_id = r.get(f"sid_user:{request_sid}")
    room_id = r.get(f"sid_room:{request_sid}")
    if (not user_id is None) and (not room_id is None):
        return user_id.decode('utf-8'), room_id.decode('utf-8')
    return None


def save_room(room_id, room):
    r.set(f"room:{room_id}", pickle.dumps(room))


def get_room(room_id):
    data = r.get(f"room:{room_id}")
    if data:
        return pickle.loads(data)
    return None


def delete_room(room_id):
    r.delete(f"room:{room_id}")


def save_room_code(code, room_id):
    r.set(f"code:{code}", room_id.encode('utf-8'))


def get_room_id_by_code(code):
    room_id = r.get(f"code:{code}")
    return room_id.decode('utf-8') if room_id else None


def delete_room_code(code):
    r.delete(f"code:{code}")


def set_quest_position(room_id, index):
    r.set(f"quest_pos:{room_id}", index)


def get_quest_position(room_id):
    pos = r.get(f"quest_pos:{room_id}")
    return int(pos) if pos else None


def delete_quest_position(room_id):
    r.delete(f"quest_pos:{room_id}")


def add_active_room(room_id):
    r.sadd("active_rooms", room_id.encode('utf-8'))


def remove_active_room(room_id):
    r.srem("active_rooms", room_id.encode('utf-8'))


def get_active_rooms():
    room_ids = r.smembers("active_rooms")
    return [room_id.decode('utf-8') for room_id in room_ids]


def clear_room_data(room_id):
    delete_room(room_id)
    delete_quest_position(room_id)
