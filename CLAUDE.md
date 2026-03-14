# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Run the application:**
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Test API endpoints:**
```bash
# Register a user
curl -X POST http://localhost:8000/api/register -H "Content-Type: application/json" -d '{"username":"testuser","password":"password123"}'

# Login
curl -X POST http://localhost:8000/api/login -H "Content-Type: application/json" -d '{"username":"testuser","password":"password123"}'

# Get rooms (requires token from login/register response)
curl "http://localhost:8000/api/rooms?token=YOUR_TOKEN_HERE"
```

**Database inspection:**
```bash
# View tables
sqlite3 chat.db ".tables"

# Query users
sqlite3 chat.db "SELECT id, username FROM users;"

# Query rooms
sqlite3 chat.db "SELECT id, name, creator_id FROM rooms;"
```

## Architecture Overview

### Dual-Layer Data Model

The application uses a **hybrid persistence model** that splits data between persistent storage and in-memory state:

**Persistent (SQLite via database.py):**
- User accounts (username, password_hash)
- Room definitions (name, creator_id)
- Room memberships (many-to-many relationship)
- Message history (id, room_id, user_id, username, content, timestamp)

**In-Memory (models.py ChatStore):**
- Online users (session_id → OnlineUser mapping)
- Typing indicators (room_id → Set[user_id])

Messages are **persisted to the database** and loaded when entering a room. The in-memory deque (maxlen=100) serves as a cache for the current session. When modifying message-related features, work with both `database.py` (persistence) and `models.py` (in-memory cache). When modifying user/room management, work with `database.py`.

### Request Flow

**REST API Flow (app.py):**
1. Client sends HTTP request with JWT token (in query param or body)
2. `verify_token()` extracts user_id from JWT
3. Database functions validate permissions (e.g., `is_room_member()`)
4. Response returned via FastAPI

**WebSocket Flow (app.py):**
1. Client connects and sends `authenticate` event with JWT token
2. Server validates token and adds user to `chat_store.online_users`
3. Client sends events (e.g., `enter_room`, `send_message`)
4. Server validates user state (e.g., `current_room_id`) and broadcasts to room
5. Room-scoped broadcasts use Socket.IO rooms (e.g., `room_{room_id}`)

### Authentication & Authorization

**JWT Token Flow:**
- Tokens created in `auth.py` with 7-day expiration
- Token contains `user_id` in payload
- REST endpoints verify via `verify_token()` and query param
- WebSocket authenticates once on connect, then tracks via `session_id`

**Authorization Patterns:**
- Room membership: Check `is_room_member(db, room_id, user_id)` before allowing access
- Creator-only actions: Compare `room.creator_id == user_id` for invite/kick/delete
- Online user tracking: Map Socket.IO `session_id` to authenticated `user_id`

### Frontend State Machine

The single-page frontend (`static/index.html`) operates as a state machine with four screens:

1. **auth**: Login/register commands only
2. **room_list**: Room browsing, creation, online users
3. **chat**: Active in a room, sending messages
4. **settings**: Room management (creator only)

Commands are parsed and routed based on `state.currentScreen`. The terminal UI is purely cosmetic—all functionality is command-driven.

## Key Implementation Details

### Socket.IO Room Management

Socket.IO "rooms" (not to be confused with chat rooms) are used for targeted broadcasts:
- Users join Socket.IO room `room_{room_id}` when entering a chat room
- Broadcasts use `sio.emit('event', data, room=f"room_{room_id}")` to target room members
- Users must leave Socket.IO room when exiting chat room to stop receiving messages

### Database Session Handling

Database sessions are created per-request via `get_db()` dependency injection for REST endpoints. For WebSocket handlers, sessions are manually created:
```python
db = next(get_db())
# ... use db ...
db.close()
```

Always close sessions in WebSocket handlers to prevent connection leaks.

### Message Persistence

Messages are persisted to the SQLite database and loaded when users enter a room:
- Messages table stores: id, room_id, user_id, username, content, timestamp
- On room entry, the last 100 messages are loaded from the database
- New messages are saved to both the database and in-memory deque
- The in-memory deque (maxlen=100) serves as a cache for the current session
- Messages survive server restarts and page refreshes

