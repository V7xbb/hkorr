from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import random
import string
import json
import hashlib
import secrets
import os

app = FastAPI(title="XO Game Server", version="3.0")

# ============ CORS ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ الملفات ============
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
AUTH_FILE = DATA_DIR / "auth.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"
MATCHES_FILE = DATA_DIR / "matches.json"
GLOBAL_CHAT_FILE = DATA_DIR / "global_chat.json"

# ============ تحميل البيانات ============
def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return default
    except:
        return default

def save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"خطأ في الحفظ: {e}")

# ============ البيانات ============
users: Dict[str, dict] = load_json(USERS_FILE, {})
auth_users: Dict[str, dict] = load_json(AUTH_FILE, {})   # keyed by user_id
sessions: Dict[str, dict] = load_json(SESSIONS_FILE, {}) # token -> {user_id, expires}
matches: List[dict] = load_json(MATCHES_FILE, [])
global_chat: List[dict] = load_json(GLOBAL_CHAT_FILE, [])
rooms: Dict[str, dict] = {}
connections: Dict[str, Dict[str, WebSocket]] = {}
global_connections: Dict[str, WebSocket] = {}  # user_id -> WebSocket

# ============ الأدوات ============
def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def generate_id(length=12):
    return secrets.token_hex(length // 2)

def now_iso():
    return datetime.utcnow().isoformat()

def hash_password(password: str, salt: str = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    return (salt, pwd_hash)

def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    _, computed = hash_password(password, salt)
    return secrets.compare_digest(computed, stored_hash)

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    sessions[token] = {"user_id": user_id, "expires": expires, "created": now_iso()}
    save_json(SESSIONS_FILE, sessions)
    return token

def get_user_from_token(token: str) -> Optional[dict]:
    sess = sessions.get(token)
    if not sess:
        return None
    if datetime.fromisoformat(sess["expires"]) < datetime.utcnow():
        del sessions[token]
        save_json(SESSIONS_FILE, sessions)
        return None
    uid = str(sess["user_id"])
    return users.get(uid)

def get_or_create_user(user_id: int, name: str = "Player", username: str = ""):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "id": user_id,
            "name": name,
            "username": username,
            "email": "",
            "points": 0,
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "streak": 0,
            "best_streak": 0,
            "owned_skins": ["gold"],
            "current_skin": "gold",
            "owned_items": {},
            "current_items": {},
            "created_at": now_iso(),
            "last_seen": now_iso(),
            "is_registered": False,
        }
        save_users()
    else:
        users[uid]["last_seen"] = now_iso()
        if name and name != "Player":
            users[uid]["name"] = name
    return users[uid]

def save_users():
    save_json(USERS_FILE, users)

def save_matches():
    global matches
    matches = matches[-200:]
    save_json(MATCHES_FILE, matches)

def add_points(user_id: int, points: int):
    uid = str(user_id)
    if uid in users:
        users[uid]["points"] = max(0, users[uid].get("points", 0) + points)
        save_users()

def record_match(player_x: int, player_o: int, winner: str, moves: List[int], room_code: str = None):
    match = {
        "id": len(matches) + 1,
        "player_x": player_x,
        "player_o": player_o,
        "winner": winner,
        "moves": moves,
        "room_code": room_code,
        "timestamp": now_iso(),
    }
    matches.append(match)
    save_matches()

    for pid in [player_x, player_o]:
        uid = str(pid)
        if uid in users:
            users[uid]["games"] = users[uid].get("games", 0) + 1

    if winner == "X" and str(player_x) in users:
        users[str(player_x)]["wins"] = users[str(player_x)].get("wins", 0) + 1
        users[str(player_x)]["streak"] = users[str(player_x)].get("streak", 0) + 1
        users[str(player_x)]["best_streak"] = max(
            users[str(player_x)].get("best_streak", 0),
            users[str(player_x)]["streak"]
        )
        if str(player_o) in users:
            users[str(player_o)]["losses"] = users[str(player_o)].get("losses", 0) + 1
            users[str(player_o)]["streak"] = 0
        add_points(player_x, 50)
        add_points(player_o, 10)
    elif winner == "O" and str(player_o) in users:
        users[str(player_o)]["wins"] = users[str(player_o)].get("wins", 0) + 1
        users[str(player_o)]["streak"] = users[str(player_o)].get("streak", 0) + 1
        users[str(player_o)]["best_streak"] = max(
            users[str(player_o)].get("best_streak", 0),
            users[str(player_o)]["streak"]
        )
        if str(player_x) in users:
            users[str(player_x)]["losses"] = users[str(player_x)].get("losses", 0) + 1
            users[str(player_x)]["streak"] = 0
        add_points(player_o, 50)
        add_points(player_x, 10)
    elif winner == "draw":
        if str(player_x) in users:
            users[str(player_x)]["draws"] = users[str(player_x)].get("draws", 0) + 1
        if str(player_o) in users:
            users[str(player_o)]["draws"] = users[str(player_o)].get("draws", 0) + 1
        add_points(player_x, 25)
        add_points(player_o, 25)

    save_users()

def check_winner(board: List[str]) -> Optional[str]:
    wins = [
        [0,1,2],[3,4,5],[6,7,8],
        [0,3,6],[1,4,7],[2,5,8],
        [0,4,8],[2,4,6]
    ]
    for a,b,c in wins:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None

# ============================================================
# الصفحة الرئيسية
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def root():
    for path in ["index.html", "static/index.html"]:
        f = Path(path)
        if f.exists():
            return f.read_text(encoding="utf-8")
    return "<h1>XO Server</h1><p>index.html not found</p>"

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "users": len(users),
        "registered_users": sum(1 for u in users.values() if u.get("is_registered")),
        "rooms": len(rooms),
        "matches": len(matches),
        "timestamp": now_iso(),
    }

