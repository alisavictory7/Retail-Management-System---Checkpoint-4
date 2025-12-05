"""Centralized application configuration for all environments."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final

from dotenv import load_dotenv

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables once, prioritizing runtime env over file values
load_dotenv(dotenv_path=ENV_PATH, override=False)


def _str_to_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _determine_database_url() -> str:
    """
    Return a connection string using the following precedence:
    1. Explicit DATABASE_URL
    2. Individual DB_* components (for PostgreSQL)
    3. Local SQLite fallback (for onboarding / tests)
    """
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")

    if all([username, password, host, port, name]):
        driver = os.getenv("DB_DRIVER", "postgresql+psycopg2")
        return f"{driver}://{username}:{password}@{host}:{port}/{name}"

    # SQLite dev fallback stored under /db/app.db to keep repo tidy
    fallback_path = BASE_DIR / "db" / "app.db"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{fallback_path.as_posix()}"


class Config:
    """Default runtime configuration shared across Flask, services, and scripts."""

    APP_NAME: Final[str] = os.getenv("APP_NAME", "Retail Management System")
    APP_ENV: Final[str] = os.getenv("APP_ENV", "development")

    SECRET_KEY: Final[str] = os.getenv("SECRET_KEY", "change-me-in-prod")
    DEBUG: Final[bool] = _str_to_bool(os.getenv("FLASK_DEBUG"), default=APP_ENV == "development")
    TESTING: Final[bool] = _str_to_bool(os.getenv("FLASK_TESTING"), default=False)

    # Flask run configuration (used by run.py + Docker)
    FLASK_RUN_HOST: Final[str] = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    FLASK_RUN_PORT: Final[int] = int(os.getenv("FLASK_RUN_PORT", "5000"))

    # Database
    DATABASE_URL: Final[str] = _determine_database_url()
    SQL_ECHO: Final[bool] = _str_to_bool(os.getenv("SQL_ECHO"), default=False)
    DB_POOL_SIZE: Final[int] = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: Final[int] = int(os.getenv("DB_MAX_OVERFLOW", "20"))

    # Returns & Refunds policy knobs
    RETURN_WINDOW_DAYS: Final[int] = int(os.getenv("RETURN_WINDOW_DAYS", "30"))
    MAX_RETURN_ITEM_QUANTITY: Final[int] = int(os.getenv("MAX_RETURN_ITEM_QUANTITY", "5"))
    RETURNS_REQUIRE_PHOTOS: Final[bool] = _str_to_bool(os.getenv("RETURNS_REQUIRE_PHOTOS"), default=False)
    RETURNS_MAX_PHOTOS: Final[int] = int(os.getenv("RETURNS_MAX_PHOTOS", "20"))
    _allowed_ext = [
        ext.strip().lower()
        for ext in os.getenv("RETURNS_ALLOWED_EXTENSIONS", "jpg,jpeg,png,gif,webp").split(",")
        if ext.strip()
    ]
    RETURNS_ALLOWED_EXTENSIONS: Final[tuple[str, ...]] = tuple(_allowed_ext) or ("jpg", "jpeg", "png", "gif", "webp")
    RETURNS_UPLOAD_SUBDIR: Final[str] = os.getenv("RETURNS_UPLOAD_SUBDIR", "uploads/returns")
    RETURNS_UPLOAD_DIR: Final[Path] = Path(
        os.getenv("RETURNS_UPLOAD_DIR", (BASE_DIR / "static" / RETURNS_UPLOAD_SUBDIR).as_posix())
    )
    FEATURE_RETURNS_ENABLED: Final[bool] = _str_to_bool(os.getenv("FEATURE_RETURNS_ENABLED"), default=True)

    # Observability and reliability
    STRUCTURED_LOGS_ENABLED: Final[bool] = _str_to_bool(os.getenv("STRUCTURED_LOGS_ENABLED"), default=True)
    LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "INFO")
    REQUEST_ID_HEADER: Final[str] = os.getenv("REQUEST_ID_HEADER", "X-Request-ID")
    OBSERVABILITY_ENABLED: Final[bool] = _str_to_bool(os.getenv("OBSERVABILITY_ENABLED"), default=True)
    METRICS_EXPORT_INTERVAL: Final[int] = int(os.getenv("METRICS_EXPORT_INTERVAL", "60"))
    DASHBOARD_SAMPLE_WINDOW_MIN: Final[int] = int(os.getenv("DASHBOARD_SAMPLE_WINDOW_MIN", "15"))
    PAYMENT_REFUND_FAILURE_PROBABILITY: Final[float] = float(os.getenv("PAYMENT_REFUND_FAILURE_PROBABILITY", "0.1"))
    THROTTLING_MAX_RPS: Final[int] = int(os.getenv("THROTTLING_MAX_RPS", "100"))
    THROTTLING_WINDOW_SECONDS: Final[int] = int(os.getenv("THROTTLING_WINDOW_SECONDS", "1"))

    QUALITY_SCENARIO_TAGS: Final[str] = os.getenv("QUALITY_SCENARIO_TAGS", "availability,performance")

    # Checkpoint 4: Feature configurations
    LOW_STOCK_THRESHOLD: Final[int] = int(os.getenv("LOW_STOCK_THRESHOLD", "5"))
    ORDER_HISTORY_PAGE_SIZE: Final[int] = int(os.getenv("ORDER_HISTORY_PAGE_SIZE", "20"))

    DEFAULT_TIMEZONE: Final[str] = os.getenv("DEFAULT_TIMEZONE", "UTC")
    SUPER_ADMIN_TOKEN: Final[str] = os.getenv("SUPER_ADMIN_TOKEN", "CP3_SUPERADMIN_TOKEN_N9fA7qLzX4")
    SUPER_ADMIN_USERNAME: Final[str] = os.getenv("SUPER_ADMIN_USERNAME", "super_admin")
    SUPER_ADMIN_PASSWORD: Final[str] = os.getenv("SUPER_ADMIN_PASSWORD", "super_admin_92587")
    SUPER_ADMIN_EMAIL: Final[str] = os.getenv("SUPER_ADMIN_EMAIL", "super_admin@example.com")

    @classmethod
    def configure_app(cls, app: Any) -> None:
        """Apply core configuration to a Flask app instance."""
        app.config["SECRET_KEY"] = cls.SECRET_KEY
        app.config["ENV"] = cls.APP_ENV
        app.config["DEBUG"] = cls.DEBUG
        app.config["TESTING"] = cls.TESTING
        app.config["SQLALCHEMY_DATABASE_URI"] = cls.DATABASE_URL
        app.config["SQLALCHEMY_ECHO"] = cls.SQL_ECHO
        app.config["RETURN_WINDOW_DAYS"] = cls.RETURN_WINDOW_DAYS
        app.config["MAX_RETURN_ITEM_QUANTITY"] = cls.MAX_RETURN_ITEM_QUANTITY
        app.config["FEATURE_RETURNS_ENABLED"] = cls.FEATURE_RETURNS_ENABLED
        cls.RETURNS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        app.config["RETURNS_UPLOAD_DIR"] = str(cls.RETURNS_UPLOAD_DIR)
        app.config["RETURNS_UPLOAD_SUBDIR"] = cls.RETURNS_UPLOAD_SUBDIR
        app.config["RETURNS_MAX_PHOTOS"] = cls.RETURNS_MAX_PHOTOS
        app.config["RETURNS_ALLOWED_EXTENSIONS"] = cls.RETURNS_ALLOWED_EXTENSIONS
        app.config["STRUCTURED_LOGS_ENABLED"] = cls.STRUCTURED_LOGS_ENABLED
        app.config["OBSERVABILITY_ENABLED"] = cls.OBSERVABILITY_ENABLED


