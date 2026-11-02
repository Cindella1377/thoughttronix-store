import datetime
import re
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .forms import EmailChangeForm

# --- Signup -----------------------------------------------------------------


def test_signup_page_returns_200(client, db):
    response = client.get(reverse("accounts:signup"))

    assert response.status_code == HTTPStatus.OK


def test_signup_creates_plain_customer(client, db):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "email": "fresh@example.com",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
        follow=True,
    )

    user = get_user_model().objects.get(username="fresh-thinker")
    assert user.email == "fresh@example.com"
    assert not user.is_staff
    assert not user.is_superuser

    # Signup hands off to the login page with a confirmation message;
    # auto-login is a student exercise, so the visitor is still anonymous.
    assert response.redirect_chain[-1][0] == reverse("accounts:login")
    assert "Account created" in response.content.decode()
    assert not response.context["user"].is_authenticated


def test_signup_password_mismatch_shows_field_error(client, db):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "email": "fresh@example.com",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9001",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["password2"]
    assert not get_user_model().objects.filter(username="fresh-thinker").exists()


def test_signup_requires_an_email(client, db):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["email"]
    assert not get_user_model().objects.filter(username="fresh-thinker").exists()


def test_signup_rejects_an_email_already_in_use(client, customer):
    """Capitalisation does not make an email a different one."""
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "email": "Customer@Example.com",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["email"] == [
        "An account with this email already exists."
    ]
    assert "An account with this email already exists." in response.content.decode()
    assert not get_user_model().objects.filter(username="fresh-thinker").exists()


# --- The email rule ----------------------------------------------------------


def test_two_accounts_cannot_share_an_email(customer):
    with pytest.raises(IntegrityError), transaction.atomic():
        get_user_model().objects.create_user(
            username="twin", email=customer.email, password="x"
        )


def test_email_uniqueness_ignores_capitalisation(customer):
    with pytest.raises(IntegrityError), transaction.atomic():
        get_user_model().objects.create_user(
            username="twin", email="CUSTOMER@example.com", password="x"
        )


def test_model_validation_refuses_a_blank_or_duplicate_email(customer):
    """What the admin site relies on to refuse a bad email."""
    User = get_user_model()

    with pytest.raises(ValidationError) as blank:
        User(username="blank", password="x").full_clean()
    assert "email" in blank.value.message_dict

    with pytest.raises(ValidationError) as duplicate:
        User(username="twin", email="Customer@example.com", password="x").full_clean()
    assert "An account with this email already exists." in duplicate.value.messages


# --- Login and logout --------------------------------------------------------


def test_login_page_returns_200(client, db):
    response = client.get(reverse("accounts:login"))

    assert response.status_code == HTTPStatus.OK


def test_login_round_trip(client, customer):
    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert response.context["user"] == customer


def test_login_bad_credentials_stays_put(client, customer):
    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "wrong"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].non_field_errors()


def test_logout_signs_out_with_message(client, customer):
    client.force_login(customer)

    response = client.post(reverse("accounts:logout"), follow=True)

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert "You have signed out." in response.content.decode()
    assert not response.context["user"].is_authenticated


# --- Forgotten password -------------------------------------------------------


def _reset_link(message):
    """The reset link's path, as found in a reset email."""
    return re.search(r"https?://[^/\s]+(/\S+)", message.body).group(1)


def _request_reset(client, email):
    return client.post(reverse("accounts:password_reset"), {"email": email})


class _TokensFromThePast(PasswordResetTokenGenerator):
    """Makes reset tokens as they would have been made ``age`` ago."""

    def __init__(self, age):
        super().__init__()
        self.age = age

    def _now(self):
        return datetime.datetime.now() - self.age


def _aged_reset_link(user, age):
    return reverse(
        "accounts:password_reset_confirm",
        kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": _TokensFromThePast(age).make_token(user),
        },
    )


def test_login_page_links_to_password_reset(client, db):
    page = client.get(reverse("accounts:login")).content.decode()

    assert reverse("accounts:password_reset") in page


def test_reset_request_page_returns_200(client, db):
    response = client.get(reverse("accounts:password_reset"))

    assert response.status_code == HTTPStatus.OK


