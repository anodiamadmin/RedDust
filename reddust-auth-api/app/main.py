""" RedDust Authentication API — FastAPI application entry point.
Responsibilities:
- Register all RedDust Auth API routers.
- Return safe validation errors without exposing request credentials.
- Return safe database errors without exposing SQL or connection details.
The WebRTC Gateway POST /offer belongs to the separate
reddust-gateway application on port 8000. """

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.routes import auth, calls, health, users

# ---------------------------------------------------------
# 1. Create the FastAPI application
# ---------------------------------------------------------
app = FastAPI(
    title="RedDust Auth API",
    version="0.1.0",
)

# ---------------------------------------------------------
# 2. Register the Auth API routers
# ---------------------------------------------------------
# GET /healthz
app.include_router(health.router)

# POST /v1/auth/google
# POST /v1/auth/refresh
# POST /v1/auth/logout
app.include_router(auth.router)

# GET /v1/users/me
app.include_router(users.router)

# POST /v1/calls
# POST /v1/calls/{id}/end
app.include_router(calls.router)

# ---------------------------------------------------------
# 3. Safe request-validation error handler
# ---------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def safe_validation_error(
    request: Request,
    exc: RequestValidationError,
):
    """ Return HTTP 422 without echoing submitted credentials.
    Do not include raw request bodies, ID tokens, access
    tokens, refresh tokens or other sensitive input values.  """

    errors = [
        {
            "loc": list(err.get("loc", ())),
            "msg": "Invalid request field",
            "type": err.get("type", "value_error"),
        }
        for err in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )

# ---------------------------------------------------------
# 4. Safe SQLAlchemy/database error handler
# ---------------------------------------------------------
@app.exception_handler(SQLAlchemyError)
async def safe_database_error(
    request: Request,
    exc: SQLAlchemyError,
):
    """ Return HTTP 503 without exposing internal database
    errors, SQL statements, credentials or bind parameters. """

    if request.url.path.startswith("/v1/calls"):
        code = "CALL_SERVICE_UNAVAILABLE"
    else:
        code = "AUTH_UNAVAILABLE"

    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": code,
                "message": "Service temporarily unavailable",
            }
        },
    )


""" OLD CODE without healthz route. RedDust Auth API only. The WebRTC Gateway runs as a separate app."""
# from fastapi import FastAPI
 
# app = FastAPI(title="RedDust Auth API", version="0.1.0")
 
# @app.get("/healthz")
# def healthz():
#     return {"status": "ok", "service": "reddust-auth-api"}

# from fastapi import FastAPI, Request
# from fastapi.exceptions import RequestValidationError
# from fastapi.responses import JSONResponse
# from sqlalchemy.exc import SQLAlchemyError

# from app.routes import auth, calls, health, users

# app = FastAPI(title="RedDust Auth API", version="0.1.0")
# app.include_router(health.router)
# app.include_router(auth.router)
# app.include_router(users.router)
# app.include_router(calls.router)

# @app.exception_handler(RequestValidationError)
# async def safe_validation_error(request: Request, exc: RequestValidationError):
#     # FastAPI's default error may echo input credential values. Strip them.
#     errors = [
#         {"loc": list(err.get("loc", ())),
#          "msg": err.get("msg", "Invalid input"),
#          "type": err.get("type", "value_error")}
#         for err in exc.errors()
#     ]
#     return JSONResponse(status_code=422, content={"detail": errors})

# @app.exception_handler(SQLAlchemyError)
# async def safe_database_error(request: Request, exc: SQLAlchemyError):
#     # Do not return SQL statements, bind parameters or secret material.
#     code = ("CALL_SERVICE_UNAVAILABLE" if request.url.path.startswith("/v1/calls")
#             else "AUTH_UNAVAILABLE")
#     return JSONResponse(status_code=503, content={
#         "detail": {"code": code, "message": "Service temporarily unavailable"}
#     })
