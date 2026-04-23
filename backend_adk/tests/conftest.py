"""Shared pytest fixtures — in-memory SQLite database, test client."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db._database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_app.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_token(client):
    """Register an admin and return its JWT token."""
    client.post("/auth/register", json={
        "email": "admin@testco.com",
        "password": "Admin1234!",
        "full_name": "Test Admin",
        "role": "admin",
        "tenant_slug": "testco",
    })
    # Manually mark verified so login works
    from app.models._user import User
    from sqlalchemy.orm import Session
    db_session: Session = next(app.dependency_overrides[get_db]())
    user = db_session.query(User).filter(User.email == "admin@testco.com").first()
    if user:
        user.email_verified = True
        db_session.commit()

    resp = client.post("/auth/login", json={
        "email": "admin@testco.com",
        "password": "Admin1234!",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
