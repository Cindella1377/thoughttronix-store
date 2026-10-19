"""The reviews section on the product page — phase 1 of the reviews plan."""

import datetime

from .models import Review


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


def test_anyone_else_sees_no_form(client, customer, product):
    assert 'id="review-form"' not in page(client, product)

    client.force_login(customer)
    assert 'id="review-form"' not in page(client, product)


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
