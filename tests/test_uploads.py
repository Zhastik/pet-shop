import io
import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from app.routers import products


@pytest.mark.asyncio
async def test_rejects_disguised_image(tmp_path, monkeypatch):
    monkeypatch.setattr(products, 'MEDIA_ROOT', tmp_path)
    upload = UploadFile(io.BytesIO(b'<script>alert(1)</script>'), filename='image.jpg',
                        headers=Headers({'content-type':'image/jpeg'}))
    with pytest.raises(HTTPException) as error:
        await products.save_product_image(upload)
    assert error.value.status_code == 400
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_image_delete_cannot_escape_media(tmp_path, monkeypatch):
    media = tmp_path / 'media'
    media.mkdir()
    outside = tmp_path / 'keep.txt'
    outside.write_text('keep')
    monkeypatch.setattr(products, 'BASE_DIR', tmp_path)
    monkeypatch.setattr(products, 'MEDIA_ROOT', media)
    await products.remove_product_image('/keep.txt')
    assert outside.read_text() == 'keep'
