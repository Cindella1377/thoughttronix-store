"""Coupons on the cart — coverage priority 3 in the coupons PRD.

The cart's coupon pricing (discount, paused coupons, shortfall), and the
two service functions that keep a cart's coupon valid: ``apply_coupon``
and ``refresh_cart_coupon``, including the notices they leave. The cart
totals exactly $80.00.
"""

import datetime
from decimal import Decimal

import pytest

from .models import Coupon
from .services import ChangeReason, apply_coupon, refresh_cart_coupon

AMOUNT = Coupon.DiscountType.AMOUNT


def put_on(cart, coupon):
    cart.coupon = coupon
    cart.save()


# Pricing on the cart


def test_no_coupon_means_no_discount(cart_80):
    assert cart_80.discount() == Decimal("0.00")
    assert cart_80.grand_total() == Decimal("80.00")


def test_discount_and_grand_total(cart_80, coupon):
    put_on(cart_80, coupon)
    assert cart_80.discount() == Decimal("8.00")
    assert cart_80.grand_total() == Decimal("72.00")


def test_a_coupon_below_its_minimum_is_paused(cart_80, make_coupon):
    put_on(
        cart_80,
        make_coupon(
            "SAVE15", "15", discount_type=AMOUNT, minimum_order=Decimal("100.00")
        ),
    )
    assert cart_80.discount() == Decimal("0.00")
    assert cart_80.grand_total() == Decimal("80.00")
    assert cart_80.coupon_shortfall() == Decimal("20.00")


def test_a_paused_coupon_resumes_at_its_minimum(cart_80, make_coupon):
    put_on(
        cart_80,
        make_coupon(
            "SAVE15", "15", discount_type=AMOUNT, minimum_order=Decimal("80.00")
        ),
    )
    assert cart_80.coupon_shortfall() == Decimal("0.00")
    assert cart_80.discount() == Decimal("15.00")


def test_a_fixed_discount_never_makes_the_total_negative(cart_80, make_coupon):
    put_on(cart_80, make_coupon("SAVE100", "100", discount_type=AMOUNT))
    assert cart_80.grand_total() == Decimal("0.00")


def test_remove_coupon_clears_coupon_notice_and_replaced(cart_80, coupon, expired):
    cart_80.coupon_notice = "Something changed."
    cart_80.replaced_coupon = expired("THOUGHTS10")
    cart_80.replaced_coupon_status = "Expired"
    put_on(cart_80, coupon)
    cart_80.remove_coupon()
    cart_80.refresh_from_db()
    assert cart_80.coupon is None
    assert cart_80.coupon_notice == ""
    assert cart_80.replaced_coupon is None
    assert cart_80.replaced_coupon_status == ""


def test_dismiss_notice_keeps_the_coupon(cart_80, coupon):
    cart_80.coupon_notice = "Something changed."
    put_on(cart_80, coupon)
    cart_80.dismiss_coupon_notice()
    cart_80.refresh_from_db()
    assert cart_80.coupon == coupon
    assert cart_80.coupon_notice == ""


def test_summary_describes_the_discount(make_coupon):
    assert make_coupon("TEN", "10").summary == "10% off"
    assert make_coupon("HALF", "12.5").summary == "12.5% off"
    assert make_coupon("FIVE", "5", discount_type=AMOUNT).summary == "$5.00 off"


# refresh_cart_coupon


def test_refresh_leaves_an_active_coupon_alone(cart_80, coupon, now):
    put_on(cart_80, coupon)
    assert refresh_cart_coupon(cart_80, now=now) is None
    assert cart_80.coupon == coupon
    assert cart_80.coupon_notice == ""


def test_refresh_with_no_coupon_does_nothing(cart_80, now):
    assert refresh_cart_coupon(cart_80, now=now) is None


def test_refresh_leaves_a_paused_coupon_alone(cart_80, make_coupon, now):
    paused = make_coupon("SAVE15", "15", minimum_order=Decimal("100.00"))
    put_on(cart_80, paused)
    assert refresh_cart_coupon(cart_80, now=now) is None
    assert cart_80.coupon == paused


def test_refresh_swaps_an_expired_coupon_and_explains(
    cart_80, expired, make_coupon, now
):
    thoughts10 = expired(
        "THOUGHTS10", expires_at=datetime.datetime(2026, 9, 30, 12, tzinfo=datetime.UTC)
    )
    save7 = make_coupon("SAVE7", "7.50", discount_type=AMOUNT, is_public=True)
    put_on(cart_80, thoughts10)

    change = refresh_cart_coupon(cart_80, now=now)

    assert change.old == thoughts10
    assert change.new == save7
    assert change.reason is ChangeReason.EXPIRED
    cart_80.refresh_from_db()
    assert cart_80.coupon == save7
    assert cart_80.coupon_notice == (
        "THOUGHTS10 expired on Sep 30, so we applied SAVE7 instead, "
        "which saves you $7.50 on this cart."
    )
    assert cart_80.replaced_coupon == thoughts10
    assert cart_80.replaced_coupon_status == "Expired"


