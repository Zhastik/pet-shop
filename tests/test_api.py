import os
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import settings
from sqlalchemy.engine import make_url

if os.getenv("RUN_DB_TESTS") == "1" and not (make_url(settings.database_url).database or "").endswith("_test"):
    raise RuntimeError("Integration tests require a database name ending in _test")


def test_health_and_request_id():
    # Liveness needs no database and does not enter lifespan.
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get('/health/live')
    assert response.status_code == 200
    assert len(response.headers['x-request-id']) == 32
    response = client.get('/does-not-exist')
    assert response.json()['request_id'] == response.headers['x-request-id']
    assert response.json()['code'] == 'HTTP_404'


def test_category_write_requires_authentication():
    client = TestClient(create_app())
    assert client.post('/categories/', json={'name': 'Private'}).status_code == 401


@pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires dedicated PostgreSQL test DB')
def test_checkout_concurrency_and_idempotency():
    with TestClient(create_app()) as client:
        suffix = uuid.uuid4().hex
        def register(role):
            email = f'{role}-{uuid.uuid4().hex}@example.com'
            assert client.post('/users/', json={'email':email,'password':'Test-password-123','role':'buyer'}).status_code == 201
            r = client.post('/users/token', data={'username':email,'password':'Test-password-123'})
            return {'Authorization':'Bearer '+r.json()['access_token']}
        seller = register('staff')
        buyers = [register('buyer'), register('buyer')]
        # Seed category directly: category management is admin-only.
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from app.config import settings
        from app.models.categories import CategoryModel
        async def category():
            engine = create_async_engine(settings.database_url)
            try:
                async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                    item = CategoryModel(name='Concurrency '+suffix[:8])
                    db.add(item)
                    await db.commit()
                    return item.id
            finally:
                await engine.dispose()
        async def authorize_staff():
            engine = create_async_engine(settings.database_url)
            from app.models.users import UserModel
            import jwt
            from app.config import SECRET_KEY, ALGORITHM
            email = jwt.decode(seller['Authorization'][7:], SECRET_KEY, algorithms=[ALGORITHM])['sub']
            try:
                async with async_sessionmaker(engine)() as db:
                    user = await db.scalar(__import__('sqlalchemy').select(UserModel).where(UserModel.email == email))
                    user.role = 'staff'
                    await db.commit()
            finally:
                await engine.dispose()
        asyncio.run(authorize_staff())
        category_id = asyncio.run(category())
        product = client.post('/products/',headers=seller,data={'name':'Last pair '+suffix[:8], 'price':'12.34','stock':1,'category_id':category_id})
        assert product.status_code == 201, product.text
        pid = product.json()['id']
        for headers in buyers:
            assert client.post('/cart/',headers=headers,json={'product_id':pid,'quantity':1}).status_code == 201
        def checkout(pair):
            index, headers = pair
            return client.post('/orders/checkout',headers={**headers,'Idempotency-Key':suffix+str(index)})
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(checkout, enumerate(buyers)))
        assert sorted(r.status_code for r in responses) == [201,400]
        winner = next(i for i,r in enumerate(responses) if r.status_code == 201)
        repeat = checkout((winner,buyers[winner]))
        assert repeat.json()['id'] == responses[winner].json()['id']
        assert repeat.json()['total_amount'] == '12.34'
        assert client.get(f'/products/{pid}').json()['stock'] == 0
        assert client.get('/cart/',headers=buyers[winner]).json()['items'] == []
        loser = 1-winner
        assert client.get('/cart/',headers=buyers[loser]).json()['total_quantity'] == 1
        assert client.get('/orders/'+str(repeat.json()['id']),headers=buyers[loser]).status_code == 404
        assert client.get('/orders/',headers=buyers[loser]).json()['total'] == 0
        with ThreadPoolExecutor(2) as pool:
            duplicates = list(pool.map(lambda _: checkout((winner,buyers[winner])), range(2)))
        assert {r.json()['id'] for r in duplicates} == {repeat.json()['id']}

        missing = client.post('/reviews/',headers=buyers[winner],json={'product_id':2147483647,'comment':'test','grade':5})
        assert missing.status_code == 400
        review = {'product_id':pid,'comment':'Good','grade':5}
        assert client.post('/reviews/',headers=buyers[winner],json=review).status_code == 201
        assert client.post('/reviews/',headers=buyers[winner],json=review).status_code == 400
        assert client.get(f'/products/{pid}').json()['rating'] == 5
        # A later unavailable line must roll back an earlier stock change.
        client.delete(f'/cart/items/{pid}', headers=buyers[loser])
        products = []
        for stock in (2, 0):
            response = client.post('/products/', headers=seller, data={
                'name':'Rollback '+uuid.uuid4().hex[:8], 'price':'10.25',
                'stock':stock, 'category_id':category_id})
            assert response.status_code == 201
            products.append(response.json()['id'])
            assert client.post('/cart/',headers=buyers[loser],json={
                'product_id':products[-1], 'quantity':1}).status_code == 201
        assert client.post('/orders/checkout',headers=buyers[loser]).status_code == 400
        assert client.get(f'/products/{products[0]}').json()['stock'] == 2
        assert client.get('/cart/',headers=buyers[loser]).json()['total_quantity'] == 2
        assert client.get('/orders/',headers=buyers[loser]).json()['total'] == 0


@pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires PostgreSQL and Redis')
def test_refresh_reuse_revokes_session():
    with TestClient(create_app()) as client:
        email = f'session-{uuid.uuid4().hex}@example.com'
        assert client.post('/users/', json={'email':email,'password':'Test-password-123'}).status_code == 201
        pair = client.post('/users/token', data={'username':email,'password':'Test-password-123'}).json()
        rotated = client.post('/users/refresh-token', json={'refresh_token':pair['refresh_token']})
        assert rotated.status_code == 200
        headers = {'Authorization':'Bearer '+rotated.json()['access_token']}
        assert client.get('/cart/',headers=headers).status_code == 200
        assert client.post('/users/refresh-token', json={'refresh_token':pair['refresh_token']}).status_code == 401
        assert client.get('/cart/',headers=headers).status_code == 401
        pair = client.post('/users/token', data={'username':email,'password':'Test-password-123'}).json()
        headers = {'Authorization':'Bearer '+pair['access_token']}
        assert client.post('/users/logout',headers=headers).status_code == 204
        assert client.get('/cart/',headers=headers).status_code == 401
        pair = client.post('/users/token', data={'username':email,'password':'Test-password-123'}).json()
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(lambda _: client.post('/users/refresh-token',
                json={'refresh_token':pair['refresh_token']}), range(2)))
        assert sorted(r.status_code for r in responses) == [200,401]
        issued = next(r.json()['access_token'] for r in responses if r.status_code == 200)
        assert client.get('/cart/', headers={'Authorization':'Bearer '+issued}).status_code == 401


@pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires Redis')
def test_shared_auth_rate_limit(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, 'rate_limit_enabled', True)
    with TestClient(create_app(), client=('rate-test-'+uuid.uuid4().hex, 50000)) as client:
        for _ in range(30):
            assert client.post('/users/token', data={}).status_code == 422
        response = client.post('/users/token', data={})
        assert response.status_code == 429
        assert response.headers['retry-after'] == '60'
        assert response.headers['x-request-id'] == response.json()['request_id']

@pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires PostgreSQL and Redis')
def test_redis_failure_denies_access(monkeypatch):
    from unittest.mock import AsyncMock
    with TestClient(create_app()) as client:
        email = f'outage-{uuid.uuid4().hex}@example.com'
        assert client.post('/users/', json={'email':email,'password':'Test-password-123'}).status_code == 201
        pair = client.post('/users/token', data={'username':email,'password':'Test-password-123'}).json()
        monkeypatch.setattr(client.app.state.redis, 'exists', AsyncMock(side_effect=ConnectionError()))
        response = client.get('/cart/', headers={'Authorization':'Bearer '+pair['access_token']})
        assert response.status_code == 503
        assert 'access_token' not in response.text

@pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='Requires test PostgreSQL and Redis')
def test_admin_exclusively_assigns_staff_and_specs():
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.models.users import UserModel
    with TestClient(create_app()) as client:
        email = 'admin-'+uuid.uuid4().hex+'@example.com'
        other = 'buyer-'+uuid.uuid4().hex+'@example.com'
        for role in ('staff','seller','admin'):
            assert client.post('/users/',json={'email':other,'password':'Test-password-123','role':role}).status_code == 422
        admin_id = client.post('/users/',json={'email':email,'password':'Test-password-123'}).json()['id']
        buyer_id = client.post('/users/',json={'email':other,'password':'Test-password-123'}).json()['id']
        async def bootstrap_admin():
            engine=create_async_engine(settings.database_url)
            try:
                async with async_sessionmaker(engine)() as db:
                    user=await db.scalar(select(UserModel).where(UserModel.id==admin_id))
                    user.role='admin'
                    await db.commit()
            finally:
                await engine.dispose()
        asyncio.run(bootstrap_admin())
        def login(email):
            pair=client.post('/users/token',data={'username':email,'password':'Test-password-123'}).json()
            return {'Authorization':'Bearer '+pair['access_token']}
        admin, buyer=login(email), login(other)
        endpoint=f'/users/{buyer_id}/role'
        assert client.patch(endpoint,headers=buyer,json={'role':'staff'}).status_code==403
        assert client.get('/users/',headers=buyer).status_code==403
        assert client.patch(endpoint,headers=admin,json={'role':'admin'}).status_code==422
        assert client.patch(endpoint,headers=admin,json={'role':'staff'}).json()['role']=='staff'
        assert client.get('/users/me',headers=buyer).json()['role']=='staff'
        assert client.patch(endpoint,headers=buyer,json={'role':'buyer'}).status_code==403
        category=client.post('/categories/',headers=admin,json={'name':'Specs '+uuid.uuid4().hex[:8]}).json()['id']
        import json
        data={'name':'Specs glasses','price':'100.25','stock':2,'category_id':category,
              'specifications':json.dumps({'frame_material':'Ацетат','lens_width_mm':54,'polarized':False})}
        response=client.post('/products/',headers=buyer,data=data)
        assert response.status_code==201, response.text
        assert response.json()['specifications']['lens_width_mm']==54
        assert response.json()['specifications']['polarized'] is False
        data['specifications']='{"lens_width_mm": -1}'
        assert client.post('/products/',headers=buyer,data=data).status_code==422
        assert client.patch(endpoint,headers=admin,json={'role':'buyer'}).status_code==200
        data['specifications']='{}'
        assert client.post('/products/',headers=buyer,data=data).status_code==403
        assert client.patch(f'/users/{admin_id}/role',headers=admin,json={'role':'buyer'}).status_code==409
