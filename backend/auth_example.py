#!/usr/bin/env python3
"""
Example: Integrating JWT with User Authentication
This shows how to integrate JWT tokens with a user login system.
"""

from jwt_utils import generate_token, decode_token
import hashlib

# Mock user database (replace with your actual user system)
USERS = {
    "user123": {
        "password_hash": hashlib.sha256("password123".encode()).hexdigest(),
        "role": "user",
        "name": "John Doe"
    },
    "admin_user": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "name": "Admin User"
    }
}

def authenticate_user(username: str, password: str) -> str:
    """Authenticate user and return JWT token"""
    if username not in USERS:
        raise ValueError("User not found")

    user = USERS[username]
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    if password_hash != user["password_hash"]:
        raise ValueError("Invalid password")

    # Generate JWT token
    token = generate_token(username, user["role"])
    return token

def validate_token(token: str) -> dict:
    """Validate JWT token and return user info"""
    payload = decode_token(token)
    user_id = payload["user_id"]

    if user_id not in USERS:
        raise ValueError("User no longer exists")

    user_info = USERS[user_id].copy()
    user_info.update(payload)
    return user_info

# Example usage
if __name__ == "__main__":
    try:
        # Login
        token = authenticate_user("user123", "password123")
        print(f"Login successful! Token: {token}")

        # Validate token
        user_info = validate_token(token)
        print(f"User authenticated: {user_info}")

    except ValueError as e:
        print(f"Authentication failed: {e}")