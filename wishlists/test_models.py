"""Wishlist model rules — coverage priorities 1 and 2 in the wishlists PRD."""

import pytest
from django.db import IntegrityError

from .models import MAIN_LIST_NAME, Wishlist, WishlistItem


def test_main_for_creates_my_wishlist_once(customer):
    first = Wishlist.objects.main_for(customer)
    again = Wishlist.objects.main_for(customer)

    assert first == again
    assert first.name == MAIN_LIST_NAME
    assert first.is_main
    assert customer.wishlists.count() == 1


def test_database_refuses_a_second_main_list(customer):
    Wishlist.objects.main_for(customer)

    with pytest.raises(IntegrityError):
        Wishlist.objects.create(owner=customer, name="Birthday", is_main=True)


def test_two_owners_each_get_their_own_main_list(customer, staff_user):
    assert Wishlist.objects.main_for(customer) != Wishlist.objects.main_for(staff_user)


def test_a_product_cannot_appear_twice_in_one_list(customer, product):
    wishlist = Wishlist.objects.main_for(customer)
    wishlist.add(product)
    wishlist.add(product)

    assert wishlist.items.count() == 1
    with pytest.raises(IntegrityError):
        WishlistItem.objects.create(wishlist=wishlist, product=product, position=9)


def test_toggle_adds_then_removes(customer, product):
    wishlist = Wishlist.objects.main_for(customer)

    assert wishlist.toggle(product) is True
    assert wishlist.has(product)
    assert wishlist.toggle(product) is False
    assert not wishlist.has(product)


def test_new_items_land_on_top(customer, product, featured_product):
    wishlist = Wishlist.objects.main_for(customer)
    wishlist.add(product)
    wishlist.add(featured_product)

    assert list(wishlist.products()) == [featured_product, product]


def test_deleting_a_product_removes_it_from_lists(customer, product):
    wishlist = Wishlist.objects.main_for(customer)
    wishlist.add(product)

    product.delete()

    assert wishlist.items.count() == 0
