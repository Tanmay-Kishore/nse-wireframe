#!/usr/bin/env python3
"""
Test JWT Token Generator for NSE Monitor WebSocket Authentication
Run this script to generate test tokens for development/testing.
"""

import jwt
from datetime import datetime, timedelta, timezone

# Use the same secret key as in websocket.py
JWT_SECRET_KEY = 'your-secret-key-change-in-production'
JWT_ALGORITHM = 'HS256'

def generate_test_token(user_id='test_user_123', hours_valid=24):
    """Generate a test JWT token"""
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(hours=hours_valid),
        'iat': datetime.now(timezone.utc)
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

if __name__ == '__main__':
    token = generate_test_token()
    print('Test JWT Token:')
    print(token)
    print()
    print('Token payload contains:')
    print('- user_id: test_user_123')
    print('- expires: 24 hours from now')
    print('- issued: now')
    print()
    print('Use in WebSocket URLs:')
    print(f'ws://localhost:8000/ws/screener?token={token}')
    print(f'ws://localhost:8000/ws/price?symbol=RELIANCE&token={token}')