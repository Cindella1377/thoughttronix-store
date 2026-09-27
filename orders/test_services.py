"""place_order tests — coverage priority 3 in the PRD.

Denormalization, cart emptying, atomicity, unavailable rejection, and
the card_last4-only rule.
"""

import datetime
from decimal import Decimal

import pytest

from products.models import Product

from .models import CartItem, Coupon, Order, OrderItem
from .services import apply_coupon, place_order, refresh_cart_coupon
from .test_checkout_form import VALID_DATA


@pytest.fixture
def checkout_data():
    return dict(VALID_DATA)


def test_creates_an_order_with_denormalized_snapshot(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data)

    assert order.user == cart.user
    assert order.total == Decimal("699.98")
    assert order.status == Order.Status.PLACED
    item = order.items.get()
    assert item.product_name == "Seraphine Home Hub"
    assert item.unit_price == Decimal("349.99")
    assert item.quantity == 2
    assert item.line_total == Decimal("699.98")


def test_order_history_survives_catalog_changes(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data)

    product = cart_item.product
    product.name = "Seraphine Home Hub II"
    product.price = Decimal("999.00")
    product.save()

    item = order.items.get()
    assert item.product_name == "Seraphine Home Hub"
    assert item.unit_price == Decimal("349.99")


def test_addresses_and_email_are_copied_onto_the_order(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data)

    assert order.email == "casey@example.com"
    assert order.shipping_street == "12 Cortex Lane"
    assert order.shipping_line2 == "Unit 7"
    assert order.shipping_state == "TX"
    assert order.billing_zip == "79015-1234"


def test_only_the_last_four_card_digits_are_stored(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data)

    assert order.card_last4 == "4242"
    stored = [field.name for field in Order._meta.get_fields()]
    assert "card_number" not in stored
    assert "card_cvv" not in stored
    assert "card_expiry" not in stored


def test_the_cart_is_emptied(cart, cart_item, checkout_data):
    place_order(cart, cart.user, checkout_data)

    assert not cart.items.exists()
    assert cart.total() == Decimal("0.00")


def test_an_empty_cart_is_rejected(cart, checkout_data):
    with pytest.raises(ValueError):
        place_order(cart, cart.user, checkout_data)

    assert not Order.objects.exists()


def test_an_unavailable_product_is_rejected(
    cart, cart_item, unavailable_product, checkout_data
):
    cart.items.create(product=unavailable_product)

    with pytest.raises(ValueError, match="EchoPatch"):
        place_order(cart, cart.user, checkout_data)

    assert not Order.objects.exists()
    assert cart.items.count() == 2  # the cart is untouched


def test_a_failure_midway_leaves_no_partial_order(
    cart, cart_item, category, checkout_data, monkeypatch
):
    """All-or-nothing: if any line fails, no order and no emptied cart."""
    cart.add(
        Product.objects.create(
            name="Charging Pillow",
            slug="charging-pillow",
            price=Decimal("69.00"),
            category=category,
        )
    )

    original = OrderItem.objects.create
    calls = {"count": 0}

    def create_then_explode(**kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("boom")
        return original(**kwargs)

    monkeypatch.setattr(OrderItem.objects, "create", create_then_explode)

    with pytest.raises(RuntimeError):
        place_order(cart, cart.user, checkout_data)

    assert not Order.objects.exists()
    assert not OrderItem.objects.exists()
    assert CartItem.objects.count() == 2


# Coupons — coverage priority 4 in the coupons PRD. The cart totals $80.00.


def test_an_order_without_a_coupon_records_no_discount(cart_80, checkout_data, now):
    order = place_order(cart_80, cart_80.user, checkout_data, now=now)

    assert order.total == Decimal("80.00")
    assert order.discount == Decimal("0.00")
    assert order.coupon is None
    assert order.coupon_code == ""


def test_the_cart_coupon_is_charged_and_snapshotted(
    cart_80, coupon, checkout_data, now
):
    cart_80.coupon = coupon
    cart_80.save()

    order = place_order(cart_80, cart_80.user, checkout_data, now=now)

    assert order.total == Decimal("72.00")
    assert order.discount == Decimal("8.00")
    assert order.coupon == coupon
    assert order.coupon_code == "FALL10"


def test_the_snapshot_survives_the_coupon_being_deleted(
    cart_80, coupon, checkout_data, now
):
    cart_80.coupon = coupon
    cart_80.save()
    order = place_order(cart_80, cart_80.user, checkout_data, now=now)

    coupon.delete()
    order.refresh_from_db()

    assert order.coupon is None
    assert order.coupon_code == "FALL10"
    assert order.discount == Decimal("8.00")


def test_a_coupon_that_expired_since_the_cart_was_viewed_is_swapped(
    cart_80, make_coupon, checkout_data, now
):
    make_coupon("SAVE5", "5", discount_type=Coupon.DiscountType.AMOUNT, is_public=True)
    ending = make_coupon("ENDING10", expires_at=now)
    cart_80.coupon = ending
    cart_80.save()

    # Viewed a second before expiry: still fine.
    refresh_cart_coupon(cart_80, now=now - datetime.timedelta(seconds=1))
    assert cart_80.coupon == ending
    # Placed at the moment of expiry: swapped, never honored.
    order = place_order(cart_80, cart_80.user, checkout_data, now=now)

    assert order.coupon_code == "SAVE5"
    assert order.total == Decimal("75.00")


def test_a_paused_coupon_records_no_discount(cart_80, make_coupon, checkout_data, now):
    cart_80.coupon = make_coupon("SAVE15", "15", minimum_order=Decimal("100.00"))
    cart_80.save()

    order = place_order(cart_80, cart_80.user, checkout_data, now=now)

    assert order.total == Decimal("80.00")
    assert order.coupon is None
    assert order.coupon_code == ""


def test_placing_an_order_clears_the_cart_coupon_and_notice(
    cart_80, coupon, checkout_data, now
):
    cart_80.coupon = coupon
    cart_80.coupon_notice = "THOUGHTS10 expired, so we applied FALL10 instead."
    cart_80.save()

    place_order(cart_80, cart_80.user, checkout_data, now=now)

    cart_80.refresh_from_db()
    assert cart_80.coupon is None
    assert cart_80.coupon_notice == ""


def test_the_coupon_code_seam_applies_the_code(cart_80, coupon, checkout_data, now):
    order = place_order(
        cart_80, cart_80.user, checkout_data, coupon_code="fall10", now=now
    )

    assert order.coupon == coupon
    assert order.total == Decimal("72.00")


def test_the_coupon_code_seam_rejects_an_unknown_code(cart_80, checkout_data, now):
    with pytest.raises(ValueError, match="No coupon"):
        place_order(cart_80, cart_80.user, checkout_data, coupon_code="NOPE", now=now)

    assert not Order.objects.exists()
    assert cart_80.items.exists()


def test_a_once_per_customer_coupon_is_swapped_on_second_use(
    cart_80, make_coupon, product, checkout_data, now
):
    welcome = make_coupon(
        "WELCOME5",
        "5",
        discount_type=Coupon.DiscountType.AMOUNT,
        once_per_customer=True,
    )
    cart_80.coupon = welcome
    cart_80.save()
    first = place_order(cart_80, cart_80.user, checkout_data, now=now)
    assert first.coupon == welcome

    cart_80.add(product)
    apply_coupon(cart_80, "WELCOME5", now=now)

    assert cart_80.coupon is None
    assert cart_80.coupon_notice == (
        "You've already used WELCOME5 (one per customer), "
        "and no replacement is available right now."
    )
