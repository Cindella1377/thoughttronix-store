"""Public pages and first names — coverage priorities 8 and 10 in the PRD."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from .models import Wishlist


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


@pytest.fixture
def birthday(customer, product):
    Wishlist.objects.main_for(customer)
    wishlist = Wishlist.objects.create_for(customer, "Birthday")
    wishlist.add(product)
    return wishlist


def public_page(client, username="customer"):
    return client.get(reverse("wishlists:public", args=[username]))


def switch(client, wishlist, on):
    data = {"on": "on"} if on else {}
    return client.post(reverse("wishlists:public_toggle", args=[wishlist.pk]), data)


# The switch


def test_public_switch_toggles_independently_of_the_link(signed_in, birthday):
    response = switch(signed_in, birthday, on=True)
    birthday.refresh_from_db()

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    assert birthday.is_public
    assert birthday.share_token is None

    switch(signed_in, birthday, on=False)
    birthday.refresh_from_db()
    assert not birthday.is_public


def test_another_users_public_switch_is_a_404(client, staff_user, birthday):
    client.force_login(staff_user)

    assert switch(client, birthday, on=True).status_code == HTTPStatus.NOT_FOUND


# The public page


def test_public_page_shows_only_public_lists(client, customer, birthday):
    birthday.set_public(True)
    linked = Wishlist.objects.create_for(customer, "Linked only")
    linked.set_link_sharing(True)

    response = public_page(client)

    assert response.status_code == HTTPStatus.OK
    assert b"Birthday" in response.content
    assert b"Seraphine Home Hub" in response.content
    assert b"Linked only" not in response.content
    assert b"My Wishlist" not in response.content


def test_public_page_has_no_owner_controls_or_email(client, customer, birthday):
    birthday.set_public(True)

    content = public_page(client).content.decode()

    assert reverse("wishlists:detail", args=[birthday.pk]) not in content
    assert customer.email not in content


def test_real_user_with_nothing_public_gets_the_empty_state(client, birthday):
    response = public_page(client)

    assert response.status_code == HTTPStatus.OK
    assert b"hasn't shared any lists yet" in response.content
    assert reverse("products:catalog").encode() in response.content


def test_unknown_username_is_a_404(client, db):
    assert public_page(client, "nobody-here").status_code == HTTPStatus.NOT_FOUND


# First names


def test_first_name_form_saves_the_name(signed_in, customer):
    response = signed_in.post(
        reverse("accounts:first_name"), {"first_name": "Casey"}, follow=True
    )
    customer.refresh_from_db()

    assert customer.first_name == "Casey"
    assert b"Name saved." in response.content


def test_first_name_form_clears_the_name(signed_in, customer):
    customer.first_name = "Casey"
    customer.save()

    signed_in.post(reverse("accounts:first_name"), {"first_name": ""})
    customer.refresh_from_db()

    assert customer.first_name == ""


def test_first_name_form_shows_errors_on_the_account_page(signed_in):
    response = signed_in.post(reverse("accounts:first_name"), {"first_name": "x" * 151})

    assert response.status_code == HTTPStatus.OK
    assert b"Change email" in response.content
    assert b"at most 150 characters" in response.content


def test_first_name_form_requires_sign_in(client, db):
    response = client.post(reverse("accounts:first_name"), {"first_name": "Casey"})

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response["Location"]


def test_account_page_shows_the_first_name_form(signed_in):
    response = signed_in.get(reverse("accounts:account"))

    assert reverse("accounts:first_name").encode() in response.content


def test_headings_use_the_first_name(client, customer, birthday):
    customer.first_name = "Casey"
    customer.save()
    birthday.set_public(True)
    birthday.set_link_sharing(True)

    shared = client.get(reverse("wishlists:shared", args=[birthday.share_token]))

    assert b"Casey's wishlists" in public_page(client).content
    assert b"Casey's Birthday" in shared.content


def test_headings_fall_back_to_the_username(client, birthday):
    birthday.set_link_sharing(True)

    shared = client.get(reverse("wishlists:shared", args=[birthday.share_token]))

    assert b"customer's wishlists" in public_page(client).content
    assert b"customer's Birthday" in shared.content


def test_first_name_prompt_shows_only_when_blank(signed_in, customer):
    prompt = b"Add your first name so friends recognise your lists."
    assert prompt in signed_in.get(reverse("wishlists:index")).content

    customer.first_name = "Casey"
    customer.save()

    assert prompt not in signed_in.get(reverse("wishlists:index")).content
