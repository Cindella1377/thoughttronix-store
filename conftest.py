"""Project-wide pytest fixtures.

Shared test data lives here as plain fixtures — no factories. The suite
grows with the project; tests never invoke the seed command.
"""

import datetime
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from orders.models import Cart, CartItem, Coupon, Order
from products.models import Category, Product, Tag


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Point uploads at a temporary directory. Applied to every test, so
    nothing — the seed tests included — can touch the real ``media/``."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture
def photo():
    """A tiny real image, generated in memory, as a staff upload."""
    buffer = BytesIO()
    Image.new("RGB", (4, 5), "purple").save(buffer, format="PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(
        username="customer",
        email="customer@example.com",
        password="customer123",
    )


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="employee",
        email="employee@example.com",
        password="employee123",
        is_staff=True,
        job_title="Junior Thought Curator",
    )


@pytest.fixture
def category(db):
    return Category.objects.create(name="Home Assistants", slug="home-assistants")


@pytest.fixture
def product(category):
    return Product.objects.create(
        name="Seraphine Home Hub",
        slug="seraphine-home-hub",
        tagline="She's always listening. In a good way.",
        description="The flagship Seraphine hub with a seven-microphone array.",
        price=Decimal("349.99"),
        category=category,
    )


@pytest.fixture
def unavailable_product(category):
    return Product.objects.create(
        name="EchoPatch",
        slug="echopatch",
        tagline="Never miss a word. Anyone's.",
        price=Decimal("139.00"),
        is_available=False,
        category=category,
    )


@pytest.fixture
def featured_product(category):
    return Product.objects.create(
        name="SoulSear Mark II",
        slug="soulsear-mark-ii",
        tagline="Warmth you can feel. Mostly.",
        price=Decimal("899.00"),
        is_featured=True,
        category=category,
    )


@pytest.fixture
def tag(db):
    return Tag.objects.create(name="bestseller", slug="bestseller")


@pytest.fixture
def cart(customer):
    return Cart.for_user(customer)


@pytest.fixture
def cart_item(cart, product):
    return CartItem.objects.create(cart=cart, product=product, quantity=2)


# A fixed moment for coupon tests: time-dependent code takes ``now``.
COUPON_NOW = datetime.datetime(2026, 10, 1, 12, 0, tzinfo=datetime.UTC)


@pytest.fixture
def now():
    return COUPON_NOW


@pytest.fixture
def make_coupon(db):
    """Build a coupon, active around ``COUPON_NOW`` unless dates are given."""

    def make(code, value="10", **fields):
        fields.setdefault("discount_type", Coupon.DiscountType.PERCENT)
        fields.setdefault("starts_at", COUPON_NOW - datetime.timedelta(days=30))
        fields.setdefault("expires_at", COUPON_NOW + datetime.timedelta(days=30))
        return Coupon.objects.create(code=code, value=Decimal(value), **fields)

    return make


@pytest.fixture
def expired(make_coupon, now):
    """Build a coupon that expired a day before ``COUPON_NOW``."""

    def make(code, value="10", **fields):
        fields.setdefault("starts_at", now - datetime.timedelta(days=60))
        fields.setdefault("expires_at", now - datetime.timedelta(days=1))
        return make_coupon(code, value, **fields)

    return make


@pytest.fixture
def coupon(make_coupon):
    return make_coupon("FALL10", is_public=True)


@pytest.fixture
def cart_80(cart, category):
    """A cart totalling exactly $80.00, so coupon savings are easy to read."""
    product = Product.objects.create(
        name="MindSync Charger",
        slug="mindsync-charger",
        price=Decimal("40.00"),
        category=category,
    )
    CartItem.objects.create(cart=cart, product=product, quantity=2)
    return cart


@pytest.fixture
def make_order(db):
    """Build an order of one product for a user, in the given status."""

    def make(user, product, status=Order.Status.DELIVERED):
        order = Order.objects.create(
            user=user, status=status, total=product.price, email=user.email
        )
        order.items.create(
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=1,
        )
        return order

    return make


@pytest.fixture
def delivered_order(make_order, customer, product):
    """``customer`` received ``product``: a confirmed buyer who may review it."""
    return make_order(customer, product)
