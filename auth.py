import bcrypt

def hash_password(password):
    password_bytes = password.encode()
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode()

def check_password(password, stored_hash):
    password_bytes = password.encode()
    stored_hash_bytes = stored_hash.encode()
    return bcrypt.checkpw(password_bytes, stored_hash_bytes)