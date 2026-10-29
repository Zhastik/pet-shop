from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.db_depends import get_async_db
from app.models.cart_items import CartItemModel
from app.models.products import ProductModel
from app.models.users import UserModel
from app.schemas import (
    CartSchema,
    CartItemSchema,
    CartItemCreate,
    CartItemUpdate,
)

router = APIRouter(prefix="/cart", tags=["cart"])

async def _ensure_product_available(product_id: int, db: AsyncSession = Depends(get_async_db)) -> None:
    result = await db.scalars(select(ProductModel)
            .where(ProductModel.id == product_id, ProductModel.is_active == True))

    product = result.first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

async def _get_cart_item(user_id: int, product_id: int, db: AsyncSession = Depends(get_async_db)) -> CartItemModel | None:
    result = await db.scalars(
        select(CartItemModel).options(selectinload(CartItemModel.product))
        .where(CartItemModel.user_id == user_id, CartItemModel.product_id == product_id)
    )
    return result.first()


@router.get("/", response_model=CartSchema)
async def get_cart(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    result = await db.scalars(
        select(CartItemModel)
        .options(selectinload(CartItemModel.product))
        .where(CartItemModel.user_id == current_user.id)
        .order_by(CartItemModel.id)
    )

    items = result.all()

    total_quantity = sum(item.quantity for item in items)

    price_items = (
        Decimal(item.quantity) * (item.product.price if item.product.price is not None else Decimal("0"))
        for item in items
    )

    total_price_decimal = sum(price_items, Decimal("0.00"))

    return CartSchema(
        user_id=current_user.id,
        items=items,
        total_quantity = total_quantity,
        total_price = total_price_decimal
    )

@router.post("/", response_model=CartItemSchema, status_code=status.HTTP_201_CREATED)
async def add_item_to_cart(
        payload: CartItemCreate,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    await _ensure_product_available(payload.product_id, db)

    cart_item = await _get_cart_item(current_user.id, payload.product_id, db)
    if cart_item:
        cart_item.quantity += payload.quantity
    else:
        cart_item = CartItemModel(
            user_id = current_user.id,
            product_id = payload.product_id,
            quantity = payload.quantity
        )
        db.add(cart_item)

    await db.commit()
    updated_item = await _get_cart_item(current_user.id, payload.product_id, db)
    return updated_item

@router.put("/items/{product_id}", response_model=CartItemSchema)
async def update_cart_item(
        product_id: int,
        payload: CartItemUpdate,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    await _ensure_product_available(product_id, db)
    cart_item = await _get_cart_item(current_user.id, product_id, db)
    if not cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Cart item not found")

    cart_item.quantity = payload.quantity
    await db.commit()
    update_item = await _get_cart_item(current_user.id, product_id, db)
    return update_item

@router.delete("/items/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item_from_cart(
        product_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    cart_item = await _get_cart_item(current_user.id, product_id, db)
    if not cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    await db.delete(cart_item)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    await db.execute(delete(CartItemModel).where(CartItemModel.user_id == current_user.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