def test_reset_request_emails_a_link_and_the_username(client, customer, mailoutbox):
    # Typed in different capitals than the account's own.
    response = _request_reset(client, "Customer@Example.com")

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:password_reset_done")
    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert message.to == ["customer@example.com"]
    assert message.subject == "Reset your ThoughtTronix password"
    assert "Your username, in case that slipped your mind too: customer" in message.body
    assert _reset_link(message).startswith("/accounts/password/reset/")


def test_console_backend_prints_the_reset_link_on_one_line(
    client, customer, settings, capsys
):
    """The default backend: the link must be copyable from the terminal."""
    settings.EMAIL_BACKEND = "config.mail.ConsoleEmailBackend"

    _request_reset(client, customer.email)

    printed = capsys.readouterr().out
    assert "To: customer@example.com" in printed
    link = re.search(r"http://testserver(/accounts/password/reset/\S+/\S+/)\n", printed)
    assert client.get(link.group(1), follow=True).context["validlink"]


def test_reset_request_for_unknown_email_looks_the_same(client, customer, mailoutbox):
    response = _request_reset(client, "nobody@example.com")

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:password_reset_done")
    assert mailoutbox == []


def test_reset_sent_page_returns_200(client, db):
    response = client.get(reverse("accounts:password_reset_done"))

    assert response.status_code == HTTPStatus.OK
    assert "Check your inbox" in response.content.decode()


def test_reset_link_sets_a_new_password_then_hands_off_to_login(
    client, customer, mailoutbox
):
    _request_reset(client, customer.email)

    form_page = client.get(_reset_link(mailoutbox[0]), follow=True)
    assert form_page.context["validlink"]

    response = client.post(
        form_page.redirect_chain[-1][0],
        {
            "new_password1": "neural-implant-9000",
            "new_password2": "neural-implant-9000",
        },
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:login")
    assert "Password changed" in response.content.decode()
    assert not response.context["user"].is_authenticated
    customer.refresh_from_db()
    assert customer.check_password("neural-implant-9000")


def test_reset_link_works_only_once(client, customer, mailoutbox):
    _request_reset(client, customer.email)
    link = _reset_link(mailoutbox[0])
    form_page = client.get(link, follow=True)
    client.post(
        form_page.redirect_chain[-1][0],
        {
            "new_password1": "neural-implant-9000",
            "new_password2": "neural-implant-9000",
        },
    )

    response = client.get(link, follow=True)

    page = response.content.decode()
    assert not response.context["validlink"]
    assert "This link has expired" in page
    assert "Request a new link" in page
    assert reverse("accounts:password_reset") in page


def test_reset_link_expires_after_one_hour(client, customer):
    fresh = _aged_reset_link(customer, datetime.timedelta(minutes=59))
    stale = _aged_reset_link(customer, datetime.timedelta(minutes=61))

    assert client.get(fresh, follow=True).context["validlink"]

    response = client.get(stale, follow=True)

    assert not response.context["validlink"]
    assert "Request a new link" in response.content.decode()


def test_reset_rejects_mismatched_new_passwords(client, customer, mailoutbox):
    _request_reset(client, customer.email)
    form_page = client.get(_reset_link(mailoutbox[0]), follow=True)

    response = client.post(
        form_page.redirect_chain[-1][0],
        {
            "new_password1": "neural-implant-9000",
            "new_password2": "neural-implant-9001",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["new_password2"]
    customer.refresh_from_db()
    assert customer.check_password("customer123")


# --- The account page -----------------------------------------------------------


def test_account_page_requires_sign_in(client, db):
    response = client.get(reverse("accounts:account"))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))


def test_account_page_shows_username_and_email(client, customer):
    client.force_login(customer)

    page = client.get(reverse("accounts:account")).content.decode()

    assert "customer" in page
    assert "customer@example.com" in page
    assert reverse("accounts:password_change") in page


# --- Changing the email --------------------------------------------------------


def test_change_email_saves_and_notifies_the_old_address(customer, mailoutbox):
    customer.change_email("casey@example.com")

    customer.refresh_from_db()
    assert customer.email == "casey@example.com"
    assert len(mailoutbox) == 1
    notice = mailoutbox[0]
    assert notice.to == ["customer@example.com"]
    assert notice.subject == "Your ThoughtTronix email was changed"
    assert "Hello customer" in notice.body
    assert "casey@example.com" not in notice.body


def test_email_change_form_accepts_a_new_address(customer):
    form = EmailChangeForm(
        customer,
        {"email": "casey@example.com", "current_password": "customer123"},
    )

    assert form.is_valid()


def test_email_change_form_rejects_a_wrong_password(customer):
    form = EmailChangeForm(
        customer, {"email": "casey@example.com", "current_password": "wrong"}
    )

    assert form.errors["current_password"] == ["That is not your current password."]


def test_email_change_form_rejects_another_accounts_address(customer, staff_user):
    form = EmailChangeForm(
        customer,
        {"email": "Employee@Example.com", "current_password": "customer123"},
    )

    assert form.errors["email"] == ["An account with this email already exists."]


def test_email_change_form_rejects_an_unchanged_address(customer):
    form = EmailChangeForm(
        customer,
        {"email": "Customer@Example.com", "current_password": "customer123"},
    )

    assert form.errors["email"] == ["That is already your email."]


def test_changing_email_on_the_account_page(client, customer, mailoutbox):
    client.force_login(customer)

    response = client.post(
        reverse("accounts:account"),
        {"email": "casey@example.com", "current_password": "customer123"},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:account")
    page = response.content.decode()
    assert "Email changed." in page
    assert "casey@example.com" in page
    customer.refresh_from_db()
    assert customer.email == "casey@example.com"
    assert [message.to for message in mailoutbox] == [["customer@example.com"]]


def test_refused_email_change_changes_nothing(client, customer, mailoutbox):
    client.force_login(customer)

    response = client.post(
        reverse("accounts:account"),
        {"email": "casey@example.com", "current_password": "wrong"},
    )

    assert response.status_code == HTTPStatus.OK
    assert "That is not your current password." in response.content.decode()
    customer.refresh_from_db()
    assert customer.email == "customer@example.com"
    assert mailoutbox == []


def test_changing_email_requires_sign_in(client, customer, mailoutbox):
    response = client.post(
        reverse("accounts:account"),
        {"email": "casey@example.com", "current_password": "customer123"},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))
    customer.refresh_from_db()
    assert customer.email == "customer@example.com"
    assert mailoutbox == []


# --- Changing the password -----------------------------------------------------


def test_change_password_requires_sign_in(client, db):
    response = client.get(reverse("accounts:password_change"))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))


