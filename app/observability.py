from prometheus_client import Counter, Histogram
from starlette.responses import JSONResponse
from app.config import settings
import hashlib

REQUESTS = Counter("http_requests_total", "HTTP responses", ["method", "route", "status"])
DURATION = Histogram("http_request_duration_seconds", "HTTP duration", ["method", "route"])

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from contextvars import ContextVar

request_id = ContextVar('request_id', default='')


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {'time': datetime.now(timezone.utc).isoformat(), 'level': record.levelname,
                'logger': record.name, 'message': record.getMessage(), 'request_id': request_id.get()}
        if record.exc_info:
            data['exception'] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def configure_logging(level):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


class RequestMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        rid = uuid.uuid4().hex
        scope.setdefault('state', {})['request_id'] = rid
        context = request_id.set(rid)
        started, status = time.monotonic(), 500
        async def wrapped(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message['headers'] += [(b'x-request-id', rid.encode()),
                                       (b'x-content-type-options', b'nosniff'),
                                       (b'referrer-policy', b'strict-origin-when-cross-origin')]
            await send(message)
        try:
            if settings.rate_limit_enabled and scope['path'] in ('/users/token', '/users/', '/users/refresh-token', '/users/access-token') and scope['method'] == 'POST':
                client = scope.get('client')
                identity = hashlib.sha256((client[0] if client else 'unknown').encode()).hexdigest()
                redis = scope['app'].state.redis
                try:
                    limit = await redis.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n", 1, 'auth-limit:'+identity)
                except Exception:
                    return await JSONResponse({'detail':'Authentication temporarily unavailable', 'code':'RATE_LIMIT_UNAVAILABLE', 'request_id':rid}, status_code=503)(scope, receive, wrapped)
                if limit > 30:
                    return await JSONResponse({'detail':'Too many requests', 'code':'RATE_LIMITED', 'request_id':rid}, status_code=429, headers={'Retry-After':'60'})(scope, receive, wrapped)
            await self.app(scope, receive, wrapped)
        finally:
            route = scope.get('route')
            label = getattr(route, 'path', '/static-or-unmatched')
            REQUESTS.labels(scope['method'], label, str(status)).inc()
            DURATION.labels(scope['method'], label).observe(time.monotonic()-started)
            logging.getLogger('http').info('%s %s status=%s duration_ms=%.2f', scope['method'],
                getattr(route, 'path', '/static-or-unmatched'), status, (time.monotonic()-started)*1000)
            request_id.reset(context)
