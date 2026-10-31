"""Bootstrap administrator locally: docker compose exec web python -m app.create_admin"""
import asyncio
import getpass
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select
from app import models  # noqa: F401
from app.database import async_session_maker, async_engine
from app.auth import hash_password
from app.models.users import UserModel
from app.services.audit import audit


async def main():
    email = str(TypeAdapter(EmailStr).validate_python(input('Admin email: ').strip()))
    password = getpass.getpass('Password (8+ characters, max 72 UTF-8 bytes): ')
    if len(password) < 8 or len(password.encode()) > 72 or password != getpass.getpass('Repeat password: '):
        raise SystemExit('Invalid password or confirmation')
    try:
        async with async_session_maker() as db:
            if await db.scalar(select(UserModel.id).where(UserModel.email == email)):
                raise SystemExit('Account already exists; no changes made')
            user = UserModel(email=email, hashed_password=hash_password(password), role='admin')
            db.add(user)
            await db.flush()
            await audit(db, user.id, 'admin.bootstrap', user.id)
            await db.commit()
        print('Administrator created')
    finally:
        await async_engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
