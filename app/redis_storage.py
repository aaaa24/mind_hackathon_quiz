import redis
import pickle
from typing import Optional, List
from .models import Room

# Подключение к Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False)


def save_room(room_id: str, room: Room):
    """Сохранить комнату в Redis."""
    r.set(f"room:{room_id}", pickle.dumps(room))


def get_room(room_id: str) -> Optional[Room]:
    """Получить комнату из Redis."""
    data = r.get(f"room:{room_id}")
    if data:
        return pickle.loads(data)
    return None


def delete_room(room_id: str):
    """Удалить комнату из Redis."""
    r.delete(f"room:{room_id}")


def save_room_code(code: str, room_id: str):
    """Сохранить сопоставление код -> room_id."""
    r.set(f"code:{code}", room_id.encode('utf-8'))


def get_room_id_by_code(code: str) -> Optional[str]:
    """Получить room_id по коду."""
    room_id = r.get(f"code:{code}")
    return room_id.decode('utf-8') if room_id else None


def delete_room_code(code: str):
    """Удалить код комнаты."""
    r.delete(f"code:{code}")


def set_quest_position(room_id: str, index: int):
    """Сохранить индекс текущего вопроса."""
    r.set(f"quest_pos:{room_id}", index)


def get_quest_position(room_id: str) -> Optional[int]:
    """Получить индекс текущего вопроса."""
    pos = r.get(f"quest_pos:{room_id}")
    return int(pos) if pos else None


def delete_quest_position(room_id: str):
    """Удалить индекс вопроса."""
    r.delete(f"quest_pos:{room_id}")


def add_active_room(room_id: str):
    """Добавить комнату в список активных."""
    r.sadd("active_rooms", room_id.encode('utf-8'))


def remove_active_room(room_id: str):
    """Удалить комнату из списка активных."""
    r.srem("active_rooms", room_id.encode('utf-8'))


def get_active_rooms() -> List[str]:
    """Получить список всех активных комнат."""
    room_ids = r.smembers("active_rooms")
    return [room_id.decode('utf-8') for room_id in room_ids]


def clear_room_data(room_id: str):
    """Удалить все данные комнаты из Redis."""
    delete_room(room_id)
    delete_quest_position(room_id)
    # Удалить код, если знаем его
    # Лучше хранить обратное сопоставление: room_id -> code