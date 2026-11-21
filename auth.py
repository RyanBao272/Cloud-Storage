import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

SECRET_FILE = "secret.key"
TOKEN_MINUTES = 60

if not os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, "w") as f:
        f.write(secrets.token_hex(32))

with open(SECRET_FILE) as f:
    SECRET_KEY = f.read().strip()

def hash_password(password):
    password_bytes = password.encode()
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode()

def check_password(password, stored_hash):
    password_bytes = password.encode()
    stored_hash_bytes = stored_hash.encode()
    return bcrypt.checkpw(password_bytes, stored_hash_bytes)

def create_token(user_id):
    expires = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    return int(payload["sub"])