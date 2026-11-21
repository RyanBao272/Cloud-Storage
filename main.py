import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from database import init_db, get_connection
from auth import hash_password, check_password, create_token, decode_token

os.makedirs("storage", exist_ok=True)
init_db()
app = FastAPI()
bearer = HTTPBearer()

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

@app.get("/")
def home_page():
    return FileResponse("static/index.html")

@app.get("/tables")
def list_tables():
    conn = get_connection()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    conn.close()
    return {"tables": [row["name"] for row in rows]}


@app.post("/register")
def register(user: UserCreate):
    if len(user.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if len(user.password.encode()) > 72:
        raise HTTPException(status_code=400, detail="Password can't be more than 72 bytes")

    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (user.username,)
    ).fetchone()
    if existing is not None:
        conn.close()
        raise HTTPException(status_code=409, detail="Username already taken")

    password_hash = hash_password(user.password)
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (user.username, password_hash),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, "username": user.username}

@app.post("/login")
def login(user: UserLogin):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (user.username,)
    ).fetchone()
    conn.close()
    if row is None or not check_password(user.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong username or password")
    token = create_token(row["id"])
    return {"access_token": token, "token_type": "bearer"}

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    token = credentials.credentials
    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    conn = get_connection()
    row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return {"id": row["id"], "username": row["username"]}

@app.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user