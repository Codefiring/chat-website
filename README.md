# Chat Room Website

A lightweight, real-time chat application with a terminal-style interface for maintaining a low profile.

## Features

- User registration and authentication (JWT tokens)
- Private, invite-only chat rooms
- Real-time messaging with WebSocket
- Typing indicators
- Message history (last 100 messages per room)
- Online user tracking
- Room management (create, invite, remove members, delete)
- Terminal/debugging console UI design

## Technology Stack

- **Backend**: FastAPI + python-socketio
- **Frontend**: Vanilla HTML/CSS/JavaScript with Socket.IO
- **Database**: SQLite with SQLAlchemy
- **Authentication**: Bcrypt + JWT

## Installation

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

Start the server:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at: http://localhost:8000

## Usage

### Authentication

When you first open the application, you'll see a terminal-style interface. Use these commands:

- `/register <username> <password>` - Create a new account
- `/login <username> <password>` - Login to existing account
- `/help` - Show available commands

Example:
```
> /register alice mypassword123
> /login alice mypassword123
```

### Room List

After logging in, you'll see your available channels:

- `/list` - Refresh channel list
- `/join <number>` - Join a channel by number
- `/create <name>` - Create a new channel
- `/list-users` - Show online users
- `/logout` - Logout
- `/help` - Show help

Example:
```
> /create team-chat
> /join 1
```

### Chat

Inside a channel:

- Type any message (without `/`) to send it
- `/leave` - Leave the channel
- `/settings` - Open channel settings (admin only)
- `/help` - Show help

Example:
```
> Hello everyone!
> /leave
```

### Channel Settings (Admin Only)

Channel creators can manage their channels:

- `/invite <username>` - Invite a user to the channel
- `/kick <username>` - Remove a user from the channel
- `/delete-room` - Delete the channel
- `/back` - Return to chat
- `/help` - Show help

Example:
```
> /settings
> /invite bob
> /kick charlie
```

## Features

### Terminal UI Design

The interface is designed to look like a developer terminal/debugging console:
- Black background with green monospace text
- Command-line interface (no buttons)
- Timestamp-based message display
- Minimal, text-only interface
- Looks like a system debugging tool

### Security

- Passwords are hashed with bcrypt (12 salt rounds)
- JWT tokens with 7-day expiration
- Private rooms (only members can see/access)
- Creator-only room management
- Token-based authentication for all API calls

### Real-time Features

- Instant message delivery via WebSocket
- Typing indicators
- Online user tracking
- Room membership notifications
- Auto-reconnection handling

## Database Schema

### Users Table
- `id` - Primary key
- `username` - Unique username
- `password_hash` - Bcrypt hashed password
- `created_at` - Account creation timestamp

### Rooms Table
- `id` - Primary key
- `name` - Room name
- `creator_id` - Foreign key to users (room creator)
- `created_at` - Room creation timestamp

### Room Members Table (Many-to-Many)
- `room_id` - Foreign key to rooms
- `user_id` - Foreign key to users
- `joined_at` - Join timestamp

## Architecture

### Backend (app.py)

- **REST API**: Authentication, room management, user discovery
- **WebSocket**: Real-time chat, typing indicators, presence
- **Database**: SQLite with SQLAlchemy ORM
- **In-Memory**: Message history (last 100 per room), online users, typing state

### Frontend (static/index.html)

- **Single HTML file** with embedded CSS and JavaScript
- **Command parser** for terminal-style interface
- **Socket.IO client** for real-time communication
- **State management** for current screen, room, messages
- **Command history** with up/down arrow navigation

## Development

### Project Structure

```
chat_website/
├── app.py                 # FastAPI + SocketIO server
├── auth.py                # Authentication (bcrypt, JWT)
├── database.py            # SQLite database models
├── models.py              # In-memory data structures
├── requirements.txt       # Python dependencies
├── static/
│   └── index.html         # Frontend (HTML/CSS/JS)
├── chat.db                # SQLite database (auto-created)
└── README.md             # This file
```

### API Endpoints

**Authentication:**
- `POST /api/register` - Register new user
- `POST /api/login` - Login user
- `GET /api/verify` - Verify JWT token

**Rooms:**
- `GET /api/rooms` - Get user's rooms
- `POST /api/rooms` - Create room
- `GET /api/rooms/{id}` - Get room details
- `POST /api/rooms/{id}/invite` - Invite user (creator only)
- `DELETE /api/rooms/{id}/members/{user_id}` - Remove user (creator only)
- `DELETE /api/rooms/{id}` - Delete room (creator only)

**Users:**
- `GET /api/users/online` - Get online users

### WebSocket Events

**Client → Server:**
- `authenticate` - Authenticate with JWT token
- `enter_room` - Enter a room
- `send_message` - Send message
- `typing_start` - Start typing
- `typing_stop` - Stop typing
- `leave_room` - Leave room

**Server → Client:**
- `authenticated` - Authentication success
- `auth_error` - Authentication failed
- `room_entered` - Room info and history
- `new_message` - New message broadcast
- `user_entered` - User joined room
- `user_left` - User left room
- `typing_update` - Typing users update
- `online_users_update` - Online users update
- `error` - Error message

## Notes

- Message history is stored in-memory (last 100 messages per room)
- Messages are lost on server restart, but rooms and memberships persist
- Only room creators can invite/remove members and delete rooms
- Users can only see rooms they are members of
- JWT tokens expire after 7 days
- Change the SECRET_KEY in auth.py for production use

## License

This is a personal project for educational purposes.
