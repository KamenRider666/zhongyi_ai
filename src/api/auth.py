"""用户认证模块 — 注册 / 登录 / JWT"""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from src.config import settings
from src.data.database import TCMDatabase

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── 密码 & JWT 配置 ──
SECRET_KEY = settings.DASHSCOPE_API_KEY or "zhongyi-dev-secret-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
PBKDF2_ITERATIONS = 600_000

security = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    """使用 PBKDF2-SHA256 哈希密码"""
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    return f"$pbkdf2${PBKDF2_ITERATIONS}${salt}${key}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """验证密码"""
    try:
        _, alg, iterations, salt, key = stored_hash.split("$")
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
        return new_key == key
    except (ValueError, AttributeError):
        return False


# ── 请求模型 ──
class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


# ── 数据库初始化 ──
def _init_user_table():
    """初始化 users 表"""
    db = TCMDatabase()
    ph = db._ph
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if db.db_type == "mysql" else ""
    db._exec_sql(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {'INTEGER PRIMARY KEY AUTOINCREMENT' if db.db_type == 'sqlite' else 'INT AUTO_INCREMENT PRIMARY KEY'},
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            email VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ){suffix}
    """)


# 启动时自动建表
_init_user_table()


# ── 辅助函数 ──
def _get_user_by_username(username: str) -> Optional[dict]:
    """从数据库获取用户"""
    db = TCMDatabase()
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE username = {db._ph}", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def _create_user(username: str, password: str, email: Optional[str]) -> dict:
    """创建用户"""
    db = TCMDatabase()
    password_hash = _hash_password(password)
    db._exec_sql(
        f"INSERT INTO users (username, password_hash, email) VALUES ({db._ph}, {db._ph}, {db._ph})",
        username, password_hash, email or "",
    )
    return {"username": username, "email": email}


def _create_token(username: str) -> str:
    """生成 JWT token"""
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """从 Authorization header 中解析当前用户名（用作依赖注入）"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")
        return username
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")


# ── 接口 ──
@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """用户注册"""
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 位字符")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位字符")
    if _get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="用户名已存在")

    _create_user(req.username, req.password, req.email)
    token = _create_token(req.username)
    return TokenResponse(access_token=token, username=req.username)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """用户登录"""
    user = _get_user_by_username(req.username)
    if not user or not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = _create_token(req.username)
    return TokenResponse(access_token=token, username=req.username)


@router.get("/me")
async def me(username: str = Depends(get_current_user)):
    """获取当前登录用户信息"""
    user = _get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"username": user["username"], "email": user.get("email"), "created_at": str(user.get("created_at"))}
