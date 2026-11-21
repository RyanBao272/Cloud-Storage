import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from database import init_db, get_connection
from auth import hash_password

os.makedirs("storage", exist_ok=True)
init_db()

app = FastAPI()

class UserCreate(BaseModel):
    username: str
    password: str

@app.get("/")
def read_root():
    return {"message": "my drive is alive"}


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
        raise HTTPException(status_code=400, detail="Password must be at most 72 bytes")

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