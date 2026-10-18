"""Reordering — coverage priority 2 in the wishlists PRD."""

from decimal import Decimal
from http import HTTPStatus

import pytest
from django.urls import reverse

from products.models import Product

from .models import Wishlist


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


@pytest.fixture
def three(category):
    """Three products, named so the expected order reads easily."""
    return [
        Product.objects.create(
            name=name, slug=name.lower(), price=Decimal("10.00"), category=category
        )
        for name in ["Alpha", "Bravo", "Charlie"]
    ]


@pytest.fixture
def wishlist(customer, three):
    wishlist = Wishlist.objects.main_for(customer)
    for product in three:
        wishlist.add(product)
    return wishlist  # Charlie, Bravo, Alpha — newest first


def names(wishlist):
    return [product.name for product in wishlist.products()]


def item(wishlist, name):
    return wishlist.items.get(product__name=name)


def move(client, wishlist, name, direction):
    return client.post(
        reverse(
            "wishlists:item_move",
            args=[wishlist.pk, item(wishlist, name).pk, direction],
        )
    )


def test_move_up_swaps_with_the_item_above(wishlist):
    wishlist.move_up(item(wishlist, "Alpha"))

    assert names(wishlist) == ["Charlie", "Alpha", "Bravo"]


def test_move_down_swaps_with_the_item_below(wishlist):
    wishlist.move_down(item(wishlist, "Charlie"))

    assert names(wishlist) == ["Bravo", "Charlie", "Alpha"]


def test_moves_past_the_ends_do_nothing(wishlist):
    wishlist.move_up(item(wishlist, "Charlie"))
    wishlist.move_down(item(wishlist, "Alpha"))

    assert names(wishlist) == ["Charlie", "Bravo", "Alpha"]


def test_a_product_added_after_a_reorder_lands_on_top(wishlist, featured_product):
    wishlist.move_up(item(wishlist, "Alpha"))
    wishlist.move_up(item(wishlist, "Alpha"))

    wishlist.add(featured_product)

    assert names(wishlist) == ["SoulSear Mark II", "Alpha", "Charlie", "Bravo"]


def test_move_endpoint_rerenders_in_the_new_order(signed_in, wishlist):
    response = move(signed_in, wishlist, "Alpha", "up")

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    content = response.content.decode()
    assert content.index("Charlie") < content.index("Alpha") < content.index("Bravo")


def test_move_endpoint_rejects_other_directions(signed_in, wishlist):
    response = move(signed_in, wishlist, "Alpha", "sideways")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_another_users_item_is_a_404(client, staff_user, wishlist):
    client.force_login(staff_user)

    response = move(client, wishlist, "Alpha", "up")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert names(wishlist) == ["Charlie", "Bravo", "Alpha"]


def test_top_and_bottom_arrows_are_disabled(signed_in, wishlist):
    response = signed_in.get(reverse("wishlists:detail", args=[wishlist.pk]))

    assert response.content.count(b"disabled") == 2
