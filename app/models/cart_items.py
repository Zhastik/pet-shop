from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class CartItemModel(Base):
    __tablename__ = "cart_items"

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_cart_quantity"),
        UniqueConstraint("user_id", "product_id", name = "uq_cart_items_user_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable= False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    update_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete= "CASCADE"), nullable=False, index=True)
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="cart_items")

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete= "CASCADE"), nullable= False, index=True)
    product: Mapped["ProductModel"] = relationship("ProductModel", back_populates="cart_items")