def test_refresh_follows_the_staff_chain(cart_80, expired, make_coupon, now):
    thoughts20 = make_coupon("THOUGHTS20", "20")
    thoughts10 = expired("THOUGHTS10", replaced_by=thoughts20)
    put_on(cart_80, thoughts10)

    assert refresh_cart_coupon(cart_80, now=now).new == thoughts20


def test_a_paused_replacement_notice_omits_savings(cart_80, expired, make_coupon, now):
    big = make_coupon("BIG20", "20", minimum_order=Decimal("500.00"))
    put_on(cart_80, expired("THOUGHTS10", replaced_by=big))

    refresh_cart_coupon(cart_80, now=now)

    assert cart_80.coupon_notice.endswith("so we applied BIG20 instead.")


def test_refresh_removes_when_nothing_qualifies(cart_80, expired, now):
    thoughts10 = expired("THOUGHTS10")
    put_on(cart_80, thoughts10)

    change = refresh_cart_coupon(cart_80, now=now)

    assert change.new is None
    cart_80.refresh_from_db()
    assert cart_80.coupon is None
    assert cart_80.coupon_notice.endswith("and no replacement is available right now.")
    # Still shown faded, so the customer sees what happened to their code.
    assert cart_80.replaced_coupon == thoughts10
    assert cart_80.replaced_coupon_status == "Expired"


def test_refresh_expires_exactly_at_expires_at(cart_80, make_coupon, now):
    put_on(cart_80, make_coupon("ENDING", expires_at=now))
    assert refresh_cart_coupon(cart_80, now=now - datetime.timedelta(seconds=1)) is None
    assert refresh_cart_coupon(cart_80, now=now).reason is ChangeReason.EXPIRED


def test_refresh_swaps_a_coupon_that_is_not_running(cart_80, make_coupon, now):
    # Only reachable if staff reschedule a coupon already on carts.
    put_on(cart_80, make_coupon("LATER", starts_at=now + datetime.timedelta(days=1)))

    change = refresh_cart_coupon(cart_80, now=now)

    assert change.reason is ChangeReason.NOT_STARTED
    assert cart_80.coupon_notice == (
        "LATER isn't running right now, and no replacement is available right now."
    )
    assert cart_80.replaced_coupon_status == "Not running"


# apply_coupon


def test_apply_puts_the_coupon_on_the_cart(cart_80, coupon, now):
    change = apply_coupon(cart_80, "FALL10", now=now)

    assert change.new == coupon
    assert change.reason is ChangeReason.APPLIED
    cart_80.refresh_from_db()
    assert cart_80.coupon == coupon


def test_apply_matches_case_insensitively(cart_80, coupon, now):
    assert apply_coupon(cart_80, "  fall10 ", now=now).new == coupon


def test_apply_replaces_the_current_coupon_and_clears_the_swap(
    cart_80, coupon, expired, make_coupon, now
):
    save5 = make_coupon("SAVE5", "5", discount_type=AMOUNT)
    put_on(cart_80, coupon)
    cart_80.coupon_notice = "An old notice."
    cart_80.replaced_coupon = expired("THOUGHTS10")
    cart_80.replaced_coupon_status = "Expired"
    cart_80.save()

    change = apply_coupon(cart_80, "SAVE5", now=now)

    assert change.old == coupon
    assert change.new == save5
    cart_80.refresh_from_db()
    assert cart_80.coupon == save5
    assert cart_80.coupon_notice == ""
    assert cart_80.replaced_coupon is None
    assert cart_80.replaced_coupon_status == ""


def test_apply_swaps_a_code_that_has_already_expired(cart_80, expired, coupon, now):
    thoughts10 = expired("THOUGHTS10")

    change = apply_coupon(cart_80, "thoughts10", now=now)

    assert change.old == thoughts10
    assert change.new == coupon
    assert change.reason is ChangeReason.EXPIRED
    assert cart_80.coupon_notice.startswith("THOUGHTS10 expired on")
    assert cart_80.replaced_coupon == thoughts10


def test_apply_rejects_an_unknown_code(cart_80, now):
    with pytest.raises(ValueError, match="No coupon"):
        apply_coupon(cart_80, "NOPE", now=now)


def test_apply_rejects_a_code_that_has_not_started(cart_80, make_coupon, now):
    make_coupon("HOLIDAY20", starts_at=now + datetime.timedelta(days=30))
    with pytest.raises(ValueError, match="not started"):
        apply_coupon(cart_80, "HOLIDAY20", now=now)
