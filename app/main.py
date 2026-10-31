import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException
from app.config import settings
from app.database import async_engine
from app.observability import configure_logging, RequestMiddleware
from app.routers import categories, products, users, reviews, cart, orders


@asynccontextmanager
async def lifespan(app):
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, send_default_pii=False, max_request_body_size="never")
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        from redis.asyncio import Redis
        app.state.redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        await app.state.redis.ping()
        yield
    finally:
        if hasattr(app.state, 'redis'):
            await app.state.redis.aclose()
        await async_engine.dispose()


def create_app():
    app = FastAPI(title='Смотри API', version='0.2.0', lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(RequestMiddleware)
    def error(request, status, detail, code, headers=None):
        return JSONResponse(status_code=status, content={'detail': detail, 'code': code,
            'request_id': getattr(request.state, 'request_id', '')}, headers=headers)
    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(request, exc.status_code, exc.detail, f'HTTP_{exc.status_code}', exc.headers)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(request, 422, 'Некорректные данные запроса', 'VALIDATION_ERROR')
    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return error(request, 409, 'Конфликт данных', 'DATA_CONFLICT')
    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logging.getLogger('app').error('Unhandled request error', exc_info=exc)
        rid = getattr(request.state, 'request_id', '')
        return error(request, 500, 'Внутренняя ошибка сервера', 'INTERNAL_ERROR', {'X-Request-ID': rid})
    for router in (categories, products, users, reviews, cart, orders):
        app.include_router(router.router)
    base = Path(__file__).resolve().parent.parent
    app.mount('/media', StaticFiles(directory=base / 'media'), name='media')
    app.mount('/shop', StaticFiles(directory=base / 'frontend', html=True), name='shop')
    from prometheus_client import make_asgi_app
    app.mount('/metrics', make_asgi_app())
    @app.get('/health/live', include_in_schema=False)
    async def live():
        return {'status': 'ok'}
    @app.get('/health/ready', include_in_schema=False)
    async def ready(request: Request):
        import asyncio
        try:
            async with asyncio.timeout(3):
                async with async_engine.connect() as conn:
                    await conn.execute(text('SELECT 1'))
                await request.app.state.redis.ping()
            return {'status': 'ready'}
        except Exception:
            return error(request, 503, 'Сервис временно не готов', 'NOT_READY')
    @app.get('/')
    async def root():
        return {'message': 'Смотри API', 'shop': '/shop/'}
    return app


app = create_app()
