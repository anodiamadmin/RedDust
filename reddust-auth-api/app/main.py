from fastapi import FastAPI
 
app = FastAPI(title="RedDust Auth API", version="0.1.0")
 
@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "reddust-auth-api"}
