import unittest
from decimal import Decimal
from pydantic import ValidationError
from app.schemas import CartSchema, UserCreate, OrderSchema


class SchemaRegressionTests(unittest.TestCase):
    def test_public_registration_rejects_admin(self):
        with self.assertRaises(ValidationError):
            UserCreate(email="user@example.com", password="password123", role="admin")

    def test_public_registration_accepts_buyer(self):
        for role in ("buyer",):
            self.assertEqual(UserCreate(email="user@example.com", password="password123", role=role).role, role)

    def test_invalid_product_form_returns_validation_error(self):
        from app.schemas import ProductCreate
        from fastapi.exceptions import RequestValidationError
        with self.assertRaises(RequestValidationError):
            ProductCreate.as_form(name='Invalid', price=Decimal('-1'), stock=1, category_id=1)

    def test_cart_preserves_fractional_currency(self):
        cart = CartSchema(user_id=1, total_quantity=0, total_price=Decimal("12.34"))
        self.assertEqual(cart.total_price, Decimal("12.34"))

    def test_order_preserves_fractional_currency(self):
        order = OrderSchema(id=1, user_id=1, status="pending", total_amount=Decimal("12.34"),
                            created_at="2026-01-01T00:00:00Z", update_at="2026-01-01T00:00:00Z")
        self.assertEqual(order.total_amount, Decimal("12.34"))


if __name__ == "__main__":
    unittest.main()
