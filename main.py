import os

from fastapi import FastAPI

from database import init_db, get_connection

os.makedirs("storage", exist_ok=True)
init_db()

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "my drive is alive"}


@app.get("/tables")
def list_tables():
    conn = get_connection()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    conn.close()
    return {"tables": [row["name"] for row in rows]}