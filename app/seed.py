import asyncio
import secrets
from decimal import Decimal
from sqlalchemy import select
from app import models  # noqa: F401 -- register ORM models
from app.database import async_session_maker, async_engine
from app.auth import hash_password
from app.models.users import UserModel
from app.models.categories import CategoryModel
from app.models.products import ProductModel


CATALOG = [('FORMA Everyday', 'Солнцезащитные очки', '4990.00', 25, 'Шоколадная оправа и дымчатые линзы. Лаконичный силуэт для прогулок по городу.', 'everyday.svg'), ('FORMA Riviera', 'Солнцезащитные очки', '6490.00', 18, 'Черепаховая оправа с мягкими углами и тёплыми коричневыми линзами. Настроение летнего побережья.', 'riviera.svg'), ('FORMA Aviator', 'Солнцезащитные очки', '7290.00', 14, 'Тонкая металлическая оправа цвета золота и каплевидные зелёные линзы. Классика для большого города.', 'aviator.svg'), ('FORMA Noir', 'Солнцезащитные очки', '5990.00', 22, 'Выразительная чёрная оправа с широкими дужками и графитовыми линзами. Акцент для повседневного образа.', 'noir.svg'), ('FORMA Rose', 'Солнцезащитные очки', '5490.00', 16, 'Оправа кошачий глаз в пудровом оттенке с розово-коричневыми линзами. Мягкие линии с характером.', 'rose.svg'), ('FORMA Sahara', 'Солнцезащитные очки', '4790.00', 30, 'Песочная круглая оправа и карамельные линзы. Лёгкий визуальный акцент в тёплой палитре.', 'sahara.svg'), ('FORMA Studio', 'Оправы для зрения', '3990.00', 20, 'Круглая оправа цвета тёмного графита с прозрачными демонстрационными линзами. Рецептурные линзы приобретаются отдельно.', 'studio.svg'), ('FORMA Line', 'Оправы для зрения', '4590.00', 24, 'Тонкая прямоугольная оправа серебристого цвета. Прозрачные демонстрационные линзы без диоптрий.', 'line.svg'), ('FORMA Olive', 'Оправы для зрения', '4290.00', 12, 'Оливковая оправа со скруглёнными углами. Спокойный цвет и прозрачные демонстрационные линзы без диоптрий.', 'olive.svg'), ('FORMA Amber', 'Оправы для зрения', '5190.00', 15, 'Янтарная оправа округлой формы с полупрозрачным эффектом. Демонстрационные линзы без диоптрий.', 'amber.svg'), ('FORMA Motion', 'Спортивные очки', '6790.00', 10, 'Обтекаемая тёмно-синяя оправа и вытянутые дымчатые линзы. Динамичный силуэт для активного образа.', 'motion.svg'), ('FORMA Mini', 'Детские очки', '2990.00', 28, 'Компактная оправа кораллового цвета и дымчатые линзы. Яркая модель детской коллекции; размер подбирается при примерке.', 'mini.svg')]


async def seed():
    """Add missing catalog models; preserve existing stock and prices."""
    async with async_session_maker() as db:
        async with db.begin():
            seller = await db.scalar(select(UserModel).where(UserModel.email == 'catalog@forma.example'))
            if seller is None:
                seller = UserModel(email='catalog@forma.example', role='buyer', is_active=False,
                                   hashed_password=hash_password(secrets.token_urlsafe(32)))
                db.add(seller)
                await db.flush()
            for name, category_name, price, stock, description, image in CATALOG:
                existing = await db.scalar(select(ProductModel).where(ProductModel.name == name))
                specs = {
                    'brand': 'FORMA', 'model': name.replace('FORMA ', ''),
                    'sku': 'SM-' + image.replace('.svg', '').upper(),
                    'purpose': category_name, 'frame_shape': 'Округлая',
                    'frame_material': 'Ацетат', 'frame_color': 'По изображению модели',
                    'lens_color': 'Прозрачные' if category_name == 'Оправы для зрения' else 'Дымчатые',
                    'lens_width_mm': 50 if category_name == 'Детские очки' else 54,
                    'bridge_width_mm': 18, 'temple_length_mm': 140,
                    'prescription_ready': category_name == 'Оправы для зрения',
                    'included': 'Очки, футляр, салфетка',
                    'care': 'Очищайте мягкой салфеткой. Храните в футляре. Избегайте высоких температур.',
                    'demo': True,
                }
                if 'Aviator' in name or 'Line' in name:
                    specs.update(frame_material='Металл', frame_shape='Авиатор' if 'Aviator' in name else 'Прямоугольная')
                if 'Rose' in name:
                    specs['frame_shape'] = 'Кошачий глаз'
                if existing:
                    if not existing.specifications:
                        existing.specifications = specs
                    continue
                category = await db.scalar(select(CategoryModel).where(CategoryModel.name == category_name))
                if category is None:
                    category = CategoryModel(name=category_name)
                    db.add(category)
                    await db.flush()
                db.add(ProductModel(name=name, description=description, price=Decimal(price),
                                    stock=stock, category_id=category.id, seller_id=seller.id,
                                    image_url='/shop/' + image, specifications=specs))
    print('Starter catalog ready')


async def main():
    try:
        await seed()
    finally:
        await async_engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