# ============================================================
# 🔐 نظام التسجيل (Registration / Auth)
# ============================================================

class RegisterReq(BaseModel):
    email: str
    username: str
    password: str

class LoginReq(BaseModel):
    email: str
    password: str

@app.post("/api/auth/register")
async def register(req: RegisterReq):
    email = req.email.strip().lower()
    username = req.username.strip()
    password = req.password

    # Validate
    if not email or "@" not in email:
        raise HTTPException(400, "البريد الإلكتروني غير صحيح")
    if len(username) < 3:
        raise HTTPException(400, "اسم المستخدم لازم 3 أحرف على الأقل")
    if len(password) < 6:
        raise HTTPException(400, "كلمة السر لازم 6 أحرف على الأقل")

    # Check email exists
    for uid, u in users.items():
        if u.get("email", "").lower() == email:
            raise HTTPException(400, "البريد الإلكتروني مستخدم بالفعل")

    # Create user with new ID
    new_id = int(datetime.utcnow().timestamp() * 1000) % 1000000000
    while str(new_id) in users:
        new_id += 1

    salt, pwd_hash = hash_password(password)

    users[str(new_id)] = {
        "id": new_id,
        "name": username,
        "username": username,
        "email": email,
        "password_salt": salt,
        "password_hash": pwd_hash,
        "points": 500,  # welcome bonus
        "games": 0, "wins": 0, "losses": 0, "draws": 0,
        "streak": 0, "best_streak": 0,
        "owned_skins": ["gold"],
        "current_skin": "gold",
        "owned_items": {},
        "current_items": {},
        "created_at": now_iso(),
        "last_seen": now_iso(),
        "is_registered": True,
    }
    save_users()

    token = create_session(new_id)
    user = users[str(new_id)]
    # Don't send password data
    user_data = {k: v for k, v in user.items() if not k.startswith("password_")}

    return {"success": True, "token": token, "user": user_data}

@app.post("/api/auth/login")
async def login(req: LoginReq):
    email = req.email.strip().lower()
    password = req.password

    # Find user by email
    found_user = None
    for uid, u in users.items():
        if u.get("email", "").lower() == email:
            found_user = u
            break

    if not found_user:
        raise HTTPException(401, "البريد الإلكتروني أو كلمة السر غير صحيحة")

    salt = found_user.get("password_salt", "")
    stored_hash = found_user.get("password_hash", "")
    if not salt or not stored_hash:
        raise HTTPException(401, "هذا الحساب غير مسجل، يرجى التسجيل أولاً")

    if not verify_password(password, salt, stored_hash):
        raise HTTPException(401, "البريد الإلكتروني أو كلمة السر غير صحيحة")

    token = create_session(found_user["id"])
    user_data = {k: v for k, v in found_user.items() if not k.startswith("password_")}
    return {"success": True, "token": token, "user": user_data}

