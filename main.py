import os
import shutil
import uuid
from fastapi import FastAPI, HTTPException, Depends, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from database import init_db, get_connection
from auth import hash_password, check_password, create_token, decode_token

STORAGE_DIR = "storage"
os.makedirs(STORAGE_DIR, exist_ok=True)
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

@app.post("/files")
def upload_file(file: UploadFile, current_user: dict = Depends(get_current_user)):
    stored_name = uuid.uuid4().hex
    path = os.path.join(STORAGE_DIR, stored_name)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    size = os.path.getsize(path)
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO files (filename, stored_name, size, owner_id) VALUES (?, ?, ?, ?)",
        (file.filename, stored_name, size, current_user["id"]),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, "filename": file.filename, "size": size}


@app.get("/files")
def list_files(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, filename, size, uploaded_at FROM files WHERE owner_id = ?",
        (current_user["id"],),
    ).fetchall()
    conn.close()

    files = []
    for row in rows:
        files.append({
            "id": row["id"],
            "filename": row["filename"],
            "size": row["size"],
            "uploaded_at": row["uploaded_at"],
        })
    return files


def get_owned_file(file_id, user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM files WHERE id = ? AND owner_id = ?", (file_id, user_id)
    ).fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    return row


@app.get("/files/{file_id}")
def download_file(file_id: int, current_user: dict = Depends(get_current_user)):
    row = get_owned_file(file_id, current_user["id"])
    path = os.path.join(STORAGE_DIR, row["stored_name"])
    return FileResponse(path, filename=row["filename"])


@app.delete("/files/{file_id}")
def delete_file(file_id: int, current_user: dict = Depends(get_current_user)):
    row = get_owned_file(file_id, current_user["id"])
    path = os.path.join(STORAGE_DIR, row["stored_name"])
    if os.path.exists(path):
        os.remove(path)
    conn = get_connection()
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    return {"deleted": file_id}