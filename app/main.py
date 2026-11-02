import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("STUDY_DB_PATH", BASE_DIR / "study.db"))
SECRET = (os.environ.get("STUDY_SECRET") or secrets.token_hex(32)).encode()

app = FastAPI(title="Study Tasks and Attendance")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def connection():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            UNIQUE(user_id, day),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)


@app.on_event("startup")
def startup():
    init_db()


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return salt.hex() + ":" + digest.hex()


def password_matches(password: str, stored: str) -> bool:
    salt, digest = stored.split(":")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000)
    return hmac.compare_digest(actual.hex(), digest)


def token(user_id: int) -> str:
    value = str(user_id)
    signature = hmac.new(SECRET, value.encode(), hashlib.sha256).hexdigest()
    return value + "." + signature


def current_user(request: Request):
    raw = request.cookies.get("session")
    if not raw or "." not in raw:
        return None
    user_id, signature = raw.split(".", 1)
    if not user_id.isdigit() or not hmac.compare_digest(signature, hmac.new(SECRET, user_id.encode(), hashlib.sha256).hexdigest()):
        return None
    with connection() as db:
        return db.execute("SELECT id, username FROM users WHERE id = ?", (int(user_id),)).fetchone()


def require_user(request: Request):
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user


class Credentials(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=4, max_length=100)


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.post("/api/signup", status_code=201)
def signup(data: Credentials, response: Response):
    try:
        with connection() as db:
            cursor = db.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)", (data.username.strip(), password_hash(data.password)))
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")
    response.set_cookie("session", token(user_id), httponly=True, samesite="lax")
    return {"username": data.username.strip()}


@app.post("/api/login")
def login(data: Credentials, response: Response):
    with connection() as db:
        user = db.execute("SELECT * FROM users WHERE username = ?", (data.username.strip(),)).fetchone()
    if user is None or not password_matches(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    response.set_cookie("session", token(user["id"]), httponly=True, samesite="lax")
    return {"username": user["username"]}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    user = current_user(request)
    return {"username": user["username"]} if user else {"username": None}


@app.get("/api/tasks")
def list_tasks(request: Request):
    user = require_user(request)
    with connection() as db:
        rows = db.execute("SELECT id, title, completed FROM tasks WHERE user_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/tasks", status_code=201)
def add_task(data: TaskInput, request: Request):
    user = require_user(request)
    with connection() as db:
        cursor = db.execute("INSERT INTO tasks(user_id, title) VALUES (?, ?)", (user["id"], data.title.strip()))
    return {"id": cursor.lastrowid, "title": data.title.strip(), "completed": 0}


@app.patch("/api/tasks/{task_id}")
def complete_task(task_id: int, request: Request):
    user = require_user(request)
    with connection() as db:
        updated = db.execute("UPDATE tasks SET completed = 1 WHERE id = ? AND user_id = ?", (task_id, user["id"])).rowcount
    if not updated:
        raise HTTPException(status_code=404, detail="할 일을 찾을 수 없습니다.")
    return {"ok": True}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, request: Request):
    user = require_user(request)
    with connection() as db:
        deleted = db.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user["id"])).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="할 일을 찾을 수 없습니다.")
    return {"ok": True}


@app.post("/api/attendance/today")
def check_attendance(request: Request):
    user = require_user(request)
    from datetime import date
    day = date.today().isoformat()
    with connection() as db:
        db.execute("INSERT OR IGNORE INTO attendance(user_id, day) VALUES (?, ?)", (user["id"], day))
    return {"day": day, "checked": True}


@app.get("/api/attendance")
def list_attendance(request: Request):
    user = require_user(request)
    with connection() as db:
        rows = db.execute("SELECT day FROM attendance WHERE user_id = ? ORDER BY day DESC", (user["id"],)).fetchall()
    return [row["day"] for row in rows]

