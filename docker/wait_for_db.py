import os
import time
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


DATABASE_URL = os.environ.get("DATABASE_URL")
MAX_ATTEMPTS = int(os.environ.get("DB_WAIT_ATTEMPTS", "30"))
SLEEP_SECONDS = int(os.environ.get("DB_WAIT_INTERVAL", "2"))

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set; cannot wait for database.")


def main() -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with engine.connect():
                print("Database connection established.")
                return
        except OperationalError as exc:
            print(f"[wait_for_db] Attempt {attempt}/{MAX_ATTEMPTS} failed: {exc}")
            time.sleep(SLEEP_SECONDS)

    raise RuntimeError("Database not reachable after waiting.")


if __name__ == "__main__":
    main()