@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token in sessions:
        del sessions[token]
        save_json(SESSIONS_FILE, sessions)
    return {"success": True}

@app.get("/api/auth/me")
async def me(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "غير مسجل الدخول")
    user_data = {k: v for k, v in user.items() if not k.startswith("password_")}
    return user_data

# ============================================================
# المستخدمين
# ============================================================

class UserReq(BaseModel):
    user_id: int
    name: str = "Player"
    username: str = ""

@app.post("/api/user/register")
async def register_guest(req: UserReq):
    """تسجيل ضيف (بدون تسجيل)"""
    user = get_or_create_user(req.user_id, req.name, req.username)
    user_data = {k: v for k, v in user.items() if not k.startswith("password_")}
    return user_data

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    uid = str(user_id)
    if uid not in users:
        raise HTTPException(404, "المستخدم غير موجود")
    user_data = {k: v for k, v in users[uid].items() if not k.startswith("password_")}
    return user_data

@app.get("/api/leaderboard")
async def leaderboard(limit: int = 20):
    sorted_users = sorted(
        users.values(),
        key=lambda u: (u.get("points", 0), u.get("wins", 0)),
        reverse=True
    )[:limit]
    return [
        {
            "rank": i + 1,
            "id": u["id"],
            "name": u.get("name", "Player"),
            "username": u.get("username", ""),
            "points": u.get("points", 0),
            "wins": u.get("wins", 0),
            "games": u.get("games", 0),
        }
        for i, u in enumerate(sorted_users)
    ]

# ============================================================
# 🏠 الغرف + الحفلات (Spectators)
# ============================================================

class CreateRoomReq(BaseModel):
    player_id: int
    player_name: str = "Player"
    is_party: bool = False  # هل هي حفلة (تسمح بمشاهدين)

class JoinRoomReq(BaseModel):
    player_id: int
    player_name: str = "Player"
    as_spectator: bool = False

@app.post("/api/rooms/create")
async def create_room(req: CreateRoomReq):
    get_or_create_user(req.player_id, req.player_name)
    code = generate_code()
    while code in rooms:
        code = generate_code()

    rooms[code] = {
        "code": code,
        "host_id": req.player_id,
        "host_name": req.player_name,
        "guest_id": None,
        "guest_name": None,
        "board": [" "] * 9,
        "turn": "X",
        "status": "waiting",
        "winner": None,
        "moves": [],
        "spectators": [],  # list of {id, name}
        "messages": [],    # chat in room
        "is_party": req.is_party,
        "started_at": None,
        "created_at": now_iso(),
    }
    return {"code": code, "room": rooms[code]}

@app.post("/api/rooms/join/{code}")
async def join_room(code: str, req: JoinRoomReq):
    code = code.upper()
    get_or_create_user(req.player_id, req.player_name)

    if code not in rooms:
        raise HTTPException(404, "الغرفة غير موجودة")

    room = rooms[code]

    # Already in game
    if room["host_id"] == req.player_id:
        return {"code": code, "room": room, "role": "host"}
    if room["guest_id"] == req.player_id:
        return {"code": code, "room": room, "role": "guest"}

    # Already spectator
    for s in room["spectators"]:
        if s["id"] == req.player_id:
            return {"code": code, "room": room, "role": "spectator"}

    # Try to join as guest
    if not req.as_spectator and room["guest_id"] is None and room["status"] != "finished":
        room["guest_id"] = req.player_id
        room["guest_name"] = req.player_name
        room["status"] = "playing"
        room["started_at"] = now_iso()
        return {"code": code, "room": room, "role": "guest"}

    # Join as spectator (if party or room full)
    if room["is_party"] or room["guest_id"] is not None:
        room["spectators"].append({"id": req.player_id, "name": req.player_name, "joined_at": now_iso()})
        return {"code": code, "room": room, "role": "spectator"}

    raise HTTPException(400, "الغرفة ممتلئة")

