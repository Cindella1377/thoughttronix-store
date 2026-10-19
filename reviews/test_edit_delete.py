"""Edit and delete your own review in place — phase 4 of the reviews plan."""

import datetime
from http import HTTPStatus

import pytest
from django.urls import reverse

from .models import Review

MOMENT = datetime.datetime(2026, 10, 18, 12, 0, tzinfo=datetime.UTC)


@pytest.fixture
def review(customer, product, delivered_order):
    return Review.objects.create(
        product=product, author=customer, rating=4, body="Hears me think."
    )


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


@pytest.fixture
def other_customer(django_user_model):
    return django_user_model.objects.create_user(
        username="other", email="other@example.com", password="other123"
    )


def url(name, review):
    return reverse(f"reviews:{name}", args=[review.pk])


def is_partial(response):
    return b"<html" not in response.content


# --- The model --------------------------------------------------------------


def test_the_author_can_edit(customer, review):
    assert review.can_edit(customer)


def test_another_customer_cannot_edit(other_customer, review):
    assert not review.can_edit(other_customer)


def test_a_visitor_cannot_edit(review):
    from django.contrib.auth.models import AnonymousUser

    assert not review.can_edit(AnonymousUser())


def test_mark_edited_records_the_moment(review):
    review.mark_edited(now=MOMENT)

    assert review.updated_at == MOMENT


# --- The page ---------------------------------------------------------------


def test_the_authors_card_carries_edit_and_delete(signed_in, product, review):
    content = signed_in.get(product.get_absolute_url()).content.decode()

    assert url("edit", review) in content
    assert url("confirm_delete", review) in content


@pytest.mark.parametrize("who", ["visitor", "other"])
def test_nobody_else_sees_edit_or_delete(client, other_customer, product, review, who):
    if who == "other":
        client.force_login(other_customer)

    content = client.get(product.get_absolute_url()).content.decode()

    assert url("edit", review) not in content
    assert url("confirm_delete", review) not in content


def test_your_own_review_is_first_and_not_repeated(
    signed_in, staff_user, product, review
):
    review.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    review.save()
    Review.objects.create(product=product, author=staff_user, rating=5, body="Newer.")

    content = signed_in.get(product.get_absolute_url()).content.decode()

    assert content.index("Hears me think.") < content.index("Newer.")
    assert content.count(f'id="review-{review.pk}"') == 1


def test_an_unedited_review_shows_no_marker(client, product, review):
    content = client.get(product.get_absolute_url()).content.decode()

    assert "edited" not in content


# --- Editing ----------------------------------------------------------------


def test_edit_swaps_the_card_for_the_filled_form(signed_in, review):
    response = signed_in.get(url("edit", review))

    content = response.content.decode()
    assert response.status_code == HTTPStatus.OK
    assert is_partial(response)
    assert f'id="review-{review.pk}"' in content
    assert 'value="4" checked' in content
    assert "Hears me think." in content
    assert url("card", review) in content


def test_saving_an_edit_returns_the_card_and_the_summary(signed_in, review):
    response = signed_in.post(url("edit", review), {"rating": 2, "body": "Hmm."})

    content = response.content.decode()
    review.refresh_from_db()
    assert (review.rating, review.body) == (2, "Hmm.")
    assert review.updated_at is not None
    assert not review.edited_by_staff
    assert f'<article id="review-{review.pk}"' in content
    assert "Space junk" in content
    assert "edited " in content
    assert 'id="review-summary"' in content
    assert "2.0 galaxies (1)" in content


def test_an_invalid_edit_returns_the_form_with_what_was_typed(signed_in, review):
    response = signed_in.post(url("edit", review), {"body": "No galaxies now."})

    content = response.content.decode()
    assert "Choose from one to five galaxies." in content
    assert "No galaxies now." in content
    review.refresh_from_db()
    assert review.rating == 4
    assert review.updated_at is None


def test_cancel_returns_the_card_unchanged(signed_in, review):
    response = signed_in.get(url("card", review))

    content = response.content.decode()
    assert is_partial(response)
    assert f'<article id="review-{review.pk}"' in content
    assert "Hears me think." in content
    assert "<form" not in content


# --- Deleting ---------------------------------------------------------------


def test_delete_asks_first(signed_in, review):
    response = signed_in.get(url("confirm_delete", review))

    content = response.content.decode()
    assert is_partial(response)
    assert "Delete this review?" in content
    assert "Yes, delete" in content
    assert "Keep it" in content
    assert Review.objects.exists()


def test_keep_it_brings_the_buttons_back(signed_in, review):
    response = signed_in.get(url("card", review))

    assert url("confirm_delete", review).encode() in response.content
    assert b"Delete this review?" not in response.content


def test_yes_delete_removes_it_and_brings_the_form_back(signed_in, review):
    response = signed_in.post(url("confirm_delete", review))

    content = response.content.decode()
    assert not Review.objects.exists()
    assert is_partial(response)
    assert 'id="review-form"' in content
    assert 'id="review-summary"' in content
    assert "No reviews yet" in content


# --- Nobody else ------------------------------------------------------------


ENDPOINTS = [
    ("get", "edit"),
    ("post", "edit"),
    ("get", "card"),
    ("get", "confirm_delete"),
    ("post", "confirm_delete"),
]


@pytest.mark.parametrize(("method", "name"), ENDPOINTS)
@pytest.mark.parametrize("who", ["visitor", "other"])
def test_nobody_else_can_reach_the_endpoints(
    client, other_customer, review, method, name, who
):
    if who == "other":
        client.force_login(other_customer)

    response = getattr(client, method)(url(name, review), {"rating": 1, "body": "x"})

    assert response.status_code == HTTPStatus.NOT_FOUND
    review.refresh_from_db()
    assert (review.rating, review.body, review.updated_at) == (
        4,
        "Hears me think.",
        None,
    )
