from app.services.audit import audit
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from app.models.products import ProductModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.db_depends import get_async_db
from app.models.cart_items import CartItemModel
from app.models.orders import OrderModel, OrderItemModel
from app.models.users import UserModel
from app.schemas import OrderSchema, OrderListSchema

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)

async def _load_order_with_items(order_id: int, db: AsyncSession) -> OrderModel:
    result = await db.scalars(
        select(OrderModel).options(
            selectinload(OrderModel.items).selectinload(OrderItemModel.product)
        ).where(OrderModel.id == order_id)
    )
    return result.first()

@router.post("/checkout", response_model=OrderSchema, status_code=status.HTTP_201_CREATED)
async def checkout_order(
        idempotency_key: str | None = Header(None, max_length=128),
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    """
        Создаёт заказ на основе текущей корзины пользователя.
        Сохраняет позиции заказа, вычитает остатки и очищает корзину.
    """
    # Serialize checkout for a user, including duplicate requests.
    await db.scalar(select(UserModel).where(UserModel.id == current_user.id).with_for_update())
    if idempotency_key:
        existing = await db.scalar(select(OrderModel).where(
            OrderModel.user_id == current_user.id, OrderModel.idempotency_key == idempotency_key))
        if existing:
            return await _load_order_with_items(existing.id, db)
    cart_result = await db.scalars(
        select(CartItemModel).options(selectinload(CartItemModel.product))
        .where(CartItemModel.user_id == current_user.id).order_by(CartItemModel.id)
    )
    cart_items = cart_result.all()
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    product_ids = sorted({item.product_id for item in cart_items})
    locked = (await db.scalars(select(ProductModel).where(ProductModel.id.in_(product_ids))
              .order_by(ProductModel.id).with_for_update().execution_options(populate_existing=True))).all()
    products = {product.id: product for product in locked}
    order = OrderModel(user_id=current_user.id, idempotency_key=idempotency_key)
    total_amout = Decimal("0")

    for cart_item in cart_items:
        product = products.get(cart_item.product_id)
        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {cart_item.product_id} is unavailable",
            )
        if product.stock < cart_item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough stock for product {product.name}"
            )
        unit_price = product.price
        if not unit_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {product.name} has no price set"
            )
        total_price = unit_price * cart_item.quantity
        total_amout += total_price
        order_item = OrderItemModel(
            product_id = cart_item.product_id,
            quantity = cart_item.quantity,
            total_price = total_price,
            unit_price = unit_price
        )

        order.items.append(order_item)

        product.stock -= cart_item.quantity

    order.total_amount = total_amout
    db.add(order)

    await db.execute(delete(CartItemModel).where(CartItemModel.id.in_([item.id for item in cart_items])))
    await db.flush()
    await audit(db, current_user.id, 'order.created', order.id)
    await db.commit()

    created_order = await _load_order_with_items(order.id, db)
    if not created_order:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load created order"
        )
    return created_order

@router.get('/', response_model=OrderListSchema)
async def list_orders(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    """
        Возвращает заказы текущего пользователя с простой пагинацией.
    """
    total = await db.scalar(
        select(func.count(OrderModel.id)).where(OrderModel.user_id == current_user.id)
    )

    result = await db.scalars(
        select(OrderModel).options(selectinload(OrderModel.items).selectinload(OrderItemModel.product))
        .where(OrderModel.user_id == current_user.id).order_by(OrderModel.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    orders = result.all()
    return OrderListSchema(
        items=orders,
        total=total or 0,
        page=page,
        page_size=page_size
    )

@router.get("/{order_id}", response_model=OrderSchema)
async def get_order(
        order_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    order = await _load_order_with_items(order_id, db)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order