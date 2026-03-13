from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from collections import deque
import socketio
from sqlalchemy.orm import Session

# Import our modules
from database import init_db, get_db, create_user, get_user_by_username, get_user_by_id
from database import create_room, get_user_rooms, get_room_by_id, delete_room
from database import add_room_member, remove_room_member, get_room_members, is_room_member
from auth import hash_password, verify_password, create_access_token, verify_token
from models import chat_store

# Initialize FastAPI
app = FastAPI()

# Initialize database
init_db()

# Initialize Socket.IO
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)

# Pydantic models for request/response
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateRoomRequest(BaseModel):
    name: str
    invited_user_ids: List[int] = []

class InviteUserRequest(BaseModel):
    user_id: int

class TokenResponse(BaseModel):
    token: str
    user_id: int
    username: str

class UserResponse(BaseModel):
    id: int
    username: str

class RoomResponse(BaseModel):
    id: int
    name: str
    creator_id: int
    members_count: int

# REST API Endpoints

@app.post("/api/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = get_user_by_username(db, request.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create user
    password_hash = hash_password(request.password)
    user = create_user(db, request.username, password_hash)

    # Generate token
    token = create_access_token(user.id)

    return TokenResponse(token=token, user_id=user.id, username=user.username)

@app.post("/api/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # Get user
    user = get_user_by_username(db, request.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate token
    token = create_access_token(user.id)

    return TokenResponse(token=token, user_id=user.id, username=user.username)

@app.get("/api/verify")
def verify(token: str, db: Session = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {"user_id": user.id, "username": user.username}

@app.get("/api/rooms", response_model=List[RoomResponse])
def get_rooms(token: str, db: Session = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    rooms = get_user_rooms(db, user_id)
    return [
        RoomResponse(
            id=room.id,
            name=room.name,
            creator_id=room.creator_id,
            members_count=len(room.members)
        )
        for room in rooms
    ]

@app.post("/api/rooms", response_model=RoomResponse)
def create_new_room(request: CreateRoomRequest, token: str, db: Session = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Create room
    room = create_room(db, request.name, user_id)

    # Invite users
    for invited_user_id in request.invited_user_ids:
        if invited_user_id != user_id:  # Don't re-add creator
            add_room_member(db, room.id, invited_user_id)

    return RoomResponse(
        id=room.id,
        name=room.name,
        creator_id=room.creator_id,
        members_count=len(room.members)
    )

@app.get("/api/rooms/{room_id}")
def get_room_details(room_id: int, token: str, db: Session = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Check if user is member
    if not is_room_member(db, room_id, user_id):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    room = get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    members = get_room_members(db, room_id)

    return {
        "id": room.id,
        "name": room.name,
        "creator_id": room.creator_id,
        "members": [{"id": m.id, "username": m.username} for m in members]
    }

@app.post("/api/rooms/{room_id}/invite")
def invite_user_to_room(room_id: int, request: InviteUserRequest, token: str, db: Session = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    room = get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check if user is creator
    if room.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Only creator can invite users")

    # Add member
    success = add_room_member(db, room_id, request.user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add user")

    return {"message": "User invited successfully"}

@app.delete("/api/rooms/{room_id}/members/{member_id}")
def remove_user_from_room(room_id: int, member_id: int, token: str, db: Session = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    room = get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check if user is creator
    if room.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Only creator can remove users")

    # Don't allow removing creator
    if member_id == room.creator_id:
        raise HTTPException(status_code=400, detail="Cannot remove creator")

    # Remove member
    success = remove_room_member(db, room_id, member_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to remove user")

    return {"message": "User removed successfully"}

@app.delete("/api/rooms/{room_id}")
async def delete_room_endpoint(room_id: int, token: str, db: Session = Depends(get_db)):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    room = get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check if user is creator
    if room.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Only creator can delete room")

    # Store room name and get members before deletion
    room_name = room.name
    members = get_room_members(db, room_id)
    member_ids = [m.id for m in members]

    # Delete room from database first
    delete_room(db, room_id)

    # Notify all online users who were members of this room
    for online_user in chat_store.online_users.values():
        if online_user.user_id in member_ids:
            await sio.emit('room_deleted', {
                'room_id': room_id,
                'room_name': room_name
            }, room=online_user.session_id)

    return {"message": "Room deleted successfully"}

@app.get("/api/users/online", response_model=List[UserResponse])
def get_online_users(token: str):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return chat_store.get_online_users_list()

# Socket.IO Event Handlers

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

    # Get user info before removing
    user = chat_store.get_online_user(sid)
    if user:
        # Leave current room if in one
        if user.current_room_id:
            await sio.leave_room(sid, f"room_{user.current_room_id}")
            await sio.emit('user_left', {
                'user_id': user.user_id,
                'username': user.username
            }, room=f"room_{user.current_room_id}")

        # Remove from online users
        chat_store.remove_online_user(sid)

        # Broadcast updated online users list
        await sio.emit('online_users_update', {
            'users': chat_store.get_online_users_list()
        })

@sio.event
async def authenticate(sid, data):
    token = data.get('token')
    if not token:
        await sio.emit('auth_error', {'message': 'Token required'}, room=sid)
        return

    # Verify token
    user_id = verify_token(token)
    if not user_id:
        await sio.emit('auth_error', {'message': 'Invalid token'}, room=sid)
        return

    # Get user from database
    db = next(get_db())
    user = get_user_by_id(db, user_id)
    db.close()

    if not user:
        await sio.emit('auth_error', {'message': 'User not found'}, room=sid)
        return

    # Add to online users
    chat_store.add_online_user(sid, user.id, user.username)

    # Send success
    await sio.emit('authenticated', {
        'user_id': user.id,
        'username': user.username
    }, room=sid)

    # Broadcast updated online users list
    await sio.emit('online_users_update', {
        'users': chat_store.get_online_users_list()
    })

@sio.event
async def enter_room(sid, data):
    room_id = data.get('room_id')
    if not room_id:
        await sio.emit('error', {'message': 'Room ID required'}, room=sid)
        return

    # Get user
    user = chat_store.get_online_user(sid)
    if not user:
        await sio.emit('error', {'message': 'Not authenticated'}, room=sid)
        return

    # Check if user is member
    db = next(get_db())
    if not is_room_member(db, room_id, user.user_id):
        db.close()
        await sio.emit('error', {'message': 'Not a member of this room'}, room=sid)
        return

    # Get room details
    room = get_room_by_id(db, room_id)
    members = get_room_members(db, room_id)

    # Load messages from database
    from database import get_room_messages as get_db_messages
    db_messages = get_db_messages(db, room_id, limit=100)
    db.close()

    if not room:
        await sio.emit('error', {'message': 'Room not found'}, room=sid)
        return

    # Populate in-memory cache with database messages (in correct order)
    if room_id not in chat_store.room_messages:
        chat_store.room_messages[room_id] = deque(maxlen=100)
        # Add messages in chronological order (oldest first)
        for db_msg in reversed(db_messages):
            from models import Message
            msg = Message(
                id=db_msg.id,
                user_id=db_msg.user_id,
                username=db_msg.username,
                content=db_msg.content,
                timestamp=db_msg.timestamp,
                room_id=db_msg.room_id
            )
            chat_store.room_messages[room_id].append(msg)

    # Leave previous room if in one
    if user.current_room_id:
        await sio.leave_room(sid, f"room_{user.current_room_id}")
        await sio.emit('user_left', {
            'user_id': user.user_id,
            'username': user.username
        }, room=f"room_{user.current_room_id}")

    # Join new room
    user.current_room_id = room_id
    await sio.enter_room(sid, f"room_{room_id}")

    # Send room info to user
    await sio.emit('room_entered', {
        'room': {
            'id': room.id,
            'name': room.name,
            'creator_id': room.creator_id
        },
        'members': [{'id': m.id, 'username': m.username} for m in members],
        'messages': chat_store.get_room_messages(room_id)
    }, room=sid)

    # Notify others in room
    await sio.emit('user_entered', {
        'user_id': user.user_id,
        'username': user.username
    }, room=f"room_{room_id}", skip_sid=sid)

@sio.event
async def send_message(sid, data):
    content = data.get('content')
    if not content:
        await sio.emit('error', {'message': 'Message content required'}, room=sid)
        return

    # Get user
    user = chat_store.get_online_user(sid)
    if not user or not user.current_room_id:
        await sio.emit('error', {'message': 'Not in a room'}, room=sid)
        return

    # Add message to in-memory and database
    db = next(get_db())
    message = chat_store.add_message(user.current_room_id, user.user_id, user.username, content, db)
    db.close()

    # Broadcast to room
    await sio.emit('new_message', message.to_dict(), room=f"room_{user.current_room_id}")

@sio.event
async def typing_start(sid):
    user = chat_store.get_online_user(sid)
    if user and user.current_room_id:
        chat_store.set_user_typing(user.current_room_id, user.user_id, True)
        typing_users = chat_store.get_typing_users(user.current_room_id)
        await sio.emit('typing_update', {
            'typing_user_ids': typing_users
        }, room=f"room_{user.current_room_id}")

@sio.event
async def typing_stop(sid):
    user = chat_store.get_online_user(sid)
    if user and user.current_room_id:
        chat_store.set_user_typing(user.current_room_id, user.user_id, False)
        typing_users = chat_store.get_typing_users(user.current_room_id)
        await sio.emit('typing_update', {
            'typing_user_ids': typing_users
        }, room=f"room_{user.current_room_id}")

@sio.event
async def leave_room(sid):
    user = chat_store.get_online_user(sid)
    if user and user.current_room_id:
        room_id = user.current_room_id
        await sio.leave_room(sid, f"room_{room_id}")
        await sio.emit('user_left', {
            'user_id': user.user_id,
            'username': user.username
        }, room=f"room_{room_id}")
        user.current_room_id = None

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

# Export the ASGI app
app = socket_app