def test_change_password_rejects_a_wrong_current_password(client, customer):
    client.force_login(customer)

    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "wrong",
            "new_password1": "neural-implant-9000",
            "new_password2": "neural-implant-9000",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["old_password"]
    customer.refresh_from_db()
    assert customer.check_password("customer123")


def test_change_password_keeps_this_session_and_ends_the_others(client, customer):
    other_device = Client()
    other_device.force_login(customer)
    client.force_login(customer)

    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "customer123",
            "new_password1": "neural-implant-9000",
            "new_password2": "neural-implant-9000",
        },
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:account")
    assert "Password changed." in response.content.decode()
    assert response.context["user"] == customer
    customer.refresh_from_db()
    assert customer.check_password("neural-implant-9000")

    elsewhere = other_device.get(reverse("accounts:account"))
    assert elsewhere.status_code == HTTPStatus.FOUND
    assert elsewhere.url.startswith(reverse("accounts:login"))


# --- Auth-aware navbar --------------------------------------------------------


def test_navbar_offers_login_and_signup_to_visitors(client, db):
    page = client.get(reverse("products:catalog")).content.decode()

    assert reverse("accounts:login") in page
    assert reverse("accounts:signup") in page
    assert "Sign out" not in page
    assert f'href="{reverse("accounts:account")}"' not in page


def test_navbar_greets_signed_in_customer(client, customer):
    client.force_login(customer)

    page = client.get(reverse("products:catalog")).content.decode()

    assert "Hi, customer" in page
    assert f'href="{reverse("accounts:account")}"' in page
    assert "Sign out" in page
    assert reverse("accounts:signup") not in page
