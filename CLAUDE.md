# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Flask Real-Time Connect** — a full-stack social networking app with real-time private messaging, user authentication, and dynamic content (posts, profile pictures).

Stack:
- **Backend:** Python / Flask
- **Real-time:** Flask-SocketIO (WebSockets)
- **Database:** SQLAlchemy on SQLite (file in `instance/`)
- **Auth:** Flask-Login
- **Frontend:** Jinja2 templates, vanilla JS, CSS/Bootstrap

## Setup & Run

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python app.py                  # entry point
```

The README documents `python app.py` as the single command to start both the Flask server and the SocketIO server. There is no test suite, linter config, or CI config in the repo — do not invent commands for them.

## Documented Architecture

The README describes a `website/` Python package split into focused modules:

- `website/__init__.py` — Flask app factory and SocketIO initialization. This is where the app, `socketio`, `login_manager`, and `db` are wired together and where Blueprints are registered.
- `website/auth.py` — Blueprint for signup, login, logout (Flask-Login session handling).
- `website/views.py` — Blueprint for main site navigation (home, dashboards, profile pages).
- `website/posts.py` — Blueprint for creating/listing user posts.
- `website/dm.py` — Both HTTP routes for chat history/contacts **and** the SocketIO event handlers for real-time DMs. This is the only module that interacts with `socketio` directly beyond `__init__.py`.
- `website/models.py` — SQLAlchemy schemas: `User`, `Message`, and any post/profile models. All DB models live here.
- `website/static/js/dm.js` — Client-side Socket.IO logic for the DM UI.
- `website/static/uploads/` — User-uploaded media, split into `images/`, `profile_pics/`, `user_posts/`.
- `website/templates/` — Jinja2 templates.
- `app.py` — Thin entry point: imports the app/socketio from `website/__init__.py` and runs the dev server.
- `instance/` — SQLite database file lives here (Flask convention; usually gitignored).

## Key Architectural Notes

- **Room ID for DMs is deterministic.** Per the README, 1-on-1 chat rooms are generated deterministically from the two user IDs (so the same pair of users always lands in the same room and message history is unified). When working on `dm.py` / `dm.js`, preserve this property — do not generate a new room ID per session.
- **SocketIO is co-initialized with Flask** in `website/__init__.py` using `eventlet` (see `requirements.txt`). Use `socketio.emit` / `@socketio.on` patterns, not raw Flask `request` for chat payloads.
- **Auth is centralized in `auth.py`** with `@login_required` guards on protected routes. Profile-picture uploads and post creation both depend on a logged-in user; route handlers should rely on Flask-Login's `current_user` rather than re-reading session state.
- **Static uploads are served from `/static/uploads/...`** by Flask's default static handler; no custom upload-route serving is expected.

## Files Actually Present

In this working directory only these files exist:
- `README.md`
- `requirements.txt`
- `CLAUDE.md` (this file)

The Flask source code described in the README's project structure is not present in this directory. If you need to work on `app.py`, `website/`, or templates, they must be created or pulled in first — do not assume they exist on disk.

## Notes for Future Sessions

- No `.gitignore`, no Cursor rules, no Copilot instructions, no CI config, and no test framework are present. If asked to add tests, linting, or CI, set them up from scratch.
- The repository is not a git repository in this environment (no `.git` directory), so do not run git operations against it.
- Dependencies are pinned exactly in `requirements.txt` — match versions when adding or upgrading.
