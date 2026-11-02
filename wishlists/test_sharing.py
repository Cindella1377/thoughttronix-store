"""Share by link — coverage priorities 3 and 4 in the wishlists PRD."""

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


@pytest.fixture
def shared(birthday):
    birthday.set_link_sharing(True)
    return birthday


def shared_url(wishlist):
    return reverse("wishlists:shared", args=[wishlist.share_token])


def switch(client, wishlist, on):
    data = {"on": "on"} if on else {}
    return client.post(reverse("wishlists:link_sharing", args=[wishlist.pk]), data)


# Model


def test_turning_sharing_on_stores_a_token(birthday):
    birthday.set_link_sharing(True)

    assert birthday.share_token


def test_turning_sharing_off_clears_the_token(shared):
    shared.set_link_sharing(False)

    assert shared.share_token is None


def test_turning_sharing_back_on_gives_a_new_token(shared):
    old = shared.share_token
    shared.set_link_sharing(False)
    shared.set_link_sharing(True)

    assert shared.share_token != old


def test_turning_on_a_shared_list_keeps_its_token(shared):
    old = shared.share_token
    shared.set_link_sharing(True)

    assert shared.share_token == old


# The switch


def test_switch_turns_sharing_on_and_shows_the_link(signed_in, birthday):
    response = switch(signed_in, birthday, on=True)
    birthday.refresh_from_db()

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    assert shared_url(birthday).encode() in response.content


def test_switch_off_makes_the_old_link_404(signed_in, client, shared):
    url = shared_url(shared)

    switch(signed_in, shared, on=False)
    client.logout()

    assert client.get(url).status_code == HTTPStatus.NOT_FOUND


def test_switch_on_again_never_revives_the_old_link(signed_in, shared):
    old_url = shared_url(shared)

    switch(signed_in, shared, on=False)
    switch(signed_in, shared, on=True)

    assert signed_in.get(old_url).status_code == HTTPStatus.NOT_FOUND


def test_another_users_switch_is_a_404(client, staff_user, birthday):
    client.force_login(staff_user)

    response = switch(client, birthday, on=True)
    birthday.refresh_from_db()

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert birthday.share_token is None


def test_index_shows_each_lists_switch(signed_in, birthday):
    response = signed_in.get(reverse("wishlists:index"))

    assert reverse("wishlists:link_sharing", args=[birthday.pk]).encode() in (
        response.content
    )


# The shared page


def test_visitor_can_view_a_shared_list(client, shared):
    response = client.get(shared_url(shared))

    assert response.status_code == HTTPStatus.OK
    assert b"customer's Birthday" in response.content
    assert b"Seraphine Home Hub" in response.content


def test_shared_page_has_no_owner_controls(signed_in, shared):
    content = signed_in.get(shared_url(shared)).content.decode()

    # Every owner control posts under the list's own pk path.
    assert reverse("wishlists:detail", args=[shared.pk]) not in content
    assert "✕" not in content
    assert "Make main" not in content


def test_shared_page_hides_the_owners_email_and_other_lists(client, customer, shared):
    other = Wishlist.objects.create_for(customer, "Secret plans")

    content = client.get(shared_url(shared)).content.decode()

    assert customer.email not in content
    assert other.name not in content


def test_viewer_lamp_saves_to_the_viewers_own_main_list(
    client, staff_user, customer, shared, product
):
    client.force_login(staff_user)
    page = client.get(shared_url(shared))
    assert b"Add Seraphine Home Hub to your main wishlist" in page.content

    client.post(reverse("wishlists:lamp", args=[product.pk]))

    assert Wishlist.objects.main_for(staff_user).has(product)
    assert shared.items.count() == 1


def test_visitor_buttons_are_sign_in_links_back_to_the_list(client, shared):
    content = client.get(shared_url(shared)).content.decode()

    back = f"{reverse('accounts:login')}?next={shared_url(shared)}"
    assert content.count(back) == 2  # Add to cart and the lamp


def test_unshared_list_is_reachable_only_by_its_owner(client, birthday):
    assert birthday.share_token is None
    assert not Wishlist.objects.filter(share_token="").exists()
    assert client.get(reverse("wishlists:shared", args=["guess"])).status_code == (
        HTTPStatus.NOT_FOUND
    )
