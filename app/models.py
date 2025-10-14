from enum import Enum
from typing import Dict, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field


class RoomStatus(str, Enum):
    WAITING = 'waiting'
    QUESTION = 'question'
    FINISHED = 'finished'
    CHECK_CORRECT_ANSWER = "checkCorrectAnswer"


@dataclass
class Player:
    user_id: str
    username: str
    score: int = 0
    correct: int = 0
    answered: bool = False
    answer: Optional[str] = None
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Category:
    id: str
    name: str


@dataclass
class Question:
    id: str
    text: str
    options: List[str]
    correct_answer: str
    time_limit: int
    category_id: str


@dataclass
class Room:
    room_id: str
    owner: Optional[Player] = None
    status: RoomStatus = RoomStatus.WAITING
    players: Dict[str, Player] = field(default_factory=dict)
    questions: List[Question] = field(default_factory=list)
    current_question_index: int = -1
    timer_end: Optional[datetime] = None
    leaderboard: List[dict] = field(default_factory=list)
    max_players: int = 10
