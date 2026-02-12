from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from unicodedata import category

from app.database import Base

class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable= True)
    products: Mapped[list["ProductModel"]] = relationship("ProductModel", back_populates="category")

    parent: Mapped["CategoryModel | None"] = relationship("CategoryModel", back_populates="children", remote_side="CategoryModel.id")

    children: Mapped[list["CategoryModel"]] = relationship("CategoryModel", back_populates="parent")


