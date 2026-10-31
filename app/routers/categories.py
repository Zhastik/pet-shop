from app.auth import get_current_admin
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.categories import CategoryModel as CategoryModel
from app.schemas import CategorySchema as CategorySchema, CategoryCreate
from app.db_depends import get_async_db

router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)

@router.get("/", response_model=list[CategorySchema])
async def get_all_categories(db: AsyncSession = Depends(get_async_db)):
    stmt = select(CategoryModel).where(CategoryModel.is_active == True)
    res_categories = await db.scalars(stmt)
    categories = res_categories.all()
    return categories


@router.post("/", dependencies=[Depends(get_current_admin)], response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate, db: AsyncSession = Depends(get_async_db)):
    if category.parent_id is not None:
        stmt = select(CategoryModel).where(CategoryModel.id == category.parent_id,
                                           CategoryModel.is_active == True)
        res_parent = await db.scalars(stmt)
        parent = res_parent.first()
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent category not found")

    # Создание новой категории
    db_category = CategoryModel(**category.model_dump())
    db.add(db_category)
    await db.commit()
    return db_category

@router.delete("/{category_id}", dependencies=[Depends(get_current_admin)], status_code=status.HTTP_200_OK)
async def delete_category(category_id: int, db: AsyncSession=Depends(get_async_db)):
    stmt = select(CategoryModel).where(CategoryModel.id == category_id, CategoryModel.is_active == True)
    res_categories = await db.scalars(stmt)
    category = res_categories.first()
    if category is None:
        raise HTTPException(status_code=404, detail="Not found")

    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(is_active = False))
    await db.commit()

    return {"status": "success", "message": "CategoryModel marked as inactive"}

@router.put("/{category_id}", dependencies=[Depends(get_current_admin)], response_model=CategorySchema)
async def update_category(category_id: int, category: CategoryCreate, db: AsyncSession=Depends(get_async_db)):
    stmt = select(CategoryModel).where(CategoryModel.id == category_id, CategoryModel.is_active == True)
    res_categories = await db.scalars(stmt)
    db_category = res_categories.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Not found")

    if category.parent_id is not None:
        parent_stmt = select(CategoryModel).where(CategoryModel.id == category.parent_id, CategoryModel.is_active == True)
        res_parent = await db.scalars(parent_stmt)
        parent = res_parent.first()
        if parent is None:
            raise HTTPException(status_code=404, detail="Not found")

    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(**category.model_dump()))

    await db.commit()
    return db_category