"""
tests/test_auth.py
------------------
Test suite for Milestone 1 Authentication endpoints.
"""

def test_register_user_success(client):
    """Test registering a new user succeeds and returns a JWT + user object."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "Password123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["full_name"] == "Test User"
    assert "id" in data["user"]


def test_register_duplicate_email_fails(client):
    """Test registering with an existing email returns 409 Conflict."""
    payload = {
        "full_name": "User One",
        "email": "duplicate@example.com",
        "password": "Password123",
    }
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"]


def test_login_success(client):
    """Test login with valid credentials returns a token."""
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login Test",
            "email": "login@example.com",
            "password": "Password123",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "Password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "login@example.com"


def test_login_invalid_credentials(client):
    """Test login with wrong password returns 401 Unauthorized."""
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login Test",
            "email": "login2@example.com",
            "password": "Password123",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login2@example.com",
            "password": "WrongPassword123",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_get_current_user_profile(client):
    """Test GET /api/v1/auth/me returns the profile when authenticated."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Me Test",
            "email": "metest@example.com",
            "password": "Password123",
        },
    )
    token = reg.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "metest@example.com"
    assert data["full_name"] == "Me Test"


def test_get_current_user_unauthorized(client):
    """Test GET /api/v1/auth/me without token returns 401 Unauthorized."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_logout(client):
    """Test POST /api/v1/auth/logout with valid token returns 200 OK."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Logout Test",
            "email": "logout@example.com",
            "password": "Password123",
        },
    )
    token = reg.json()["access_token"]

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "logged out" in response.json()["message"]
