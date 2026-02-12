from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from starlette.status import HTTP_404_NOT_FOUND

from app.models.products import ProductModel
from app.models.categories import CategoryModel
from app.models.reviews import ReviewModel
from app.routers.products import update_product_rating
from app.schemas import ReviewSchema, ReviewCreate
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import UserModel
from app.auth import get_current_seller, get_current_buyer, get_current_admin

from app.db_depends import get_async_db

router = APIRouter(prefix="/reviews", tags=["reviews"])

@router.get("/", response_model=list[ReviewSchema])
async def get_all_reviews(db: AsyncSession = Depends(get_async_db)):
    reviews = await db.scalars(
        select(ReviewModel).where(ReviewModel.is_active == True)
    )
    res_review = reviews.all()
    return res_review

@router.get("/products/{product_id}/", response_model=list[ReviewSchema])
async def get_review_by_product(product_id: int, db: AsyncSession = Depends(get_async_db)):
    product = await db.scalar(
        select(ProductModel).where(ProductModel.id == product_id, ProductModel.is_active == True)
    )
    if not product:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Not Found")
    review = await db.scalars(
        select(ReviewModel).where(ReviewModel.product_id == product_id,ReviewModel.is_active == True)
    )
    res_review = review.all()
    return res_review

@router.post("/", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_review(
        review: ReviewCreate,
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_buyer)
):
    product = db.scalar(
        select(ProductModel).where(ProductModel.id == review.product_id, ProductModel.is_active == True)
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    db_review = ReviewModel(**review.model_dump(), user_id = current_user.id)
    try:
        db.add(db_review)
        await db.flush()
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже оставляли отзыв на этот товар"
        )

    await update_product_rating(db, review.product_id)
    await db.commit()
    await db.refresh(db_review)
    return db_review

@router.delete("/{review_id}", response_model=ReviewSchema)
async def delete_review(
        review_id: int,
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_admin)
):
    res_review = await db.scalar(
        select(ReviewModel).where(ReviewModel.id == review_id, ReviewModel.is_active == True)
    )
    if not res_review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found or inactive")

    res_product = await db.scalar(
        select(ProductModel).where(ProductModel.id == res_review.product_id, ProductModel.is_active == True)
    )
    if not res_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Если пользователь не является автором отзыва или не имеет роли admin")

    res_review.is_active = False

    await db.flush()
    await update_product_rating(db, res_review.product_id)

    await db.commit()
    return res_review