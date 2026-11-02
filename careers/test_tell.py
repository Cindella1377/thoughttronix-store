"""Telling the applicant — phase 4 of the careers plan."""

from http import HTTPStatus

import pytest
from django.core import mail
from django.db import transaction
from django.urls import reverse

from .models import Stage
from .services import move_application, submit_application

SECRET_NOTE = "Weak interview, candidly."


class Boom(Exception):
    pass


@pytest.fixture
def as_recruiter(client, recruiter):
    client.force_login(recruiter)
    return client


@pytest.fixture
def application(make_application, make_job, customer):
    return make_application(make_job(), customer)


def stage(kind):
    return Stage.objects.filter(kind=kind).first()


def move_url(application):
    return reverse("careers:move", args=[application.pk])


@pytest.mark.parametrize(
    ("kind", "label"),
    [
        (Stage.Kind.ENTRY, "Received"),
        (Stage.Kind.IN_PROGRESS, "Under review"),
        (Stage.Kind.HIRED, "Application successful"),
        (Stage.Kind.REJECTED, "Not moving forward"),
        (Stage.Kind.WITHDRAWN, "Withdrawn"),
    ],
)
def test_each_kind_shows_its_label(client, customer, application, kind, label):
    application.stage = stage(kind)
    application.save()
    client.force_login(customer)

    response = client.get(reverse("careers:applications"))

    assert label.encode() in response.content


def test_applying_sends_the_received_email(
    customer, make_job, resume, django_capture_on_commit_callbacks
):
    job = make_job()

    with django_capture_on_commit_callbacks(execute=True):
        submit_application(job, customer, resume)

    message = mail.outbox[0]
    assert len(mail.outbox) == 1
    assert message.to == [customer.email]
    assert job.title in message.subject
    assert "Received" in message.body


def test_nothing_is_sent_before_the_commit(customer, make_job, resume):
    submit_application(make_job(), customer, resume)

    assert mail.outbox == []


@pytest.mark.parametrize(
    ("kind", "label"),
    [
        (Stage.Kind.HIRED, "Application successful"),
        (Stage.Kind.REJECTED, "Not moving forward"),
    ],
)
def test_a_final_move_sends_its_email(
    recruiter, application, kind, label, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        move_application(application, stage(kind), recruiter)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [application.user.email]
    assert label in mail.outbox[0].body


def test_other_moves_send_nothing(
    recruiter, application, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        move_application(application, Stage.objects.get(name="Offer"), recruiter)

    assert mail.outbox == []


def test_a_rolled_back_move_sends_nothing(
    recruiter, application, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(Boom), transaction.atomic():
            move_application(application, stage(Stage.Kind.HIRED), recruiter)
            raise Boom

    assert mail.outbox == []
    application.refresh_from_db()
    assert application.stage.kind == Stage.Kind.ENTRY


def test_a_failed_email_does_not_undo_the_move(
    recruiter, application, django_capture_on_commit_callbacks, settings
):
    settings.EMAIL_BACKEND = "no.such.Backend"

    with django_capture_on_commit_callbacks(execute=True):
        move_application(application, stage(Stage.Kind.HIRED), recruiter)

    application.refresh_from_db()
    assert application.stage.kind == Stage.Kind.HIRED


def test_stage_names_and_notes_stay_out_of_applicant_view(
    client,
    customer,
    recruiter,
    application,
    django_capture_on_commit_callbacks,
):
    hired = stage(Stage.Kind.HIRED)
    Stage.objects.filter(pk=hired.pk).update(name="Maybe pile")
    hired.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        move_application(application, hired, recruiter, note=SECRET_NOTE)

    client.force_login(customer)
    pages = [
        client.get(reverse("careers:applications")).content.decode(),
        client.get(application.job.get_absolute_url()).content.decode(),
    ]
    message = mail.outbox[0]
    for text in (*pages, message.subject, message.body):
        assert "Maybe pile" not in text
        assert SECRET_NOTE not in text


@pytest.mark.parametrize("kind", [Stage.Kind.HIRED, Stage.Kind.REJECTED])
def test_a_final_move_asks_first(as_recruiter, application, kind):
    response = as_recruiter.post(
        move_url(application),
        {"stage": stage(kind).pk, "note": "Sharp."},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    assert b"This will email the applicant" in response.content
    assert b'value="Sharp."' in response.content
    application.refresh_from_db()
    assert application.stage.kind == Stage.Kind.ENTRY


def test_without_htmx_the_warning_is_a_full_page(as_recruiter, application):
    response = as_recruiter.post(
        move_url(application), {"stage": stage(Stage.Kind.HIRED).pk}
    )

    assert b"<html" in response.content
    assert b"This will email the applicant" in response.content
    application.refresh_from_db()
    assert application.stage.kind == Stage.Kind.ENTRY


def test_confirming_makes_the_move(
    as_recruiter, application, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = as_recruiter.post(
            move_url(application),
            {"stage": stage(Stage.Kind.HIRED).pk, "confirmed": "1"},
        )

    assert response.status_code == HTTPStatus.FOUND
    application.refresh_from_db()
    assert application.stage.kind == Stage.Kind.HIRED
    assert len(mail.outbox) == 1


def test_an_ordinary_move_needs_no_confirmation(as_recruiter, application):
    offer = Stage.objects.get(name="Offer")

    response = as_recruiter.post(
        move_url(application), {"stage": offer.pk}, headers={"HX-Request": "true"}
    )

    detail = reverse("careers:application", args=[application.pk])
    assert response["HX-Redirect"] == detail
    application.refresh_from_db()
    assert application.stage == offer


def test_the_move_form_uses_htmx_not_a_browser_dialog(as_recruiter, application):
    response = as_recruiter.get(reverse("careers:application", args=[application.pk]))

    assert b"hx-post" in response.content
    assert b"hx-confirm" not in response.content
