"""The genie lamp and the wishlists page — coverage priority 5 in the PRD."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from .models import Wishlist


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


def lamp(client, product):
    return client.post(reverse("wishlists:lamp", args=[product.pk]))


def is_partial(response):
    return b"<html" not in response.content


def test_lamp_adds_to_the_main_list_with_smoke(signed_in, customer, product):
    response = lamp(signed_in, product)

    assert response.status_code == HTTPStatus.OK
    assert is_partial(response)
    assert Wishlist.objects.main_for(customer).has(product)
    assert b"lamp-smoke" in response.content
    assert b"text-amber-400" in response.content


def test_lamp_removes_from_the_main_list_without_smoke(signed_in, customer, product):
    lamp(signed_in, product)
    response = lamp(signed_in, product)

    assert not Wishlist.objects.main_for(customer).has(product)
    assert b"lamp-smoke" not in response.content
    assert b"text-amber-400" not in response.content


def test_lamp_says_what_it_will_do(signed_in, product):
    added = lamp(signed_in, product)
    removed = lamp(signed_in, product)

    assert b"Remove Seraphine Home Hub" in added.content
    assert b"Add Seraphine Home Hub" in removed.content


def test_lamp_works_for_staff(client, staff_user, product):
    client.force_login(staff_user)
    lamp(client, product)

    assert Wishlist.objects.main_for(staff_user).has(product)


def test_lamp_will_not_add_an_unavailable_product(signed_in, unavailable_product):
    response = lamp(signed_in, unavailable_product)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_lamp_removes_a_product_that_became_unavailable(signed_in, customer, product):
    lamp(signed_in, product)
    product.is_available = False
    product.save()

    response = lamp(signed_in, product)

    assert response.status_code == HTTPStatus.OK
    assert not Wishlist.objects.main_for(customer).has(product)


def test_lamp_requires_sign_in(client, product):
    response = lamp(client, product)

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response["Location"]


def test_catalog_shows_gold_lamps_for_saved_products(
    signed_in, customer, product, featured_product
):
    Wishlist.objects.main_for(customer).add(product)

    response = signed_in.get(reverse("products:catalog"))

    assert b"Remove Seraphine Home Hub from your main wishlist" in response.content
    assert b"Add SoulSear Mark II to your main wishlist" in response.content


def test_catalog_renders_lamps_without_creating_a_list(signed_in, customer, product):
    response = signed_in.get(reverse("products:catalog"))

    assert b"Add Seraphine Home Hub to your main wishlist" in response.content
    assert not customer.wishlists.exists()


def test_catalog_lamp_is_a_sign_in_link_for_visitors(client, product):
    response = client.get(reverse("products:catalog"))

    assert b"Sign in to save Seraphine Home Hub" in response.content
    assert f"{reverse('accounts:login')}?next=/".encode() in response.content


def test_navbar_and_account_page_link_to_wishlists(signed_in):
    response = signed_in.get(reverse("accounts:account"))

    assert response.content.count(reverse("wishlists:index").encode()) == 2


def test_navbar_has_no_wishlist_link_for_visitors(client, product):
    response = client.get(reverse("products:catalog"))

    assert reverse("wishlists:index").encode() not in response.content


def test_wishlists_page_shows_the_main_list(signed_in, customer, product):
    wishlist = Wishlist.objects.main_for(customer)
    wishlist.add(product)

    response = signed_in.get(reverse("wishlists:index"))

    assert b"My Wishlist" in response.content
    assert b"1 item" in response.content
    assert reverse("wishlists:detail", args=[wishlist.pk]).encode() in response.content


def test_wishlists_page_has_an_empty_state(signed_in):
    response = signed_in.get(reverse("wishlists:index"))

    assert b"Your lamp is empty" in response.content


def test_wishlists_page_requires_sign_in(client):
    response = client.get(reverse("wishlists:index"))

    assert response.status_code == HTTPStatus.FOUND
