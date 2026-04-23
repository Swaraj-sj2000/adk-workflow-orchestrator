"""Auth endpoint tests — register, email verification, login, refresh, 2FA."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._user import User


def _register(client: TestClient, email: str = "user@example.com", role: str = "admin", slug: str = "example"):
    return client.post("/auth/register", json={
        "email": email,
        "password": "Secure1234!",
        "full_name": "Test User",
        "role": role,
        "tenant_slug": slug,
    })


def _verify_user(db: Session, email: str):
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.email_verified = True
        user.email_verify_token = None
        db.commit()


def _login(client: TestClient, email: str = "user@example.com"):
    return client.post("/auth/login", json={"email": email, "password": "Secure1234!"})


class TestRegister:
    def test_register_success(self, client):
        resp = _register(client, email="reg1@corp.com", slug="corp1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "reg1@corp.com"
        assert body["email_verified"] is False

    def test_duplicate_email_rejected(self, client):
        _register(client, email="dup@corp.com", slug="corp2")
        resp = _register(client, email="dup@corp.com", slug="corp2")
        assert resp.status_code == 400

    def test_login_blocked_before_verification(self, client):
        _register(client, email="unverified@corp.com", slug="corp3")
        resp = _login(client, "unverified@corp.com")
        assert resp.status_code == 401
        assert "verify" in resp.json()["detail"].lower()

    def test_login_allowed_after_verification(self, client, db):
        _register(client, email="verified@corp.com", slug="corp4")
        _verify_user(db, "verified@corp.com")
        resp = _login(client, "verified@corp.com")
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert "refresh_token" in resp.json()


class TestRefreshToken:
    def test_refresh_returns_new_tokens(self, client, db):
        _register(client, email="refresh@corp.com", slug="corp5")
        _verify_user(db, "refresh@corp.com")
        login_resp = _login(client, "refresh@corp.com")
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["refresh_token"] != refresh_token  # rotated

    def test_used_refresh_token_rejected(self, client, db):
        _register(client, email="used@corp.com", slug="corp6")
        _verify_user(db, "used@corp.com")
        login_resp = _login(client, "used@corp.com")
        rt = login_resp.json()["refresh_token"]

        client.post("/auth/refresh", json={"refresh_token": rt})
        # Second use of the same token must fail
        resp = client.post("/auth/refresh", json={"refresh_token": rt})
        assert resp.status_code == 401

    def test_invalid_refresh_token_rejected(self, client):
        resp = client.post("/auth/refresh", json={"refresh_token": "bogus-token"})
        assert resp.status_code == 401


class TestPasswordReset:
    def test_forgot_password_always_200(self, client):
        resp = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
        assert resp.status_code == 200

    def test_reset_with_invalid_token_fails(self, client):
        resp = client.post("/auth/reset-password", json={"token": "bad", "new_password": "NewPass1!"})
        assert resp.status_code == 400


class TestTOTP:
    def test_setup_and_enable_2fa(self, client, db):
        _register(client, email="totp@corp.com", slug="corp7")
        _verify_user(db, "totp@corp.com")
        login_resp = _login(client, "totp@corp.com")
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        setup_resp = client.post("/auth/2fa/setup", headers=headers)
        assert setup_resp.status_code == 200
        secret = setup_resp.json()["secret"]

        import pyotp
        code = pyotp.TOTP(secret).now()
        enable_resp = client.post("/auth/2fa/enable", json={"totp_code": code}, headers=headers)
        assert enable_resp.status_code == 200

        # Confirm totp_enabled in DB
        user = db.query(User).filter(User.email == "totp@corp.com").first()
        db.refresh(user)
        assert user.totp_enabled is True

    def test_disable_2fa_with_valid_code(self, client, db):
        _register(client, email="totp2@corp.com", slug="corp8")
        _verify_user(db, "totp2@corp.com")
        login_resp = _login(client, "totp2@corp.com")
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        setup_resp = client.post("/auth/2fa/setup", headers=headers)
        secret = setup_resp.json()["secret"]
        import pyotp
        client.post("/auth/2fa/enable", json={"totp_code": pyotp.TOTP(secret).now()}, headers=headers)

        disable_resp = client.post("/auth/2fa/disable", json={"totp_code": pyotp.TOTP(secret).now()}, headers=headers)
        assert disable_resp.status_code == 200

    def test_enable_2fa_with_wrong_code_fails(self, client, db):
        _register(client, email="totp3@corp.com", slug="corp9")
        _verify_user(db, "totp3@corp.com")
        login_resp = _login(client, "totp3@corp.com")
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        client.post("/auth/2fa/setup", headers=headers)
        resp = client.post("/auth/2fa/enable", json={"totp_code": "000000"}, headers=headers)
        assert resp.status_code == 400
