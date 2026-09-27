"""The back-office Coupons tab — coverage priorities 5 and 6 in the coupons PRD.

``CouponForm``'s rules, access control, and CRUD round-trips.
"""

import datetime
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.urls import reverse
from django.utils import timezone

from .forms import CouponForm
from .models import Coupon

pytestmark = pytest.mark.django_db


def coupon_data(**overrides):
    data = {
        "code": "WINTER25",
        "discount_type": Coupon.DiscountType.PERCENT,
        "value": "25",
        "starts_at": "2026-12-01T00:00",
        "expires_at": "2027-01-01T00:00",
        "minimum_order": "",
        "replaced_by": "",
    }
    data.update(overrides)
    return data


def manage_urls(coupon):
    """Every staff-only coupon URL, for the access-control sweeps."""
    return [
        reverse("orders:manage_coupons"),
        reverse("orders:manage_coupon_create"),
        reverse("orders:manage_coupon_update", kwargs={"pk": coupon.pk}),
        reverse("orders:manage_coupon_delete", kwargs={"pk": coupon.pk}),
    ]


# --- CouponForm ---------------------------------------------------------------


def test_a_valid_coupon_saves_with_its_code_uppercased():
    form = CouponForm(coupon_data(code="winter25", is_public="on"))

    assert form.is_valid(), form.errors
    coupon = form.save()
    assert coupon.code == "WINTER25"
    assert coupon.is_public
    assert not coupon.once_per_customer


def test_codes_are_unique_regardless_of_case(coupon):
    form = CouponForm(coupon_data(code="fall10"))

    assert not form.is_valid()
    assert "code" in form.errors


def test_codes_are_letters_numbers_and_hyphens(db):
    form = CouponForm(coupon_data(code="SAVE 10%"))

    assert form.errors["code"] == ["Use letters, numbers, and hyphens only."]


@pytest.mark.parametrize("value", ["0", "-5"])
def test_the_value_must_be_positive(value):
    assert "value" in CouponForm(coupon_data(value=value)).errors


@pytest.mark.parametrize("value", ["0.5", "101"])
def test_a_percentage_must_be_between_1_and_100(value):
    form = CouponForm(coupon_data(value=value))

    assert form.errors["value"] == ["A percentage must be between 1 and 100."]


def test_an_amount_may_exceed_100():
    form = CouponForm(
        coupon_data(discount_type=Coupon.DiscountType.AMOUNT, value="150")
    )
    assert form.is_valid(), form.errors


def test_the_minimum_order_must_be_positive_when_given():
    assert "minimum_order" in CouponForm(coupon_data(minimum_order="0")).errors


@pytest.mark.parametrize("expires_at", ["2026-12-01T00:00", "2026-11-30T00:00"])
def test_the_end_must_come_after_the_start(expires_at):
    form = CouponForm(coupon_data(expires_at=expires_at))

    assert form.errors["expires_at"] == ["The end must come after the start."]


def test_a_coupon_cannot_replace_itself(coupon):
    form = CouponForm(
        coupon_data(code="FALL10", replaced_by=str(coupon.pk)), instance=coupon
    )

    assert form.errors["replaced_by"] == ["A coupon can't replace itself."]


def test_a_replacement_loop_is_rejected(make_coupon):
    a = make_coupon("AAA")
    b = make_coupon("BBB", replaced_by=a)
    c = make_coupon("CCC", replaced_by=b)

    # A → C would close the loop A → C → B → A.
    form = CouponForm(coupon_data(code="AAA", replaced_by=str(c.pk)), instance=a)

    assert form.errors["replaced_by"] == ["That makes a loop: CCC leads back to AAA."]


def test_a_chain_without_a_loop_is_fine(make_coupon):
    a = make_coupon("AAA")
    b = make_coupon("BBB")
    make_coupon("CCC", replaced_by=b)

    form = CouponForm(coupon_data(code="AAA", replaced_by=str(b.pk)), instance=a)

    assert form.is_valid(), form.errors


# --- Access control -----------------------------------------------------------


def test_anonymous_users_are_sent_to_login(client, coupon):
    for url in manage_urls(coupon):
        response = client.get(url)

        assert response.status_code == HTTPStatus.FOUND, url
        assert reverse("accounts:login") in response.url


def test_customers_get_403(client, customer, coupon):
    client.force_login(customer)

    for url in manage_urls(coupon):
        assert client.get(url).status_code == HTTPStatus.FORBIDDEN, url


def test_staff_get_200(client, staff_user, coupon):
    client.force_login(staff_user)

    for url in manage_urls(coupon):
        response = client.get(url)

        assert response.status_code == HTTPStatus.OK, url
        assert "{#" not in response.content.decode(), url


# --- The list and CRUD round-trips --------------------------------------------


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


def test_the_coupons_tab_is_active(staff_client, db):
    response = staff_client.get(reverse("orders:manage_coupons"))

    assert response.context["section"] == "coupons"
    assert b">Coupons</a>" in response.content


def test_the_list_has_a_designed_empty_state(staff_client, db):
    response = staff_client.get(reverse("orders:manage_coupons"))

    assert b"No coupons yet" in response.content


def test_the_list_shows_each_coupons_status(staff_client, make_coupon):
    now = timezone.now()
    day = datetime.timedelta(days=1)
    make_coupon("RUNNING", starts_at=now - day, expires_at=now + day)
    make_coupon("SOON", starts_at=now + day, expires_at=now + 2 * day)
    make_coupon("OVER", starts_at=now - 2 * day, expires_at=now - day)

    content = staff_client.get(reverse("orders:manage_coupons")).content.decode()

    for code, status in [
        ("RUNNING", "Active"),
        ("SOON", "Scheduled"),
        ("OVER", "Expired"),
    ]:
        row = content[content.index(code) :]
        assert status in row[: row.index("</tr>")], code


def test_create_round_trip(staff_client):
    response = staff_client.post(
        reverse("orders:manage_coupon_create"), coupon_data(), follow=True
    )

    coupon = Coupon.objects.get()
    assert coupon.code == "WINTER25"
    assert coupon.value == Decimal("25.00")
    assert b"WINTER25 created." in response.content


def test_update_round_trip(staff_client, coupon):
    staff_client.post(
        reverse("orders:manage_coupon_update", kwargs={"pk": coupon.pk}),
        coupon_data(code="FALL10", value="15", once_per_customer="on"),
    )

    coupon.refresh_from_db()
    assert coupon.value == Decimal("15.00")
    assert coupon.once_per_customer


def test_delete_removes_the_coupon_from_carts(staff_client, coupon, cart_80):
    cart_80.coupon = coupon
    cart_80.save()

    staff_client.post(reverse("orders:manage_coupon_delete", kwargs={"pk": coupon.pk}))

    assert not Coupon.objects.exists()
    cart_80.refresh_from_db()
    assert cart_80.coupon is None
