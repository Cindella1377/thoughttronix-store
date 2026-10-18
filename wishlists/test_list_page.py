"""The owner's list page — coverage priorities 4 and 9 in the wishlists PRD."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from .models import Wishlist


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


@pytest.fixture
def main(customer, product):
    wishlist = Wishlist.objects.main_for(customer)
    wishlist.add(product)
    return wishlist


def detail(client, wishlist):
    return client.get(reverse("wishlists:detail", args=[wishlist.pk]))


def remove(client, wishlist, item):
    return client.post(reverse("wishlists:item_remove", args=[wishlist.pk, item.pk]))


def test_owner_sees_their_list(signed_in, main):
    response = detail(signed_in, main)

    assert response.status_code == HTTPStatus.OK
    assert b"Seraphine Home Hub" in response.content
    assert b"Add to cart" in response.content


def test_another_users_list_is_a_404(client, staff_user, main):
    client.force_login(staff_user)

    assert detail(client, main).status_code == HTTPStatus.NOT_FOUND


def test_list_page_requires_sign_in(client, main):
    assert detail(client, main).status_code == HTTPStatus.FOUND


def test_remove_takes_the_item_off_and_rerenders(signed_in, main, featured_product):
    main.add(featured_product)
    item = main.items.get(product=featured_product)

    response = remove(signed_in, main, item)

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    assert not main.has(featured_product)
    assert b"SoulSear Mark II" not in response.content
    assert b"Seraphine Home Hub" in response.content


def test_removing_the_last_item_shows_the_empty_state(signed_in, main):
    response = remove(signed_in, main, main.items.get())

    assert b"Nothing wished for yet" in response.content


def test_another_users_item_cannot_be_removed(client, staff_user, main):
    client.force_login(staff_user)

    response = remove(client, main, main.items.get())

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert main.items.count() == 1


def test_unavailable_product_is_marked_and_cannot_be_bought(signed_in, main, product):
    product.is_available = False
    product.save()

    response = detail(signed_in, main)

    assert b"No longer available" in response.content
    assert b"Add to cart" not in response.content


def test_product_back_on_sale_shows_normally(signed_in, main, product):
    product.is_available = False
    product.save()
    product.is_available = True
    product.save()

    response = detail(signed_in, main)

    assert b"No longer available" not in response.content
    assert b"Add to cart" in response.content


def test_empty_list_has_a_designed_empty_state(signed_in, customer):
    response = detail(signed_in, Wishlist.objects.main_for(customer))

    assert b"Nothing wished for yet" in response.content
