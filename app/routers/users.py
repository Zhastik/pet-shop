from app.auth import get_current_user, get_current_admin
from app.schemas import UserRoleUpdate
from app.services.audit import audit
from fastapi import Query
import uuid
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.security import OAuth2PasswordRequestForm

import jwt

from app.config import SECRET_KEY, ALGORITHM
from app.models.users import UserModel
from app.schemas import UserCreate, UserSchema, RefreshTokenRequest
from app.db_depends import get_async_db
from app.auth import hash_password, verify_password, create_access_token, create_refresh_token, oauth2_scheme

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_async_db)):
    """
    Регистрирует нового пользователя с ролью покупателя.
    """
    # Проверка уникальности email
    result = await db.scalars(select(UserModel).where(UserModel.email == user.email))
    if result.first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Email already registered")

    # Создание объекта пользователя с хешированным паролем
    db_user = UserModel(
        email=user.email,
        hashed_password=await run_in_threadpool(hash_password, user.password),
        role="buyer"
    )

    # Добавление в сессию и сохранение в базе
    db.add(db_user)
    await db.commit()
    return db_user

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_async_db)):
    result = await db.scalars(
        select(UserModel).where(UserModel.email == form_data.username, UserModel.is_active == True))
    user = result.first()
    if not user or not await run_in_threadpool(verify_password, form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session_id = uuid.uuid4().hex
    access_token = create_access_token(data= {"sub": user.email, "role": user.role, "id": user.id, "sid": session_id})
    refresh_token = create_refresh_token(data= {"sub": user.email, "role": user.role, "id": user.id, "sid": session_id})
    return {"access_token": access_token,"refresh_token": refresh_token, "token_type": "bearer"}


async def rotate_refresh(body: RefreshTokenRequest, request: Request, db: AsyncSession):
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM],
                             options={'require': ['exp', 'sub', 'token_type', 'sid', 'jti']})
        if payload['token_type'] != 'refresh':
            raise jwt.InvalidTokenError()
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail='Invalid refresh token', headers={'WWW-Authenticate':'Bearer'})
    redis = request.app.state.redis
    try:
        result = await redis.eval("""
            if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
            if redis.call('SET', KEYS[2], '1', 'EX', ARGV[1], 'NX') then return 1 end
            redis.call('SET', KEYS[1], '1', 'EX', ARGV[1])
            return -1
        """, 2, 'revoked:'+payload['sid'], 'used:'+payload['jti'], 7*86400)
        if result != 1:
            raise HTTPException(status_code=401, detail='Session revoked or refresh token reused')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail='Session service unavailable')
    user = await db.scalar(select(UserModel).where(UserModel.email == payload['sub'], UserModel.is_active == True))
    if not user:
        raise HTTPException(status_code=401, detail='User unavailable')
    data = {'sub':user.email, 'role':user.role, 'id':user.id, 'sid':payload['sid']}
    return {'access_token':create_access_token(data), 'refresh_token':create_refresh_token(data), 'token_type':'bearer'}


@router.post('/refresh-token')
async def refresh_token(body: RefreshTokenRequest, request: Request, db: AsyncSession = Depends(get_async_db)):
    return await rotate_refresh(body, request, db)


@router.post('/access-token')
async def access_token(body: RefreshTokenRequest, request: Request, db: AsyncSession = Depends(get_async_db)):
    return await rotate_refresh(body, request, db)


@router.post('/logout', status_code=204)
async def logout(request: Request, token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={'require':['exp','sid']})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail='Invalid token')
    try:
        await request.app.state.redis.set('revoked:'+payload['sid'], '1', ex=7*86400)
    except Exception:
        raise HTTPException(status_code=503, detail='Session service unavailable')
    from fastapi import Response
    return Response(status_code=204)


@router.get('/me', response_model=UserSchema)
async def me(user: UserModel = Depends(get_current_user)):
    return user


@router.get('/', response_model=list[UserSchema], dependencies=[Depends(get_current_admin)])
async def list_users(db: AsyncSession = Depends(get_async_db),
                     page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     search: str = Query('', max_length=200)):
    statement = select(UserModel).order_by(UserModel.id)
    if search:
        statement = statement.where(UserModel.email.icontains(search, autoescape=True))
    return (await db.scalars(statement.offset((page-1)*page_size).limit(page_size))).all()


@router.patch('/{user_id}/role', response_model=UserSchema)
async def set_role(user_id: int, body: UserRoleUpdate,
                   admin: UserModel = Depends(get_current_admin), db: AsyncSession = Depends(get_async_db)):
    user = await db.scalar(select(UserModel).where(UserModel.id == user_id).with_for_update())
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if user.role == 'admin':
        raise HTTPException(status_code=409, detail='Administrator role cannot be changed here')
    user.role = body.role
    await audit(db, admin.id, 'user.role.'+body.role, user.id)
    await db.commit()
    return user
