#!/usr/bin/env python3
"""
JWT Token Generator for NSE Monitor Authentication
Run this script to generate JWT tokens for testing or production use.
"""

import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

# JWT configuration (matches websocket.py)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

def generate_token(user_id: str, role: str = "user", hours_valid: int = 24) -> str:
    """Generate a JWT token for a user"""
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=hours_valid),
        'iat': datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def decode_token(token: str) -> dict:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")

def generate_test_tokens():
    """Generate some test tokens"""
    tokens = {
        "admin": generate_token("admin_user", "admin", 168),  # 1 week
        "user1": generate_token("user123", "user", 24),       # 24 hours
        "user2": generate_token("user456", "user", 24),       # 24 hours
    }

    print("Generated Test Tokens:")
    print("=" * 50)
    for user, token in tokens.items():
        print(f"\n{user.upper()}:")
        print(f"Token: {token}")
        try:
            payload = decode_token(token)
            exp_time = datetime.fromtimestamp(payload['exp'], timezone.utc)
            print(f"Expires: {exp_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"User ID: {payload['user_id']}")
            print(f"Role: {payload['role']}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    generate_test_tokens()