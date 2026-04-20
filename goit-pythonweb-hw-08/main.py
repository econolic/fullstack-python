import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from src.api import contacts, utils
from src.conf.config import settings
from src.database.db import sessionmanager

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.include_router(contacts.router, prefix="/api")
app.include_router(utils.router, prefix="/api")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Contacts API is running"}


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting Contacts API")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await sessionmanager.close()
    logger.info("Stopped Contacts API")


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.exception(
        "Database error on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(status_code=500, content={"detail": "Database error"})
