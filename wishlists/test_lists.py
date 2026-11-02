"""Several lists: the form and the create, rename, star, and delete views —
coverage priorities 1 and 7 in the wishlists PRD."""

from http import HTTPStatus

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

from .forms import WishlistForm
from .models import MAX_LISTS, Wishlist


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


# Model rules


def test_a_users_first_list_becomes_main(customer):
    assert Wishlist.objects.create_for(customer, "Birthday").is_main


def test_later_lists_are_not_main(birthday):
    assert not birthday.is_main


def test_names_are_unique_per_owner_ignoring_case(customer, birthday):
    with pytest.raises(IntegrityError):
        Wishlist.objects.create(owner=customer, name="BIRTHDAY")


def test_two_owners_may_share_a_name(birthday, staff_user):
    Wishlist.objects.create_for(staff_user, "Birthday")


def test_make_main_moves_the_star(main, birthday):
    birthday.make_main()
    main.refresh_from_db()

    assert birthday.is_main
    assert not main.is_main
    assert Wishlist.objects.main_for(birthday.owner) == birthday


def test_main_list_cannot_be_deleted(main):
    with pytest.raises(ValidationError):
        main.delete()


# WishlistForm


def test_form_rejects_a_duplicate_name_in_any_case(customer, birthday):
    form = WishlistForm(customer, data={"name": "  birthDAY "})

    assert not form.is_valid()
    assert "name" in form.errors


def test_form_rejects_a_name_over_50_characters(customer):
    form = WishlistForm(customer, data={"name": "x" * 51})

    assert not form.is_valid()
    assert "name" in form.errors


def test_form_rejects_a_list_past_the_cap(customer):
    for number in range(MAX_LISTS):
        Wishlist.objects.create_for(customer, f"List {number}")

    form = WishlistForm(customer, data={"name": "One too many"})

    assert not form.is_valid()
    assert form.non_field_errors()


def test_renaming_may_keep_the_same_name(customer, birthday):
    form = WishlistForm(customer, data={"name": "Birthday"}, instance=birthday)

    assert form.is_valid()


def test_renaming_follows_the_name_rule(customer, main, birthday):
    form = WishlistForm(customer, data={"name": "my wishlist"}, instance=birthday)

    assert not form.is_valid()


def test_renaming_is_allowed_at_the_cap(customer):
    lists = [
        Wishlist.objects.create_for(customer, f"List {n}") for n in range(MAX_LISTS)
    ]

    form = WishlistForm(customer, data={"name": "Renamed"}, instance=lists[-1])

    assert form.is_valid()


# Views


def test_index_creates_a_list(signed_in, customer, main):
    response = signed_in.post(reverse("wishlists:index"), {"name": "Birthday"})

    assert response.status_code == HTTPStatus.FOUND
    assert customer.wishlists.filter(name="Birthday", is_main=False).exists()


def test_index_shows_a_form_error_on_a_duplicate(signed_in, birthday):
    response = signed_in.post(reverse("wishlists:index"), {"name": "birthday"})

    assert response.status_code == HTTPStatus.OK
    assert b"You already have a list with that name." in response.content


def test_rename_view_renames(signed_in, birthday):
    signed_in.post(reverse("wishlists:rename", args=[birthday.pk]), {"name": "Gifts"})
    birthday.refresh_from_db()

    assert birthday.name == "Gifts"


def test_make_main_view_stars_the_list_and_the_lamp_follows(
    signed_in, customer, birthday, product
):
    signed_in.post(reverse("wishlists:make_main", args=[birthday.pk]))
    signed_in.post(reverse("wishlists:lamp", args=[product.pk]))

    birthday.refresh_from_db()
    assert birthday.is_main
    assert birthday.has(product)


def test_delete_confirmation_names_the_list_and_its_items(signed_in, birthday, product):
    birthday.add(product)

    response = signed_in.get(reverse("wishlists:delete", args=[birthday.pk]))

    assert b"Delete &ldquo;Birthday&rdquo; and its 1 item?" in response.content


def test_delete_removes_the_list_and_its_items(signed_in, customer, birthday, product):
    birthday.add(product)

    signed_in.post(reverse("wishlists:delete", args=[birthday.pk]))

    assert not customer.wishlists.filter(pk=birthday.pk).exists()
    assert not birthday.items.exists()


def test_deleting_the_main_list_is_refused(signed_in, main):
    response = signed_in.post(reverse("wishlists:delete", args=[main.pk]), follow=True)

    assert Wishlist.objects.filter(pk=main.pk).exists()
    assert b"Star another list" in response.content


@pytest.mark.parametrize("name", ["rename", "make_main", "delete"])
def test_another_users_list_is_a_404(client, staff_user, birthday, name):
    client.force_login(staff_user)

    response = client.post(reverse(f"wishlists:{name}", args=[birthday.pk]))

    assert response.status_code == HTTPStatus.NOT_FOUND
