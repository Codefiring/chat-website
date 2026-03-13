from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./chat.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Many-to-many relationship table
room_members = Table(
    'room_members',
    Base.metadata,
    Column('room_id', Integer, ForeignKey('rooms.id', ondelete='CASCADE'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('joined_at', DateTime, default=datetime.utcnow)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    created_rooms = relationship("Room", back_populates="creator", cascade="all, delete-orphan")
    rooms = relationship("Room", secondary=room_members, back_populates="members")

class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    creator_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    creator = relationship("User", back_populates="created_rooms")
    members = relationship("User", secondary=room_members, back_populates="rooms")

# Database initialization
def init_db():
    Base.metadata.create_all(bind=engine)

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# User functions
def create_user(db, username: str, password_hash: str):
    user = User(username=username, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_username(db, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_id(db, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

# Room functions
def create_room(db, name: str, creator_id: int):
    room = Room(name=name, creator_id=creator_id)
    db.add(room)
    db.commit()
    db.refresh(room)
    # Add creator as first member
    add_room_member(db, room.id, creator_id)
    return room

def get_user_rooms(db, user_id: int):
    user = get_user_by_id(db, user_id)
    if user:
        return user.rooms
    return []

def get_room_by_id(db, room_id: int):
    return db.query(Room).filter(Room.id == room_id).first()

def delete_room(db, room_id: int):
    room = get_room_by_id(db, room_id)
    if room:
        db.delete(room)
        db.commit()
        return True
    return False

# Membership functions
def add_room_member(db, room_id: int, user_id: int):
    room = get_room_by_id(db, room_id)
    user = get_user_by_id(db, user_id)
    if room and user and user not in room.members:
        room.members.append(user)
        db.commit()
        return True
    return False

def remove_room_member(db, room_id: int, user_id: int):
    room = get_room_by_id(db, room_id)
    user = get_user_by_id(db, user_id)
    if room and user and user in room.members:
        room.members.remove(user)
        db.commit()
        return True
    return False

def get_room_members(db, room_id: int):
    room = get_room_by_id(db, room_id)
    if room:
        return room.members
    return []

def is_room_member(db, room_id: int, user_id: int):
    room = get_room_by_id(db, room_id)
    user = get_user_by_id(db, user_id)
    if room and user:
        return user in room.members
    return False
