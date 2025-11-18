from __future__ import annotations

from typing import Dict

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.database import engine


def check_database_health() -> Dict[str, str]:
    """Attempt a lightweight DB query to ensure connectivity."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "UP"}
    except OperationalError as exc:
        return {"status": "DOWN", "detail": str(exc)}

