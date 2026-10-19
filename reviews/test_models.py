"""Review model rules — the phase 1 slice of the reviews PRD."""

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


def test_a_delivered_buyer_can_review(customer, product, delivered_order):
    assert Review.objects.can_review(customer, product)


@pytest.mark.parametrize(
    "status", [Order.Status.PLACED, Order.Status.SHIPPED, Order.Status.CANCELLED]
)
def test_an_order_that_is_not_delivered_does_not_count(
    make_order, customer, product, status
):
    make_order(customer, product, status)

    assert not Review.objects.can_review(customer, product)


def test_a_delivered_order_of_another_product_does_not_count(
    make_order, customer, product, featured_product
):
    make_order(customer, featured_product)

    assert not Review.objects.can_review(customer, product)


def test_a_buyer_who_has_reviewed_cannot_review_again(
    customer, product, delivered_order
):
    Review.objects.create(product=product, author=customer, rating=4)

    assert not Review.objects.can_review(customer, product)


def test_a_visitor_cannot_review(product):
    assert not Review.objects.can_review(AnonymousUser(), product)


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
