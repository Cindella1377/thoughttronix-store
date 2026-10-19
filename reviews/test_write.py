"""Posting a review with HTMX — phase 1 of the reviews plan."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from orders.models import Order

from .models import Review


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


def post_review(client, product, **data):
    return client.post(reverse("reviews:create", args=[product.pk]), data)


def is_partial(response):
    return b"<html" not in response.content


def test_a_delivered_buyer_posts_a_review(
    signed_in, customer, product, delivered_order
):
    response = post_review(signed_in, product, rating=4, body="Hears me think.")

    assert response.status_code == HTTPStatus.OK
    assert is_partial(response)
    review = Review.objects.get()
    assert (review.product, review.author, review.rating) == (product, customer, 4)
    assert review.body == "Hears me think."
    assert f'id="review-{review.pk}"'.encode() in response.content
    assert b"Stellar" in response.content
    assert b"Hears me think." in response.content


def test_text_is_optional(signed_in, product, delivered_order):
    response = post_review(signed_in, product, rating=1)

    assert response.status_code == HTTPStatus.OK
    assert Review.objects.get().body == ""


def test_the_response_refreshes_the_summary_out_of_band(
    signed_in, staff_user, product, delivered_order
):
    Review.objects.create(product=product, author=staff_user, rating=5)

    response = post_review(signed_in, product, rating=4)

    content = response.content.decode()
    assert 'id="review-summary"' in content
    assert 'hx-swap-oob="true"' in content
    assert "4.5 galaxies (2)" in content


def test_the_form_does_not_come_back_after_posting(signed_in, product, delivered_order):
    post_review(signed_in, product, rating=4)

    page = signed_in.get(product.get_absolute_url())

    assert b'id="review-form"' not in page.content


@pytest.mark.parametrize("status", [Order.Status.SHIPPED, Order.Status.CANCELLED])
def test_a_customer_without_a_delivered_order_cannot_post(
    signed_in, make_order, customer, product, status
):
    make_order(customer, product, status)

    response = post_review(signed_in, product, rating=5)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not Review.objects.exists()


def test_a_customer_who_never_ordered_cannot_post(signed_in, product):
    response = post_review(signed_in, product, rating=5)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not Review.objects.exists()


def test_a_visitor_cannot_post(client, product):
    response = post_review(client, product, rating=5)

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response["Location"]
    assert not Review.objects.exists()


def test_a_second_review_is_refused_by_the_form(
    signed_in, customer, product, delivered_order
):
    Review.objects.create(product=product, author=customer, rating=4)

    response = post_review(signed_in, product, rating=1, body="Changed my mind.")

    assert response.status_code == HTTPStatus.OK
    assert b"already reviewed" in response.content
    assert Review.objects.get().rating == 4


def test_a_missing_rating_returns_the_form_with_what_was_typed(
    signed_in, product, delivered_order
):
    response = post_review(signed_in, product, body="Forgot the galaxies.")

    assert response.status_code == HTTPStatus.OK
    assert is_partial(response)
    assert b'id="review-form"' in response.content
    assert b"Choose from one to five galaxies." in response.content
    assert b"Forgot the galaxies." in response.content
    assert not Review.objects.exists()


def test_text_over_2000_characters_returns_the_form_with_the_rating_kept(
    signed_in, product, delivered_order
):
    response = post_review(signed_in, product, rating=3, body="x" * 2001)

    content = response.content.decode()
    assert "at most 2000 characters" in content
    assert 'value="3" checked' in content
    assert "x" * 2001 in content
    assert not Review.objects.exists()


def test_text_of_exactly_2000_characters_is_fine(signed_in, product, delivered_order):
    post_review(signed_in, product, rating=3, body="x" * 2000)

    assert Review.objects.exists()
