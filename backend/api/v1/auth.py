from datetime import datetime
from fastapi import APIRouter, Depends
from models.user import User
from schemas.auth import LoginRequest, RegisterRequest
from utils.crypto import crypto
from utils.jwt import create_access_token
from utils.response import success, error
from api.deps import get_current_user
import secrets

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
async def login(req: LoginRequest):
    user = await User.get_or_none(username=req.username)
    if not user or not crypto.verify_password(req.password, user.password_hash):
        return error(code=401, message="用户名或密码错误")
    user.last_login = datetime.now()
    await user.save(update_fields=["last_login"])
    token = create_access_token(user.id, user.username, user.role)
    return success(data={
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 604800,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email,
        },
    })


@router.post("/register")
async def register(req: RegisterRequest):
    existing = await User.get_or_none(username=req.username)
    if existing:
        return error(code=400, message="用户名已存在")
    user = await User.create(
        username=req.username,
        password_hash=crypto.hash_password(req.password),
        api_key=f"sk-{secrets.token_urlsafe(32)}",
        email=req.email,
    )
    token = create_access_token(user.id, user.username, user.role)
    return success(data={
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 604800,
    })


@router.post("/refresh")
async def refresh_token(user: User = Depends(get_current_user)):
    token = create_access_token(user.id, user.username, user.role)
    return success(data={"access_token": token, "token_type": "bearer", "expires_in": 604800})


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return success(data={
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "email": user.email,
        "api_key": user.api_key,
        "avatar": user.avatar,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    })
