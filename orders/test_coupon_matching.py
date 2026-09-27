"""find_replacement tests — coverage priority 2 in the coupons PRD.

Every branch of the matching rule: the replacement chain and its loop
guard, closest public match in either direction, exclusions, tie-breaks,
and the nothing-found case. The cart below totals exactly $80.00.
"""

import datetime
from decimal import Decimal

import pytest

from products.models import Product

from .models import CartItem, Coupon, Order
from .services import find_replacement

AMOUNT = Coupon.DiscountType.AMOUNT


@pytest.fixture
def cart_80(cart, category):
    product = Product.objects.create(
        name="MindSync Charger",
        slug="mindsync-charger",
        price=Decimal("40.00"),
        category=category,
    )
    CartItem.objects.create(cart=cart, product=product, quantity=2)
    return cart


@pytest.fixture
def expired(make_coupon, now):
    """Build a coupon that expired a day before ``now``."""

    def make(code, value="10", **fields):
        fields.setdefault("starts_at", now - datetime.timedelta(days=60))
        fields.setdefault("expires_at", now - datetime.timedelta(days=1))
        return make_coupon(code, value, **fields)

    return make


@pytest.fixture
def thoughts10(expired):
    """The expired coupon being replaced: 10% off, so $8.00 on this cart."""
    return expired("THOUGHTS10")


def link(coupon, replacement):
    coupon.replaced_by = replacement
    coupon.save()


# The replacement chain


def test_follows_the_chain_to_the_first_active_coupon(
    cart_80, thoughts10, expired, make_coupon, now
):
    thoughts15 = expired("THOUGHTS15", "15")
    thoughts20 = make_coupon("THOUGHTS20", "20")
    link(thoughts10, thoughts15)
    link(thoughts15, thoughts20)

    assert find_replacement(thoughts10, cart_80, now=now) == thoughts20


def test_chain_skips_a_coupon_that_has_not_started(
    cart_80, thoughts10, make_coupon, now
):
    holiday = make_coupon("HOLIDAY20", starts_at=now + datetime.timedelta(days=30))
    fall = make_coupon("FALL15", "15")
    link(thoughts10, holiday)
    link(holiday, fall)

    assert find_replacement(thoughts10, cart_80, now=now) == fall


def test_chain_target_below_its_minimum_is_still_chosen(
    cart_80, thoughts10, make_coupon, now
):
    big_spender = make_coupon("BIG20", "20", minimum_order=Decimal("500.00"))
    link(thoughts10, big_spender)

    assert find_replacement(thoughts10, cart_80, now=now) == big_spender


def test_a_loop_in_the_chain_ends_the_walk(cart_80, thoughts10, expired, now):
    thoughts15 = expired("THOUGHTS15", "15")
    link(thoughts10, thoughts15)
    link(thoughts15, thoughts10)

    assert find_replacement(thoughts10, cart_80, now=now) is None


def test_a_dead_end_chain_falls_back_to_the_closest_public_coupon(
    cart_80, thoughts10, expired, make_coupon, now
):
    link(thoughts10, expired("THOUGHTS15", "15"))
    fall = make_coupon("FALL10", is_public=True)

    assert find_replacement(thoughts10, cart_80, now=now) == fall


# Closest public match


def test_picks_the_public_coupon_closest_in_savings(
    cart_80, thoughts10, make_coupon, now
):
    make_coupon("SAVE5", "5", discount_type=AMOUNT, is_public=True)
    make_coupon("SPRING15", "15", is_public=True)
    fall = make_coupon("FALL10", "10", is_public=True)

    assert find_replacement(thoughts10, cart_80, now=now) == fall


def test_closest_may_save_more_than_the_expired_coupon(
    cart_80, thoughts10, make_coupon, now
):
    make_coupon("SAVE6", "6", discount_type=AMOUNT, is_public=True)  # $2.00 away
    spring = make_coupon("SPRING12", "12", is_public=True)  # $9.60, $1.60 away

    assert find_replacement(thoughts10, cart_80, now=now) == spring


