import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db

router = APIRouter(prefix="/utils", tags=["utils"])
logger = logging.getLogger(__name__)


@router.get("/healthchecker")
async def healthchecker(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar_one_or_none()
        return {"message": "Contacts API is healthy"}
    except Exception:
        logger.exception("Healthcheck failed")
        raise HTTPException(
            status_code=500,
            detail="Database is not configured correctly",
        )
