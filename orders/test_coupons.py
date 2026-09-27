"""Coupon model tests — coverage priority 1 in the coupons PRD.

Savings for both discount types, the cap at the cart total, the exact
start and expiry boundaries, minimums, and status.
"""

import datetime
from decimal import Decimal

from .models import Coupon

ONE_SECOND = datetime.timedelta(seconds=1)


def test_code_is_stored_uppercase(make_coupon):
    assert make_coupon("  fall10 ").code == "FALL10"


def test_str_is_the_code(coupon):
    assert str(coupon) == "FALL10"


def test_percent_savings(make_coupon):
    coupon = make_coupon("TEN", value="10")
    assert coupon.savings_for(Decimal("80.00")) == Decimal("8.00")


def test_percent_savings_round_to_the_cent(make_coupon):
    coupon = make_coupon("FIFTEEN", value="15")
    assert coupon.savings_for(Decimal("10.99")) == Decimal("1.65")


def test_amount_savings(make_coupon):
    coupon = make_coupon("SAVE5", value="5", discount_type=Coupon.DiscountType.AMOUNT)
    assert coupon.savings_for(Decimal("80.00")) == Decimal("5")


def test_amount_savings_are_capped_at_the_total(make_coupon):
    coupon = make_coupon("SAVE10", value="10", discount_type=Coupon.DiscountType.AMOUNT)
    assert coupon.savings_for(Decimal("6.00")) == Decimal("6.00")


def test_savings_on_an_empty_cart_are_zero(coupon):
    assert coupon.savings_for(Decimal("0.00")) == Decimal("0.00")


def test_active_from_exactly_starts_at(make_coupon, now):
    coupon = make_coupon("START", starts_at=now)
    assert coupon.is_active(now)
    assert coupon in Coupon.objects.active(now)
    assert not coupon.is_active(now - ONE_SECOND)
    assert coupon not in Coupon.objects.active(now - ONE_SECOND)


def test_expired_at_exactly_expires_at(make_coupon, now):
    coupon = make_coupon("END", expires_at=now)
    assert coupon.is_expired(now)
    assert not coupon.is_active(now)
    assert coupon not in Coupon.objects.active(now)
    assert coupon.is_active(now - ONE_SECOND)
    assert coupon in Coupon.objects.active(now - ONE_SECOND)


def test_public_filters_to_public_coupons(make_coupon):
    public = make_coupon("PUBLIC", is_public=True)
    make_coupon("PRIVATE")
    assert list(Coupon.objects.public()) == [public]


def test_no_minimum_is_always_met(coupon):
    assert coupon.meets_minimum(Decimal("0.00"))


def test_minimum_is_met_at_exactly_the_minimum(make_coupon):
    coupon = make_coupon("MIN50", minimum_order=Decimal("50.00"))
    assert coupon.meets_minimum(Decimal("50.00"))
    assert not coupon.meets_minimum(Decimal("49.99"))


def test_status_follows_the_dates(coupon, now):
    assert coupon.status(coupon.starts_at - ONE_SECOND) == Coupon.Status.SCHEDULED
    assert coupon.status(now) == Coupon.Status.ACTIVE
    assert coupon.status(coupon.expires_at) == Coupon.Status.EXPIRED