@app.get("/api/rooms/{code}")
async def get_room(code: str):
    code = code.upper()
    if code not in rooms:
        raise HTTPException(404, "الغرفة غير موجودة")
    return rooms[code]

@app.get("/api/rooms")
async def list_rooms():
    return [
        {
            "code": r["code"],
            "host": r["host_name"],
            "status": r["status"],
            "spectators": len(r["spectators"]),
            "is_party": r["is_party"],
        }
        for r in rooms.values()
        if r["status"] in ("waiting", "playing") and not r["is_party"]
    ]

@app.get("/api/parties")
async def list_parties():
    """قائمة الحفلات المتاحة"""
    return [
        {
            "code": r["code"],
            "host": r["host_name"],
            "status": r["status"],
            "spectators": len(r["spectators"]),
        }
        for r in rooms.values()
        if r["is_party"] and r["status"] in ("waiting", "playing")
    ]

# ============================================================
# 🌐 الشات العام
# ============================================================

class ChatReq(BaseModel):
    user_id: int
    name: str
    text: str

@app.post("/api/chat/global/send")
async def global_send(req: ChatReq):
    text = req.text.strip()[:200]
    if not text:
        raise HTTPException(400, "الرسالة فاضية")

    msg = {
        "id": len(global_chat) + 1,
        "user_id": req.user_id,
        "name": req.name,
        "text": text,
        "timestamp": now_iso(),
    }
    global_chat.append(msg)
    # keep last 200
    if len(global_chat) > 200:
        global_chat.pop(0)
    save_json(GLOBAL_CHAT_FILE, global_chat)

    # broadcast to all global connections
    for uid, ws in list(global_connections.items()):
        try:
            await ws.send_json({"type": "global_chat", "message": msg})
        except:
            pass

    return {"success": True, "message": msg}

@app.get("/api/chat/global/messages")
async def global_messages(limit: int = 50):
    return global_chat[-limit:]

# ============================================================
# WebSocket
# ============================================================

@app.websocket("/ws/{code}/{player_id}")
async def ws_endpoint(ws: WebSocket, code: str, player_id: int):
    code = code.upper()
    pid = str(player_id)

    await ws.accept()

    if code not in connections:
        connections[code] = {}
    connections[code][pid] = ws

    try:
        if code in rooms:
            room = rooms[code]
            role = "spectator"
            if room["host_id"] == player_id:
                role = "host"
            elif room["guest_id"] == player_id:
                role = "guest"

            await ws.send_json({
                "type": "welcome",
                "room": room,
                "role": role,
            })

            await broadcast(code, {
                "type": "player_joined",
                "player_id": player_id,
            }, exclude=player_id)

        while True:
            data = await ws.receive_json()
            await handle_message(code, player_id, ws, data)

    except WebSocketDisconnect:
        if code in connections:
            connections[code].pop(pid, None)
            if not connections[code]:
                del connections[code]

        # remove from spectators if was one
        if code in rooms:
            room = rooms[code]
            room["spectators"] = [s for s in room["spectators"] if s["id"] != player_id]

        await broadcast(code, {
            "type": "player_left",
            "player_id": player_id,
        })

