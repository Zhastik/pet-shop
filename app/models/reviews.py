from datetime import datetime
from decimal import Decimal
from enum import unique

from sqlalchemy import String, Boolean, Integer, Numeric, ForeignKey, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base

class ReviewModel(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_date: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="reviews")

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    product: Mapped["ProductModel"] = relationship("ProductModel", back_populates="reviews")

    @validates("grade")
    def validate_grade(self, key, value):
        if value < 1 or value > 5:
            raise ValueError('Количество должно быть от 1 до 5')
        return value

    __table_args__ = (
        UniqueConstraint('user_id', 'product_id'),
    )