When adding message-related features:
1. Update the Message model in `database.py` if changing schema
2. Modify `save_message()` in `database.py` for persistence logic
3. Update `chat_store.add_message()` in `models.py` for in-memory cache
4. Update the `enter_room` handler in `app.py` to load messages correctly

### Terminal UI Disguise

The frontend is designed to look like a debugging console, not a chat app. When modifying the UI:
- Colors are defined as CSS variables (`--primary-color`, `--secondary-color`, `--bg-color`, etc.) — do not hardcode hex values
- Use monospace font (Courier New)
- Keep command-line interface (no buttons or modern UI elements)
- Display messages with timestamps in `[HH:MM:SS]` format
- Use terminal-style output (append lines, no chat bubbles)

### Color Theme System

Six themes are available and switchable at runtime via `/theme <name>`: `green` (default), `amber`, `blue`, `white`, `purple`, `red`.

- CSS variables are swapped on `<body>` to change themes; no page reload needed
- Theme preference is saved to `localStorage` under the key `terminalTheme` and applied on page load
- The `/theme` command is available on all screens (auth, room_list, chat, settings)
- When adding new styled elements, always use CSS variables (`var(--primary-color)`) instead of hardcoded colors

### Password Change Flow

Users can change their password from any authenticated screen with `/passwd`. The flow is multi-step:

1. Prompt for old password (hidden with asterisks)
2. Prompt for new password (hidden)
3. Prompt to confirm new password (hidden)
4. POST to `/api/change-password` with `{token, old_password, new_password}`

The backend (`database.py`: `update_user_password()`) verifies the old password via bcrypt before updating. State flags (`state.awaitingOldPassword`, `state.awaitingNewPassword`, `state.awaitingConfirmPassword`) drive the multi-step input, following the Confirmation Flow Pattern.

### Confirmation Flow Pattern

For multi-step operations requiring user confirmation (like room deletion), use state flags instead of overriding input handlers:

**Pattern:**
```javascript
// In command handler:
if (command === '/delete-room') {
    print('Are you sure? Type "yes" to confirm:');
    state.awaitingDeleteConfirmation = true;
    return;
}

// At the start of the same handler:
if (state.awaitingDeleteConfirmation) {
    state.awaitingDeleteConfirmation = false;
    if (command.toLowerCase() === 'yes') {
        // Perform the action
    } else {
        print('Cancelled');
    }
    return;
}
```

**Why this pattern:**
- Overriding `input.onkeydown` conflicts with the normal command processing flow
- State flags integrate cleanly with the existing command routing
- Easier to debug and maintain

### Cache-Busting Headers

The root endpoint (`/`) serves `static/index.html` with cache-busting headers to prevent browser caching issues:
```python
response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
response.headers["Pragma"] = "no-cache"
response.headers["Expires"] = "0"
```

This ensures users always get the latest frontend code without manual hard refresh.

## Security Considerations

**Production Deployment:**
- Change `SECRET_KEY` in `auth.py` (currently hardcoded)
- Set `cors_allowed_origins` in Socket.IO to specific domains (currently `'*'`)
- Use HTTPS in production (JWT tokens transmitted in URLs)
- Consider rate limiting on registration/login endpoints

**Password Security:**
- Bcrypt with 12 salt rounds (in `auth.py`)
- Never log or expose password_hash values
- JWT tokens are bearer tokens—treat as sensitive

## Common Modifications

**Adding a new REST endpoint:**
1. Define Pydantic request/response models at top of `app.py`
2. Add endpoint function with `@app.get/post/delete` decorator
3. Use `token: str` parameter and `verify_token()` for authentication
4. Use `db: Session = Depends(get_db)` for database access

**Adding a new WebSocket event:**
1. Add `@sio.event` handler in `app.py`
2. Get user via `chat_store.get_online_user(sid)`
3. Validate user state (e.g., check `user.current_room_id`)
4. Broadcast to room using `sio.emit('event', data, room=f"room_{room_id}")`

**Modifying database schema:**
1. Update SQLAlchemy models in `database.py`
2. Write a migration in `migrate.py` using `sqlite3.connect("chat.db")` and `ALTER TABLE` statements
3. Run `python migrate.py` to apply the migration without losing data
4. Restart the server

If starting fresh (no data to preserve), you can still delete `chat.db` and restart — `init_db()` will recreate all tables.
