import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

from src.api import auth, contacts, users, utils
from src.conf.config import settings
from src.database.db import sessionmanager
from src.services.cache import close_cache

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

tags_metadata = [
    {
        "name": "auth",
        "description": "Registration, login, JWT tokens and email verification.",
    },
    {
        "name": "users",
        "description": "Current user profile and avatar management.",
    },
    {
        "name": "contacts",
        "description": "Protected contact operations for the authenticated user.",
    },
    {
        "name": "utils",
        "description": "Service health checks.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown resources."""
    logger.info("Starting Contacts API")
    try:
        yield
    finally:
        await close_cache()
        await sessionmanager.close()
        logger.info("Stopped Contacts API")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Contacts REST API with JWT authorization, email verification, "
        "per-user contact isolation and Cloudinary avatar uploads."
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = users.limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contacts.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(utils.router, prefix="/api")


@app.get("/")
async def root() -> dict[str, str]:
    """Return a simple API status message."""
    return {"message": "Contacts API Auth is running"}


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.exception(
        "Database error on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(status_code=500, content={"detail": "Database error"})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Try again later."},
    )
