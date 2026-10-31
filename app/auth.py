import uuid
from fastapi import Request
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.status import HTTP_403_FORBIDDEN

from app.models.users import UserModel
from app.config import SECRET_KEY, ALGORITHM
from app.db_depends import get_async_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token")

def hash_password(password: str) -> str:
    """
    Преобразует пароль в хеш с использованием bcrypt.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет, соответствует ли введённый пароль сохранённому хешу.
    """
    if len(plain_password.encode("utf-8")) > 72:
        return False
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    """
    Создаёт JWT с payload (sub, role, id, exp).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "token_type": "access"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    """
    Создаёт refresh-токен с длительным сроком действия и token_type="refresh".
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "token_type": "refresh",
        "jti": uuid.uuid4().hex
        })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(request: Request, token: str = Depends(oauth2_scheme),
                           db: AsyncSession = Depends(get_async_db)):
    """
    Проверяет JWT и возвращает пользователя из базы.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "token_type", "sid"]})
        email: str = payload.get("sub")
        token_type: str | None = payload.get("token_type")
        if email is None or token_type != "access":
            raise credentials_exception

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except jwt.PyJWTError:
        raise credentials_exception

    if payload.get('sid'):
        try:
            revoked = await request.app.state.redis.exists('revoked:'+payload['sid'])
        except Exception:
            raise HTTPException(status_code=503, detail='Session service unavailable')
        if revoked:
            raise credentials_exception
    result = await db.scalars(
        select(UserModel).where(UserModel.email == email,
UserModel.is_active == True))
    user = result.first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_staff(current_user: UserModel = Depends(get_current_user)):
    """
    Проверяет, что пользователь имеет роль сотрудника магазина.
    """
    if current_user.role not in ("staff", "admin"):
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Only store staff can perform this action")
    return current_user

async def get_current_buyer(current_user: UserModel = Depends(get_current_user)):
    if current_user.role != "buyer":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Only buyer can perform this action")
    return current_user

async def get_current_admin(current_user: UserModel = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Only admin can perform this action")
    return current_user