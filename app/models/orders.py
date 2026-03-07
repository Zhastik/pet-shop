from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Boolean, Integer, Numeric, ForeignKey, Text, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    update_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable= False, index=True)
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="orders")

    items: Mapped[list["OrderItemModel"]] = relationship("OrderItemModel", back_populates="order", cascade="all, delete-orphan")

class OrderItemModel(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable= False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable= False)

    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="items")

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable= False)
    product: Mapped["ProductModel"] = relationship("ProductModel", back_populates="order_items")