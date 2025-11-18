# src/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from flask import g

from src.config import Config

engine_kwargs = {
    "echo": Config.SQL_ECHO,
    "future": True,
    "pool_pre_ping": True,
}

if not Config.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["pool_size"] = Config.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = Config.DB_MAX_OVERFLOW

engine = create_engine(Config.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()

def get_db():
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db

def close_db(e=None):
    try:
        db = g.pop('db', None)
        if db is not None:
            db.close()
    except RuntimeError:
        # Handle case where we're outside of application context
        # This can happen during test teardown
        pass

