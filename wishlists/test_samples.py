"""Seeded sample lists — coverage priority 11 in the wishlists PRD.

The seed's data is checked from its constants, without running the command.
"""

import pytest
from django.urls import reverse
from django.utils.text import slugify

from products.management.commands.seed import CATALOG, DEMO_USERS, SAMPLE_WISHLISTS

from .models import Wishlist

BADGE = b"Sample list"


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


@pytest.fixture
def sample(customer, product):
    Wishlist.objects.main_for(customer)
    wishlist = Wishlist.objects.create(owner=customer, name="Birthday", is_sample=True)
    wishlist.add(product)
    return wishlist


@pytest.fixture
def chosen(customer):
    Wishlist.objects.main_for(customer)
    return Wishlist.objects.create_for(customer, "Chosen by me")


# The seed's constants


def test_sample_lists_belong_only_to_demo_users():
    demo_usernames = {username for username, *_ in DEMO_USERS}

    assert {owner for owner, *_ in SAMPLE_WISHLISTS} <= demo_usernames


def test_sample_lists_show_every_sharing_state():
    states = {(public, linked) for _, _, public, linked, _ in SAMPLE_WISHLISTS}

    assert (True, False) in states
    assert (False, True) in states


def test_sample_list_names_are_unique_per_owner():
    names = [(owner, name.lower()) for owner, name, *_ in SAMPLE_WISHLISTS]

    assert len(set(names)) == len(names)
    assert all(name != "my wishlist" for _, name in names)


def test_sample_products_exist_in_the_catalog():
    slugs = {slugify(name) for products in CATALOG.values() for name, *_ in products}

    for *_, products in SAMPLE_WISHLISTS:
        assert set(products) <= slugs
        assert len(set(products)) == len(products)


# The badge


def test_badge_on_the_owners_pages(signed_in, sample):
    index = signed_in.get(reverse("wishlists:index"))
    detail = signed_in.get(reverse("wishlists:detail", args=[sample.pk]))

    assert index.content.count(BADGE) == 1  # not on My Wishlist
    assert BADGE in detail.content


def test_badge_on_the_shared_and_public_pages(client, sample):
    sample.set_link_sharing(True)
    sample.set_public(True)

    shared = client.get(reverse("wishlists:shared", args=[sample.share_token]))
    public = client.get(reverse("wishlists:public", args=["customer"]))

    assert BADGE in shared.content
    assert BADGE in public.content


def test_no_badge_on_lists_the_owner_made(signed_in, chosen):
    chosen.set_link_sharing(True)

    detail = signed_in.get(reverse("wishlists:detail", args=[chosen.pk]))
    shared = signed_in.get(reverse("wishlists:shared", args=[chosen.share_token]))

    assert BADGE not in detail.content
    assert BADGE not in shared.content


def test_a_sample_list_can_be_deleted(signed_in, customer, sample):
    signed_in.post(reverse("wishlists:delete", args=[sample.pk]))

    assert not customer.wishlists.filter(pk=sample.pk).exists()
