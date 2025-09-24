from fastapi import APIRouter, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

router = APIRouter()

# Use the same secret key as in websocket.py
JWT_SECRET_KEY = 'your-secret-key-change-in-production'
JWT_ALGORITHM = 'HS256'

# Simple in-memory user store (replace with proper database in production)
USERS = {
    "admin": {"password": "admin123", "user_id": "admin_001", "role": "admin"},
    "user": {"password": "user123", "user_id": "user_001", "role": "user"}
}

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    """Authenticate user and return JWT token"""
    user = USERS.get(credentials.username)
    if not user or user["password"] != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(hours=24)
    access_token = create_access_token(
        data={"user_id": user["user_id"], "role": user["role"]},
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        user_id=user["user_id"]
    )

@router.post("/logout")
async def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_current_user_info(token: str):
    """Get current user info from token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        role = payload.get("role", "user")

        return {
            "user_id": user_id,
            "role": role,
            "is_authenticated": True
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )