import json

import pytest
from flask import session

from src.main import app
from src.database import Base, engine, SessionLocal
from src.models import User


@pytest.fixture(scope="module")
def test_client():
    Base.metadata.create_all(bind=engine)
    with app.test_client() as client:
        with app.app_context():
            session.clear()
        yield client


def _login(client, username="testuser_api", password="password123"):
    db = SessionLocal()
    user = db.query(User).filter_by(username=username).first()
    if not user:
        user = User(username=username, email=f"{username}@example.com")
        user.passwordHash = "pbkdf2:sha256:260000$PpK/7a8G4Oqqe1AT$47a59ca248255e87932188ab0f668c9619e0786939b22302ac15c2b8d55728ab"
        db.add(user)
        db.commit()
    db.close()
    with client.session_transaction() as sess:
        sess["user_id"] = user.userID


def test_health_endpoint(test_client):
    response = test_client.get("/health")
    assert response.status_code in (200, 503)
    body = response.get_json()
    assert "status" in body


def test_returns_request_flow(test_client):
    _login(test_client)
    response = test_client.get("/returns")
    assert response.status_code in (200, 302)


def test_admin_dashboard_requires_admin(test_client):
    _login(test_client, username="non_admin")
    resp = test_client.get("/admin/dashboard")
    assert resp.status_code == 403

    _login(test_client, username="admin")
    with test_client.session_transaction() as sess:
        sess["is_admin"] = True
    resp = test_client.get("/admin/dashboard")
    assert resp.status_code in (200, 302)

