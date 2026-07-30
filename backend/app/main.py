from fastapi import FastAPI
from app.api.chat import router as chat_router

app = FastAPI(title="RedDust API")

app.include_router(chat_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "RedDust backend running"}
