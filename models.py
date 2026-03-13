from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Set, Optional
import uuid

@dataclass
class OnlineUser:
    """Represents a connected user"""
    session_id: str
    user_id: int
    username: str
    current_room_id: Optional[int] = None
    connected_at: datetime = None

    def __post_init__(self):
        if self.connected_at is None:
            self.connected_at = datetime.utcnow()

@dataclass
class Message:
    """Represents a chat message"""
    id: str
    user_id: int
    username: str
    content: str
    timestamp: datetime
    room_id: int

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "room_id": self.room_id
        }

class ChatStore:
    """Central store for in-memory chat state"""

    def __init__(self):
        # room_id -> deque of messages (max 100)
        self.room_messages: Dict[int, deque] = {}

        # session_id -> OnlineUser
        self.online_users: Dict[str, OnlineUser] = {}

        # room_id -> Set of user_ids currently typing
        self.typing_users: Dict[int, Set[int]] = {}

    def add_message(self, room_id: int, user_id: int, username: str, content: str) -> Message:
        """Add a message to a room's history"""
        if room_id not in self.room_messages:
            self.room_messages[room_id] = deque(maxlen=100)

        message = Message(
            id=str(uuid.uuid4()),
            user_id=user_id,
            username=username,
            content=content,
            timestamp=datetime.utcnow(),
            room_id=room_id
        )
        self.room_messages[room_id].append(message)
        return message

    def get_room_messages(self, room_id: int) -> list:
        """Get message history for a room"""
        if room_id in self.room_messages:
            return [msg.to_dict() for msg in self.room_messages[room_id]]
        return []

    def add_online_user(self, session_id: str, user_id: int, username: str) -> OnlineUser:
        """Add a user to online users"""
        user = OnlineUser(session_id=session_id, user_id=user_id, username=username)
        self.online_users[session_id] = user
        return user

    def remove_online_user(self, session_id: str) -> Optional[OnlineUser]:
        """Remove a user from online users"""
        return self.online_users.pop(session_id, None)

    def get_online_user(self, session_id: str) -> Optional[OnlineUser]:
        """Get an online user by session_id"""
        return self.online_users.get(session_id)

    def get_online_users_list(self) -> list:
        """Get list of all online users"""
        return [
            {"id": user.user_id, "username": user.username}
            for user in self.online_users.values()
        ]

    def set_user_typing(self, room_id: int, user_id: int, is_typing: bool):
        """Set typing status for a user in a room"""
        if room_id not in self.typing_users:
            self.typing_users[room_id] = set()

        if is_typing:
            self.typing_users[room_id].add(user_id)
        else:
            self.typing_users[room_id].discard(user_id)

    def get_typing_users(self, room_id: int) -> list:
        """Get list of user_ids currently typing in a room"""
        if room_id in self.typing_users:
            return list(self.typing_users[room_id])
        return []

# Global chat store instance
chat_store = ChatStore()
