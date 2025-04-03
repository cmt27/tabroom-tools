# app/main.py
from fastapi import FastAPI
from . import config

app = FastAPI(title="Tabroom Tools")

@app.get("/")
async def root():
    return {"message": "Welcome to Tabroom Tools", "status": "running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "config": {
            "database_url": config.DATABASE_URL,
            "data_dir": config.DATA_DIR,
            "cookie_dir": config.COOKIE_DIR
        }
    }