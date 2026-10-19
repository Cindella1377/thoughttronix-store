"""Returns remove reviews — phase 3 of the reviews plan.

A review stands only while its author has a Delivered order containing
the product. Moving an order off Delivered in the back office removes
the reviews it no longer supports, and moving it back restores nothing.
"""

import pytest
from django.urls import reverse

from orders.models import Order

from .models import Eligibility, Review


def set_status(order, status):
    order.status = status
    order.save()


@pytest.fixture
def review(customer, product, delivered_order):
    return Review.objects.create(product=product, author=customer, rating=4)


@pytest.mark.parametrize("status", [Order.Status.CANCELLED, Order.Status.SHIPPED])
def test_moving_the_only_delivered_order_away_removes_the_review(
    delivered_order, review, status
):
    set_status(delivered_order, status)

    assert Review.objects.remove_unqualified(delivered_order) == 1
    assert not Review.objects.exists()


def test_a_still_delivered_order_removes_nothing(delivered_order, review):
    assert Review.objects.remove_unqualified(delivered_order) == 0
    assert Review.objects.filter(pk=review.pk).exists()


def test_a_second_delivered_order_keeps_the_review(
    make_order, customer, product, delivered_order, review
):
    make_order(customer, product)
    set_status(delivered_order, Order.Status.CANCELLED)

    assert Review.objects.remove_unqualified(delivered_order) == 0
    assert Review.objects.filter(pk=review.pk).exists()


def test_reviews_of_products_not_on_the_order_are_untouched(
    make_order, customer, featured_product, delivered_order, review
):
    other_order = make_order(customer, featured_product)
    other = Review.objects.create(product=featured_product, author=customer, rating=2)
    set_status(other_order, Order.Status.CANCELLED)

    Review.objects.remove_unqualified(other_order)

    assert set(Review.objects.all()) == {review}
    assert not Review.objects.filter(pk=other.pk).exists()


def test_other_customers_reviews_are_untouched(
    make_order, staff_user, product, delivered_order, review
):
    make_order(staff_user, product)
    theirs = Review.objects.create(product=product, author=staff_user, rating=5)
    set_status(delivered_order, Order.Status.CANCELLED)

    Review.objects.remove_unqualified(delivered_order)

    assert list(Review.objects.all()) == [theirs]


def test_a_line_whose_product_was_deleted_counts_for_nothing(
    make_order, customer, featured_product, delivered_order, review
):
    gone = make_order(customer, featured_product)
    featured_product.delete()
    set_status(gone, Order.Status.CANCELLED)

    assert Review.objects.remove_unqualified(gone) == 0
    assert Review.objects.filter(pk=review.pk).exists()


def change_status(client, order, status):
    return client.post(
        reverse("orders:manage_order_status", kwargs={"pk": order.pk}),
        {"status": status},
    )


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.mark.parametrize("status", ["CANCELLED", "SHIPPED"])
def test_the_back_office_status_change_removes_the_review(
    staff_client, delivered_order, review, status
):
    change_status(staff_client, delivered_order, status)

    assert not Review.objects.exists()


def test_moving_back_to_delivered_shows_the_form_but_restores_nothing(
    staff_client, customer, product, delivered_order, review
):
    change_status(staff_client, delivered_order, "CANCELLED")
    change_status(staff_client, delivered_order, "DELIVERED")

    assert not Review.objects.exists()
    assert Review.objects.eligibility(customer, product) == Eligibility.CAN_REVIEW
