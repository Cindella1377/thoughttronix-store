"""The reviews section on the product page: summary, form place, and list."""

import datetime
from urllib.parse import quote

import pytest
from django.urls import reverse

from orders.models import Order

from .models import Review

SIGN_IN = "to review a product you've received"
ON_ITS_WAY = "Your order's on its way. You can review it once it's delivered."
NOT_A_BUYER = "Reviews come from customers who've received this product."
MESSAGES = [SIGN_IN, ON_ITS_WAY, NOT_A_BUYER]


def page(client, product):
    return client.get(product.get_absolute_url()).content.decode()


def test_a_product_with_no_reviews_shows_the_empty_state(client, product):
    content = page(client, product)

    assert 'id="reviews"' in content
    assert "No reviews yet" in content


def test_a_delivered_buyer_sees_the_form(client, customer, product, delivered_order):
    client.force_login(customer)

    content = page(client, product)

    assert 'id="review-form"' in content
    assert "Out of this world" in content


def form_place(content):
    """What the form's place says: the form, one message, or nothing."""
    shown = [message for message in MESSAGES if message in content]
    if 'id="review-form"' in content:
        shown.append("form")
    return shown


def test_a_visitor_is_asked_to_sign_in(client, product):
    content = page(client, product)

    assert form_place(content) == [SIGN_IN]


def test_the_sign_in_link_returns_to_the_reviews(client, product):
    content = page(client, product)

    next_url = quote(product.get_absolute_url() + "#reviews", safe="")
    assert f'href="{reverse("accounts:login")}?next={next_url}"' in content


def test_signing_in_lands_on_the_reviews(client, customer, product):
    response = client.post(
        reverse("accounts:login"),
        {
            "username": "customer",
            "password": "customer123",
            "next": product.get_absolute_url() + "#reviews",
        },
    )

    assert response["Location"] == product.get_absolute_url() + "#reviews"


@pytest.mark.parametrize("order_status", [Order.Status.PLACED, Order.Status.SHIPPED])
def test_an_order_on_its_way_says_so(
    client, make_order, customer, product, order_status
):
    make_order(customer, product, order_status)
    client.force_login(customer)

    assert form_place(page(client, product)) == [ON_ITS_WAY]


def test_a_customer_who_never_received_it_is_told_who_reviews(
    client, make_order, customer, product
):
    make_order(customer, product, Order.Status.CANCELLED)
    client.force_login(customer)

    assert form_place(page(client, product)) == [NOT_A_BUYER]


def test_a_reviewer_sees_nothing_more(client, customer, product, delivered_order):
    Review.objects.create(product=product, author=customer, rating=4)
    client.force_login(customer)

    assert form_place(page(client, product)) == []


def test_staff_without_a_delivered_order_see_nothing(client, staff_user, product):
    client.force_login(staff_user)

    assert form_place(page(client, product)) == []


def test_staff_with_their_own_delivered_order_see_the_form(
    client, make_order, staff_user, product
):
    make_order(staff_user, product)
    client.force_login(staff_user)

    assert form_place(page(client, product)) == ["form"]


def test_an_unavailable_product_follows_the_same_rules(
    client, make_order, customer, unavailable_product
):
    make_order(customer, unavailable_product)
    client.force_login(customer)

    assert form_place(page(client, unavailable_product)) == ["form"]


def test_reviews_are_listed_newest_first(client, customer, staff_user, product):
    Review.objects.create(
        product=product,
        author=customer,
        rating=2,
        body="The older one.",
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )
    Review.objects.create(product=product, author=staff_user, rating=5, body="Newer.")

    content = page(client, product)

    assert content.index("Newer.") < content.index("The older one.")
    assert "No reviews yet" not in content
    assert "3.5 galaxies (2)" in content


def test_a_card_shows_the_first_name_and_never_the_email(client, customer, product):
    customer.first_name = "Casey"
    customer.save()
    Review.objects.create(product=product, author=customer, rating=4)

    content = page(client, product)

    assert "Casey" in content
    assert customer.email not in content


def test_a_card_falls_back_to_the_username(client, customer, product):
    Review.objects.create(product=product, author=customer, rating=4)

    content = page(client, product)

    assert ">customer<" in content
    assert customer.email not in content


def test_galaxies_are_labelled_for_screen_readers(client, customer, product):
    Review.objects.create(product=product, author=customer, rating=4)

    content = page(client, product)

    assert 'aria-label="4 out of 5 galaxies, Stellar"' in content
    assert 'aria-label="4.0 out of 5 galaxies"' in content
