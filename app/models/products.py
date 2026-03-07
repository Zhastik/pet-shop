from decimal import Decimal
from enum import unique

from sqlalchemy import String, Boolean, Integer, Numeric, ForeignKey, Float, text, Computed, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.orders import OrderItemModel


class ProductModel(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2) )
    image_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stock: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)
    category: Mapped["CategoryModel"] = relationship("CategoryModel", back_populates="products")

    seller_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    seller: Mapped["UserModel"] = relationship("UserModel", back_populates="products")

    rating: Mapped[float] = mapped_column(Float, default=0.0, server_default=text('0'))
    reviews: Mapped[list["ReviewModel"]] = relationship("ReviewModel", back_populates="product")

    cart_items: Mapped[list["CartItemModel"]] = relationship("CartItemModel", back_populates="product", cascade="all, delete-orphan")
    order_items: Mapped[list["OrderItemModel"]] = relationship("OrderItemModel", back_populates="product")

    tsv: Mapped[TSVECTOR] = mapped_column(
        TSVECTOR,
        Computed(
            """
            setweight(to_tsvector('english', coalesce(name, '')), 'A')
            || 
            setweight(to_tsvector('english', coalesce(description, '')), 'B')
            """,
            persisted=True,
        ),
        nullable=False
    )

    __table_args__ = (
        Index("ix_products_tsv_gin", "tsv", postgresql_using="gin"),
    )