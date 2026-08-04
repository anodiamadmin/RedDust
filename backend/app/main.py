# main.py — Application entry point
# This is where FastAPI is instantiated and all routers are registered.
# uvicorn points to this file: `uvicorn app.main:app`

from fastapi import FastAPI
from app.api.chat import router as chat_router

# Create the FastAPI application instance with a human-readable title
app = FastAPI(title="RedDust API")

# Mount the chat router under the /api prefix
# All routes defined in chat.py will be accessible as /api/<route>
app.include_router(chat_router, prefix="/api")


# Basic health-check route — useful for load balancers and uptime monitors
@app.get("/")
async def root():
    return {"message": "RedDust backend running"}
