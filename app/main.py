from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db.init_db import init_db, dispose_db
from .routers import auth, user


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await dispose_db()


app = FastAPI(
    debug=settings.debug,
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allowed_methods,
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(user.router)


@app.get("/")
@app.head("/")
async def read_root():
    return {
        "message": "Welcome to the Online Complaint Management System API",
        "version": settings.app_version,
        "docs": {
            "redoc": "/api/redoc",
            "swagger": "/api/docs",
            "openapi": "/api/openapi.json",
        },
    }
