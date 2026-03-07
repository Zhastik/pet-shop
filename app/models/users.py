from decimal import Decimal

from sqlalchemy import String, Boolean, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.orders import OrderModel


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key= True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String, default="buyer")

    products: Mapped[list["ProductModel"]] = relationship("ProductModel", back_populates="seller")
    reviews: Mapped[list["ReviewModel"]] = relationship("ReviewModel", back_populates="user")
    cart_items: Mapped[list["CartItemModel"]] = relationship("CartItemModel", back_populates="user", cascade="all, delete-orphan")
    orders: Mapped[list["OrderModel"]] = relationship("OrderModel", back_populates="user", cascade="all, delete-orphan")