def test_compares_savings_on_this_cart_across_discount_types(
    cart_80, thoughts10, make_coupon, now
):
    save7 = make_coupon("SAVE7", "7.50", discount_type=AMOUNT, is_public=True)
    make_coupon("SPRING20", "20", is_public=True)  # $16.00 on this cart

    assert find_replacement(thoughts10, cart_80, now=now) == save7


def test_never_offers_a_non_public_coupon(cart_80, thoughts10, make_coupon, now):
    make_coupon("STAFFONLY", "10")  # an exact match, but not public
    save5 = make_coupon("SAVE5", "5", discount_type=AMOUNT, is_public=True)

    assert find_replacement(thoughts10, cart_80, now=now) == save5


def test_never_offers_an_inactive_public_coupon(
    cart_80, thoughts10, expired, make_coupon, now
):
    expired("OLD10", is_public=True)
    make_coupon("LATER10", is_public=True, starts_at=now + datetime.timedelta(days=1))

    assert find_replacement(thoughts10, cart_80, now=now) is None


def test_skips_public_coupons_whose_minimum_the_cart_misses(
    cart_80, thoughts10, make_coupon, now
):
    make_coupon(
        "SAVE8",
        "8",
        discount_type=AMOUNT,
        is_public=True,
        minimum_order=Decimal("100.00"),
    )
    save5 = make_coupon("SAVE5", "5", discount_type=AMOUNT, is_public=True)

    assert find_replacement(thoughts10, cart_80, now=now) == save5


# Tie-breaks


def test_equally_close_goes_to_the_bigger_saving(cart_80, thoughts10, make_coupon, now):
    make_coupon("SAVE7", "7", discount_type=AMOUNT, is_public=True)
    save9 = make_coupon("SAVE9", "9", discount_type=AMOUNT, is_public=True)

    assert find_replacement(thoughts10, cart_80, now=now) == save9


@pytest.mark.parametrize("newest", ["FALL10", "SAVE8"])
def test_identical_savings_go_to_the_newest_coupon(
    cart_80, thoughts10, make_coupon, now, newest
):
    older = now - datetime.timedelta(days=2)
    newer = now - datetime.timedelta(days=1)
    make_coupon(
        "FALL10", is_public=True, created_at=newer if newest == "FALL10" else older
    )
    make_coupon(
        "SAVE8",
        "8",
        discount_type=AMOUNT,
        is_public=True,
        created_at=newer if newest == "SAVE8" else older,
    )

    assert find_replacement(thoughts10, cart_80, now=now).code == newest


# Nothing found


def test_returns_none_when_nothing_qualifies(cart_80, thoughts10, now):
    assert find_replacement(thoughts10, cart_80, now=now) is None


# Per-customer limit — needs Order.coupon (coupons plan, Phase 3)


@pytest.mark.xfail(strict=True, reason="Order.coupon arrives in coupons Phase 3")
def test_chain_skips_a_coupon_the_customer_has_used_up(
    cart_80, thoughts10, make_coupon, now
):
    welcome = make_coupon("WELCOME5", "5", discount_type=AMOUNT, once_per_customer=True)
    fall = make_coupon("FALL10")
    link(thoughts10, welcome)
    link(welcome, fall)
    Order.objects.create(user=cart_80.user, total=Decimal("75.00"), coupon=welcome)

    assert find_replacement(thoughts10, cart_80, now=now) == fall


@pytest.mark.xfail(strict=True, reason="Order.coupon arrives in coupons Phase 3")
def test_skips_public_coupons_the_customer_has_used_up(
    cart_80, thoughts10, make_coupon, now
):
    welcome = make_coupon(
        "WELCOME8", "8", discount_type=AMOUNT, is_public=True, once_per_customer=True
    )
    save5 = make_coupon("SAVE5", "5", discount_type=AMOUNT, is_public=True)
    Order.objects.create(user=cart_80.user, total=Decimal("72.00"), coupon=welcome)

    assert find_replacement(thoughts10, cart_80, now=now) == save5
