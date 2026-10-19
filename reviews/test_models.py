"""Review model rules — eligibility, the constraint, and the summary."""

import datetime

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError

from orders.models import Order

from .models import Review


def test_galaxy_levels_are_named():
    assert [label for _, label in Review.Rating.choices] == [
        "Black hole",
        "Space junk",
        "Low orbit",
        "Stellar",
        "Out of this world",
    ]


def test_only_black_hole_carries_a_tagline():
    assert Review.Rating.BLACK_HOLE.tagline == "it took something from me"
    assert Review.Rating.STELLAR.tagline == ""


def test_database_refuses_a_second_review_of_one_product(customer, product):
    Review.objects.create(product=product, author=customer, rating=4)

    with pytest.raises(IntegrityError):
        Review.objects.create(product=product, author=customer, rating=2)


def test_a_new_review_is_not_marked_edited(customer, product):
    review = Review.objects.create(product=product, author=customer, rating=4)

    assert review.updated_at is None
    assert not review.edited_by_staff


def test_reviews_are_newest_first(customer, staff_user, product):
    older = Review.objects.create(
        product=product,
        author=customer,
        rating=2,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )
    newer = Review.objects.create(product=product, author=staff_user, rating=5)

    assert list(Review.objects.all()) == [newer, older]


def status(user, product):
    return Review.objects.eligibility(user, product)


def test_a_visitor_is_signed_out(product):
    assert status(AnonymousUser(), product) == "signed_out"


def test_a_delivered_buyer_can_review(customer, product, delivered_order):
    assert status(customer, product) == "can_review"


def test_a_buyer_who_has_reviewed_has_reviewed(customer, product, delivered_order):
    Review.objects.create(product=product, author=customer, rating=4)

    assert status(customer, product) == "has_reviewed"


@pytest.mark.parametrize("order_status", [Order.Status.PLACED, Order.Status.SHIPPED])
def test_an_order_not_yet_delivered_is_on_its_way(
    make_order, customer, product, order_status
):
    make_order(customer, product, order_status)

    assert status(customer, product) == "on_its_way"


def test_one_delivered_order_beats_one_on_its_way(
    make_order, customer, product, delivered_order
):
    make_order(customer, product, Order.Status.SHIPPED)

    assert status(customer, product) == "can_review"


def test_a_customer_who_never_ordered_is_not_a_buyer(customer, product):
    assert status(customer, product) == "not_a_buyer"


def test_cancelled_orders_alone_are_not_a_buyer(make_order, customer, product):
    make_order(customer, product, Order.Status.CANCELLED)
    make_order(customer, product, Order.Status.CANCELLED)

    assert status(customer, product) == "not_a_buyer"


def test_a_delivered_order_of_another_product_does_not_count(
    make_order, customer, product, featured_product
):
    make_order(customer, featured_product)

    assert status(customer, product) == "not_a_buyer"


def test_staff_without_a_delivered_order_are_staff(staff_user, product):
    assert status(staff_user, product) == "staff"


def test_staff_with_an_order_on_its_way_are_still_staff(
    make_order, staff_user, product
):
    make_order(staff_user, product, Order.Status.SHIPPED)

    assert status(staff_user, product) == "staff"


def test_staff_with_their_own_delivered_order_review_like_anyone(
    make_order, staff_user, product
):
    make_order(staff_user, product)
    assert status(staff_user, product) == "can_review"

    Review.objects.create(product=product, author=staff_user, rating=5)
    assert status(staff_user, product) == "has_reviewed"


def test_a_delivered_buyer_of_an_unavailable_product_can_review(
    make_order, customer, unavailable_product
):
    make_order(customer, unavailable_product)

    assert status(customer, unavailable_product) == "can_review"


def test_summary_gives_the_average_and_count(customer, staff_user, product):
    Review.objects.create(product=product, author=customer, rating=4)
    Review.objects.create(product=product, author=staff_user, rating=5)

    summary = Review.objects.summary(product)

    assert summary["count"] == 2
    assert summary["average"] == 4.5
    assert summary["filled"] == 5


def test_summary_of_a_product_with_no_reviews(product):
    assert Review.objects.summary(product) == {
        "average": None,
        "count": 0,
        "filled": 0,
    }
