from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import random
import string
import json
import asyncio
import os

app = FastAPI(title="XO Game Server", version="2.0")

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
MATCHES_FILE = DATA_DIR / "matches.json"
ROOMS_FILE = DATA_DIR / "rooms.json"

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
matches: List[dict] = load_json(MATCHES_FILE, [])
rooms: Dict[str, dict] = {}
connections: Dict[str, Dict[str, WebSocket]] = {}

# ============ الأدوات ============
def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def now_iso():
    return datetime.utcnow().isoformat()

def get_or_create_user(user_id: int, name: str = "Player", username: str = ""):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "id": user_id,
            "name": name,
            "username": username,
            "points": 0,
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "streak": 0,
            "best_streak": 0,
            "owned_skins": ["classic"],
            "current_skin": "classic",
            "created_at": now_iso(),
            "last_seen": now_iso(),
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
    matches = matches[-100:]
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
    
    # تحديث الإحصائيات
    for pid in [player_x, player_o]:
        uid = str(pid)
        if uid in users:
            users[uid]["games"] = users[uid].get("games", 0) + 1
    
    # الفائز
    if winner == "X" and str(player_x) in users:
        users[str(player_x)]["wins"] = users[str(player_x)].get("wins", 0) + 1
        users[str(player_x)]["streak"] = users[str(player_x)].get("streak", 0) + 1
        users[str(player_x)]["best_streak"] = max(
            users[str(player_x)].get("best_streak", 0),
            users[str(player_x)]["streak"]
        )
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

# ============ API ============

@app.get("/", response_class=HTMLResponse)
async def root():
    index_file = Path("static/index.html")
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>XO Server</h1><p>التطبيق في /static/index.html</p>"

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "users": len(users),
        "rooms": len(rooms),
        "matches": len(matches),
        "timestamp": now_iso(),
    }

# ========== المستخدمين ==========

class UserReq(BaseModel):
    user_id: int
    name: str = "Player"
    username: str = ""

@app.post("/api/user/register")
async def register_user(req: UserReq):
    user = get_or_create_user(req.user_id, req.name, req.username)
    return user

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    uid = str(user_id)
    if uid not in users:
        raise HTTPException(404, "المستخدم غير موجود")
    return users[uid]

@app.get("/api/leaderboard")
async def leaderboard(limit: int = 10):
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
            "points": u.get("points", 0),
            "wins": u.get("wins", 0),
        }
        for i, u in enumerate(sorted_users)
    ]

@app.get("/api/user/{user_id}/matches")
async def user_matches(user_id: int, limit: int = 10):
    user_matches = [
        m for m in matches
        if m["player_x"] == user_id or m["player_o"] == user_id
    ]
    return user_matches[-limit:]

# ========== الغرف ==========

class CreateRoomReq(BaseModel):
    player_id: int
    player_name: str = "Player"

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
        "started_at": None,
        "created_at": now_iso(),
        "spectators": [],
    }
    
    return {"code": code, "room": rooms[code]}

class JoinRoomReq(BaseModel):
    player_id: int
    player_name: str = "Player"

@app.post("/api/rooms/join/{code}")
async def join_room(code: str, req: JoinRoomReq):
    code = code.upper()
    get_or_create_user(req.player_id, req.player_name)
    
    if code not in rooms:
        raise HTTPException(404, "الغرفة غير موجودة")
    
    room = rooms[code]
    
    if room["host_id"] == req.player_id:
        return {"code": code, "room": room, "role": "host"}
    
    if room["guest_id"] == req.player_id:
        return {"code": code, "room": room, "role": "guest"}
    
    if room["guest_id"] is not None:
        raise HTTPException(400, "الغرفة ممتلئة")
    
    if room["status"] == "finished":
        raise HTTPException(400, "اللعبة انتهت")
    
    room["guest_id"] = req.player_id
    room["guest_name"] = req.player_name
    room["status"] = "playing"
    room["started_at"] = now_iso()
    
    return {"code": code, "room": room, "role": "guest"}

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
            "spectators": len(r.get("spectators", [])),
        }
        for r in rooms.values()
        if r["status"] == "waiting"
    ]

# ========== WebSocket ==========

@app.websocket("/ws/{code}/{player_id}")
async def ws_endpoint(ws: WebSocket, code: str, player_id: int):
    code = code.upper()
    pid = str(player_id)
    
    await ws.accept()
    
    if code not in connections:
        connections[code] = {}
    connections[code][pid] = ws
    
    try:
        # إرسال حالة الغرفة الحالية
        if code in rooms:
            role = "spectator"
            if rooms[code]["host_id"] == player_id:
                role = "host"
            elif rooms[code]["guest_id"] == player_id:
                role = "guest"
            
            await ws.send_json({
                "type": "welcome",
                "room": rooms[code],
                "role": role,
            })
            
            # إبلاغ الباقي
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
    
    # ===== حركة =====
    if msg_type == "move":
        if room["status"] != "playing":
            await ws.send_json({"type": "error", "message": "اللعبة لم تبدأ"})
            return
        
        # التحقق من الدور
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
            
            # تسجيل المباراة
            record_match(
                room["host_id"],
                room["guest_id"],
                winner,
                room["moves"],
                code
            )
        elif " " not in room["board"]:
            room["winner"] = "draw"
            room["status"] = "finished"
            record_match(
                room["host_id"],
                room["guest_id"],
                "draw",
                room["moves"],
                code
            )
        else:
            room["turn"] = "O" if room["turn"] == "X" else "X"
        
        await broadcast(code, {
            "type": "room_update",
            "room": room,
        })
    
    # ===== إعادة اللعب =====
    elif msg_type == "restart":
        if room["status"] == "finished":
            room["board"] = [" "] * 9
            room["turn"] = "X"
            room["status"] = "playing"
            room["winner"] = None
            room["moves"] = []
            room["started_at"] = now_iso()
            
            await broadcast(code, {
                "type": "room_update",
                "room": room,
            })
    
    # ===== دردشة =====
    elif msg_type == "chat":
        text = str(data.get("text", ""))[:200].strip()
        if not text:
            return
        
        user = users.get(str(player_id), {})
        await broadcast(code, {
            "type": "chat",
            "player_id": player_id,
            "player_name": user.get("name", "Player"),
            "text": text,
            "timestamp": now_iso(),
        })
    
    # ===== انسحاب =====
    elif msg_type == "forfeit":
        if room["status"] != "playing":
            return
        
        winner = "O" if player_id == room["host_id"] else "X"
        room["winner"] = winner
        room["status"] = "finished"
        
        record_match(
            room["host_id"],
            room["guest_id"],
            winner,
            room["moves"],
            code
        )
        
        await broadcast(code, {
            "type": "room_update",
            "room": room,
            "forfeit": True,
        })

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

# ============ الملفات الثابتة ============
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
