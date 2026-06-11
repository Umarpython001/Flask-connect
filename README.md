# 💬 Flask Real-Time Connect

A full-stack social networking application with real-time messaging, friend connections, and group chat rooms — built with Flask and WebSockets.

---

## 🚀 Features

### 👤 Authentication & Profiles
- Secure user signup, login, and logout via **Flask-Login**
- Session management with protected routes
- Custom profile picture uploads and user-specific dashboards

### 🤝 Friend Requests
- Send, accept, and decline friend requests to other users
- Friends list visible on your profile and dashboard
- Only friends can initiate direct message conversations

### 💬 Direct Messaging (1-on-1 DMs)
- Instant private messaging powered by **Flask-SocketIO** (WebSockets)
- Deterministic room logic — the same two users always share the same chat room, so message history is seamlessly unified across sessions
- Auto-scrolling chat UI with real-time message bubbles
- Persistent message history stored in the database

### 🏠 Room DMs (Group Chat)
- Create and join named chat rooms for group conversations
- Real-time messaging with multiple participants in a single room
- Room-based Socket.IO event handling — each room is an isolated channel

### 📸 Posts & Media
- Create and share posts with image attachments
- User-specific post feeds on profile dashboards
- Uploaded media served from Flask's static file handler

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.8+, Flask |
| Real-Time | Flask-SocketIO, Socket.IO (WebSockets via eventlet) |
| Database | SQLAlchemy + SQLite |
| Auth | Flask-Login |
| Frontend | Jinja2 templates, Vanilla JavaScript (ES6), CSS / Bootstrap |

---

## 📁 Project Structure

```
Flask-connect/
├── instance/                        # SQLite database (auto-created on first run)
├── website/
│   ├── static/
│   │   ├── css/                     # Stylesheets
│   │   ├── js/
│   │   │   └── dm.js                # Client-side Socket.IO logic for DMs & rooms
│   │   └── uploads/
│   │       ├── images/              # App image assets (default avatars, icons, etc.)
│   │       ├── profile_pics/        # User-uploaded profile pictures
│   │       └── user_posts/          # User-uploaded post images
│   ├── templates/                   # Jinja2 HTML templates
│   ├── __init__.py                  # App factory — wires Flask, SocketIO, DB, and Blueprints
│   ├── auth.py                      # Signup / login / logout (Blueprint)
│   ├── views.py                     # Home, dashboard, profile pages (Blueprint)
│   ├── posts.py                     # Post creation and feed logic (Blueprint)
│   ├── dm.py                        # DM routes, room routes, and all SocketIO event handlers
│   └── models.py                    # SQLAlchemy schemas: User, Message, FriendRequest, Room, etc.
├── app.py                           # Entry point
├── requirements.txt                 # Pinned dependencies
└── .gitignore
```

---

## ⚙️ Local Setup

### Prerequisites
- Python 3.8+
- pip

### Steps

**1. Clone the repository**
```bash
git clone https://github.com/Umarpython001/Flask-connect.git
cd Flask-connect
```

**2. Create and activate a virtual environment**
```bash
# Create
python -m venv venv

# Activate — Windows
venv\Scripts\activate

# Activate — macOS / Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Run the development server**
```bash
python app.py
```

The app will be available at `http://localhost:5000`.

> **Note:** `app.py` uses `eventlet.monkey_patch()` as its very first statement, which is required for Flask-SocketIO's WebSocket transport to work correctly with eventlet. Do not move or remove it.

---

## 🗺️ Roadmap

- [ ] Video post support
- [ ] Fix chat sync bug on reconnect

---

## 🏗️ Architecture Notes

- **Deterministic DM rooms** — Room IDs for 1-on-1 chats are generated from both user IDs, so the same pair always lands in the same room regardless of who initiates.
- **Single SocketIO instance** — `socketio` is initialized once in `website/__init__.py` alongside the Flask app. All socket event handlers in `dm.py` use `@socketio.on` decorators and `socketio.emit`.
- **Blueprint-based routing** — Each concern (auth, views, posts, DMs/rooms) is a separate Flask Blueprint registered in the app factory.
- **Static file uploads** — Profile pictures and post images are written to `website/static/uploads/` and served by Flask's default static handler.