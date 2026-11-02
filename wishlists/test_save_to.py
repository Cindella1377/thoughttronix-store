"""The product page's main button and "Save to…" — coverage priority 6."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from .models import Wishlist


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


@pytest.fixture
def main(customer):
    return Wishlist.objects.main_for(customer)


@pytest.fixture
def birthday(customer, main):
    return Wishlist.objects.create_for(customer, "Birthday")


def product_page(client, product):
    return client.get(product.get_absolute_url())


def save_to(client, product, wishlist):
    return client.post(reverse("wishlists:save_to", args=[product.pk, wishlist.pk]))


def main_button(client, product):
    return client.post(
        reverse("wishlists:lamp", args=[product.pk]), {"partial": "save_to"}
    )


def test_main_button_offers_to_add(signed_in, main, product):
    response = product_page(signed_in, product)

    assert b"Add to My Wishlist" in response.content


def test_main_button_adds_and_returns_the_controls(signed_in, main, product):
    response = main_button(signed_in, product)

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    assert b'id="save-to"' in response.content
    assert b"Remove from My Wishlist" in response.content
    assert main.has(product)


def test_main_button_removes(signed_in, main, product):
    main.add(product)

    response = main_button(signed_in, product)

    assert b"Add to My Wishlist" in response.content
    assert not main.has(product)


def test_main_button_creates_the_main_list_for_a_new_user(signed_in, customer, product):
    response = product_page(signed_in, product)
    assert b"Add to My Wishlist" in response.content
    assert not customer.wishlists.exists()

    main_button(signed_in, product)

    assert Wishlist.objects.main_for(customer).has(product)


def test_dropdown_ticks_lists_holding_the_product(signed_in, main, birthday, product):
    birthday.add(product)

    response = product_page(signed_in, product)

    assert b'aria-pressed="true"' in response.content
    assert response.content.count(b'aria-pressed="false"') == 1
    assert b"+ New list" in response.content


def test_save_to_adds_then_removes_in_the_chosen_list(
    signed_in, main, birthday, product
):
    save_to(signed_in, product, birthday)
    assert birthday.has(product)
    assert not main.has(product)

    save_to(signed_in, product, birthday)
    assert not birthday.has(product)


def test_button_and_ticks_agree_after_a_change(signed_in, main, birthday, product):
    response = save_to(signed_in, product, main)

    assert b"Remove from My Wishlist" in response.content
    assert response.content.count(b'aria-pressed="true"') == 1


def test_save_to_another_users_list_is_a_404(client, staff_user, birthday, product):
    client.force_login(staff_user)

    response = save_to(client, product, birthday)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not birthday.has(product)


def test_save_to_will_not_add_an_unavailable_product(
    signed_in, birthday, unavailable_product
):
    response = save_to(signed_in, unavailable_product, birthday)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_unavailable_product_page_offers_no_add_button(
    signed_in, main, unavailable_product
):
    response = product_page(signed_in, unavailable_product)

    assert b"Add to My Wishlist" not in response.content


def test_visitor_sees_a_sign_in_link(client, product):
    response = product_page(client, product)

    assert b"Save to wishlist" in response.content
    assert f"?next={product.get_absolute_url()}".encode() in response.content
