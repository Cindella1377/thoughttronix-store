"""Coupon views and form — coverage priority 7 in the coupons PRD.

Views read the real clock, so coupons here are dated relative to
``timezone.now()`` rather than the fixed ``COUPON_NOW``.
"""

import datetime
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.urls import reverse
from django.utils import timezone

from .forms import CouponApplyForm
from .models import Coupon

AMOUNT = Coupon.DiscountType.AMOUNT
DAY = datetime.timedelta(days=1)


@pytest.fixture
def live(make_coupon):
    """Build a coupon running right now, by the real clock."""

    def make(code, value="10", **fields):
        fields.setdefault("starts_at", timezone.now() - 30 * DAY)
        fields.setdefault("expires_at", timezone.now() + 30 * DAY)
        return make_coupon(code, value, **fields)

    return make


@pytest.fixture
def lapsed(live):
    """Build a coupon that expired yesterday, by the real clock."""

    def make(code, value="10", **fields):
        fields.setdefault("starts_at", timezone.now() - 60 * DAY)
        fields.setdefault("expires_at", timezone.now() - DAY)
        return live(code, value, **fields)

    return make


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


def is_partial(response):
    return b"<html" not in response.content


# CouponApplyForm


def test_form_accepts_a_known_code_and_normalizes_it(live):
    live("FALL10")
    form = CouponApplyForm({"code": " fall10 "})
    assert form.is_valid()
    assert form.cleaned_data["code"] == "FALL10"


def test_form_accepts_an_expired_code_so_it_can_be_swapped(lapsed):
    lapsed("THOUGHTS10")
    assert CouponApplyForm({"code": "THOUGHTS10"}).is_valid()


def test_form_rejects_an_unknown_code(db):
    form = CouponApplyForm({"code": "NOPE"})
    assert not form.is_valid()
    assert form.errors["code"] == ["We don't recognize that code."]


def test_form_rejects_a_code_that_has_not_started(live):
    live("HOLIDAY20", starts_at=timezone.now() + DAY)
    form = CouponApplyForm({"code": "HOLIDAY20"})
    assert not form.is_valid()
    assert "isn't active yet" in form.errors["code"][0]


def test_form_requires_a_code(db):
    assert not CouponApplyForm({"code": ""}).is_valid()


# The cart page and its HTMX endpoints


def test_cart_page_shows_the_coupon_form(signed_in, cart_80):
    response = signed_in.get(reverse("orders:cart"))
    assert b'name="code"' in response.content


def test_apply_returns_the_partial_with_the_discount(signed_in, cart_80, live):
    live("FALL10")
    response = signed_in.post(reverse("orders:apply_coupon"), {"code": "fall10"})

    assert response.status_code == HTTPStatus.OK
    assert is_partial(response)
    assert b"FALL10" in response.content
    assert b"$72.00" in response.content
    cart_80.refresh_from_db()
    assert cart_80.coupon.code == "FALL10"


def test_apply_an_unknown_code_shows_the_error(signed_in, cart_80):
    response = signed_in.post(reverse("orders:apply_coupon"), {"code": "NOPE"})

    assert is_partial(response)
    assert b"recognize that code" in response.content
    cart_80.refresh_from_db()
    assert cart_80.coupon is None


def test_apply_an_expired_code_swaps_it_with_a_notice(signed_in, cart_80, lapsed, live):
    lapsed("THOUGHTS10")
    live("FALL10", is_public=True)

    response = signed_in.post(reverse("orders:apply_coupon"), {"code": "THOUGHTS10"})

    assert b"so we applied FALL10 instead" in response.content
    cart_80.refresh_from_db()
    assert cart_80.coupon.code == "FALL10"


def test_cart_page_swaps_a_coupon_that_expired_in_the_cart(
    signed_in, cart_80, lapsed, live
):
    cart_80.coupon = lapsed("THOUGHTS10")
    cart_80.save()
    live("FALL10", is_public=True)

    response = signed_in.get(reverse("orders:cart"))

    assert b"THOUGHTS10 expired on" in response.content
    assert b"Got it" in response.content


def test_remove_coupon(signed_in, cart_80, live):
    cart_80.coupon = live("FALL10")
    cart_80.save()

    response = signed_in.post(reverse("orders:remove_coupon"))

    assert is_partial(response)
    cart_80.refresh_from_db()
    assert cart_80.coupon is None


def test_dismiss_notice(signed_in, cart_80):
    cart_80.coupon_notice = "THOUGHTS10 expired, so we applied FALL10 instead."
    cart_80.save()

    response = signed_in.post(reverse("orders:dismiss_coupon_notice"))

    assert is_partial(response)
    assert b"THOUGHTS10 expired" not in response.content
    cart_80.refresh_from_db()
    assert cart_80.coupon_notice == ""


def test_paused_coupon_shows_the_shortfall(signed_in, cart_80, live):
    cart_80.coupon = live(
        "SAVE15", "15", discount_type=AMOUNT, minimum_order=Decimal("100.00")
    )
    cart_80.save()

    response = signed_in.get(reverse("orders:cart"))

    assert b"Add $20.00 more to use SAVE15." in response.content
    assert b'Total: <span class="text-primary">$80.00' in response.content


def test_line_changes_reprice_the_coupon(signed_in, cart_80, live):
    cart_80.coupon = live(
        "SAVE15", "15", discount_type=AMOUNT, minimum_order=Decimal("100.00")
    )
    cart_80.save()
    item = cart_80.items.get()

    response = signed_in.post(reverse("orders:increment", kwargs={"pk": item.pk}))

    # $120.00 now meets the $100 minimum: the coupon resumes.
    assert b"$105.00" in response.content
    assert b"more to use" not in response.content


@pytest.mark.parametrize(
    "name",
    ["orders:apply_coupon", "orders:remove_coupon", "orders:dismiss_coupon_notice"],
)
def test_coupon_endpoints_require_login(client, db, name):
    response = client.post(reverse(name))
    assert response.status_code == HTTPStatus.FOUND
    assert "/login/" in response.url


def test_checkout_shows_the_discount(signed_in, cart_80, live):
    cart_80.coupon = live("FALL10")
    cart_80.save()

    response = signed_in.get(reverse("orders:checkout"))

    assert b"Discount (FALL10)" in response.content
    assert b"$72.00" in response.content