async def handle_message(code: str, player_id: int, ws: WebSocket, data: dict):
    msg_type = data.get("type")

    if code not in rooms:
        await ws.send_json({"type": "error", "message": "الغرفة غير موجودة"})
        return

    room = rooms[code]

    if msg_type == "move":
        # Only players can move
        if player_id not in (room["host_id"], room["guest_id"]):
            await ws.send_json({"type": "error", "message": "أنت مشاهد فقط"})
            return

        if room["status"] != "playing":
            await ws.send_json({"type": "error", "message": "اللعبة لم تبدأ"})
            return

        expected_player = room["host_id"] if room["turn"] == "X" else room["guest_id"]
        if player_id != expected_player:
            await ws.send_json({"type": "error", "message": "ليس دورك"})
            return

        index = data.get("index")
        if not isinstance(index, int) or index < 0 or index > 8:
            return
        if room["board"][index] != " ":
            return

        room["board"][index] = room["turn"]
        room["moves"].append(index)

        winner = check_winner(room["board"])
        if winner:
            room["winner"] = winner
            room["status"] = "finished"
            record_match(room["host_id"], room["guest_id"], winner, room["moves"], code)
        elif " " not in room["board"]:
            room["winner"] = "draw"
            room["status"] = "finished"
            record_match(room["host_id"], room["guest_id"], "draw", room["moves"], code)
        else:
            room["turn"] = "O" if room["turn"] == "X" else "X"

        await broadcast(code, {"type": "room_update", "room": room})

    elif msg_type == "restart":
        if player_id not in (room["host_id"], room["guest_id"]):
            return
        if room["status"] == "finished":
            room["board"] = [" "] * 9
            room["turn"] = "X"
            room["status"] = "playing"
            room["winner"] = None
            room["moves"] = []
            room["started_at"] = now_iso()
            await broadcast(code, {"type": "room_update", "room": room})

    elif msg_type == "chat":
        text = str(data.get("text", ""))[:200].strip()
        if not text:
            return
        user = users.get(str(player_id), {})
        msg = {
            "id": len(room["messages"]) + 1,
            "player_id": player_id,
            "player_name": user.get("name", "Player"),
            "text": text,
            "timestamp": now_iso(),
        }
        room["messages"].append(msg)
        if len(room["messages"]) > 100:
            room["messages"].pop(0)
        await broadcast(code, {"type": "chat", "message": msg})

    elif msg_type == "forfeit":
        if player_id not in (room["host_id"], room["guest_id"]):
            return
        if room["status"] != "playing":
            return
        winner = "O" if player_id == room["host_id"] else "X"
        room["winner"] = winner
        room["status"] = "finished"
        record_match(room["host_id"], room["guest_id"], winner, room["moves"], code)
        await broadcast(code, {"type": "room_update", "room": room, "forfeit": True})

async def broadcast(code: str, msg: dict, exclude: Optional[int] = None):
    if code not in connections:
        return
    for pid_str, ws in list(connections[code].items()):
        if exclude is not None and pid_str == str(exclude):
            continue
        try:
            await ws.send_json(msg)
        except:
            pass

# ============================================================
# WebSocket للشات العام
# ============================================================

@app.websocket("/ws/global/{user_id}")
async def global_ws(ws: WebSocket, user_id: int):
    await ws.accept()
    global_connections[str(user_id)] = ws
    try:
        # Send recent messages
        await ws.send_json({"type": "history", "messages": global_chat[-50:]})
        while True:
            data = await ws.receive_json()
            if data.get("type") == "chat":
                text = str(data.get("text", ""))[:200].strip()
                if not text:
                    continue
                user = users.get(str(user_id), {})
                msg = {
                    "id": len(global_chat) + 1,
                    "user_id": user_id,
                    "name": user.get("name", "Player"),
                    "text": text,
                    "timestamp": now_iso(),
                }
                global_chat.append(msg)
                if len(global_chat) > 200:
                    global_chat.pop(0)
                save_json(GLOBAL_CHAT_FILE, global_chat)
                # broadcast to all
                for uid, cws in list(global_connections.items()):
                    try:
                        await cws.send_json({"type": "global_chat", "message": msg})
                    except:
                        pass
    except WebSocketDisconnect:
        global_connections.pop(str(user_id), None)

# ============================================================
# الإحصائيات لكل مستخدم
# ============================================================

@app.get("/api/user/{user_id}/stats")
async def user_stats(user_id: int):
    uid = str(user_id)
    if uid not in users:
        raise HTTPException(404, "المستخدم غير موجود")
    u = users[uid]
    total = u.get("games", 0)
    wins = u.get("wins", 0)
    win_rate = round((wins / total * 100) if total > 0 else 0, 1)
    return {
        "user_id": user_id,
        "name": u.get("name"),
        "points": u.get("points", 0),
        "games": total,
        "wins": wins,
        "losses": u.get("losses", 0),
        "draws": u.get("draws", 0),
        "win_rate": win_rate,
        "streak": u.get("streak", 0),
        "best_streak": u.get("best_streak", 0),
    }

# ============================================================
# آخر المباريات
# ============================================================

@app.get("/api/matches/recent")
async def recent_matches(limit: int = 20):
    return matches[-limit:][::-1]
