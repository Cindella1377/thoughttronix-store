"""Recruiter notes — phase 6 of the careers plan."""

import datetime
from http import HTTPStatus

import pytest
from django.contrib import admin
from django.urls import reverse

from .forms import MAX_NOTE_LENGTH
from .models import Note, Stage
from .services import move_application

HTMX = {"HX-Request": "true"}


@pytest.fixture
def as_recruiter(client, recruiter):
    client.force_login(recruiter)
    return client


@pytest.fixture
def application(make_application, make_job, customer):
    return make_application(make_job(), customer)


def note_url(application):
    return reverse("careers:note", args=[application.pk])


def detail_url(application):
    return reverse("careers:application", args=[application.pk])


def test_a_recruiter_adds_a_note_without_a_reload(as_recruiter, recruiter, application):
    response = as_recruiter.post(
        note_url(application), {"body": "Strong portfolio."}, headers=HTMX
    )

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    assert b'id="timeline"' in response.content
    assert b"Strong portfolio." in response.content
    note = Note.objects.get()
    assert (note.application, note.author) == (application, recruiter)


def test_without_htmx_a_note_returns_to_the_page(as_recruiter, application):
    response = as_recruiter.post(note_url(application), {"body": "Noted."})

    assert response.url == detail_url(application)
    assert Note.objects.count() == 1


def test_without_htmx_a_refused_note_explains_itself(as_recruiter, application):
    response = as_recruiter.post(note_url(application), {"body": ""}, follow=True)

    assert b"Write a note" in response.content
    assert not Note.objects.exists()


def test_add_note_takes_a_moment(application, recruiter, now):
    note = application.add_note(recruiter, "Noted.", now=now)

    assert note.created_at == now


def test_the_timeline_merges_moves_and_notes_in_order(application, recruiter, now):
    day = datetime.timedelta(days=1)
    application.stage_changes.update(created_at=now)
    second = application.add_note(recruiter, "Second.", now=now + day)
    moved = move_application(
        application,
        Stage.objects.get(name="Offer"),
        recruiter,
        now=now + 2 * day,
    )
    fourth = application.add_note(recruiter, "Fourth.", now=now + 3 * day)

    timeline = moved.timeline()

    assert timeline[1] == second
    assert timeline[2].to_stage.name == "Offer"
    assert timeline[3] == fourth
    assert len(timeline) == 4


def test_the_detail_page_shows_the_timeline(as_recruiter, recruiter, application):
    application.add_note(recruiter, "Check references.")

    response = as_recruiter.get(detail_url(application))

    assert b"Check references." in response.content
    assert b"Applied to" in response.content
    assert recruiter.display_name.encode() in response.content


def test_the_form_says_notes_are_permanent(as_recruiter, application):
    response = as_recruiter.get(detail_url(application))

    assert b"can&#x27;t be edited" in response.content


@pytest.mark.parametrize("body", ["", "   "])
def test_a_blank_note_is_refused_in_place(as_recruiter, application, body):
    response = as_recruiter.post(note_url(application), {"body": body}, headers=HTMX)

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    assert b"This field is required" in response.content
    assert not Note.objects.exists()


def test_a_long_note_is_refused_and_kept_in_the_form(as_recruiter, application):
    body = "x" * (MAX_NOTE_LENGTH + 1)

    response = as_recruiter.post(note_url(application), {"body": body}, headers=HTMX)

    assert body.encode() in response.content
    assert not Note.objects.exists()


def test_a_note_cannot_inject_html(as_recruiter, recruiter, application):
    application.add_note(recruiter, "<script>alert(1)</script>")

    response = as_recruiter.get(detail_url(application))

    assert b"<script>alert(1)" not in response.content


def test_those_who_cannot_recruit_cannot_add_notes(
    client, customer, staff_user, application
):
    assert client.post(note_url(application), {"body": "Hi"}).status_code == (
        HTTPStatus.FOUND
    )
    for user in (customer, staff_user):
        client.force_login(user)
        response = client.post(note_url(application), {"body": "Hi"})
        assert response.status_code == HTTPStatus.FORBIDDEN
    assert not Note.objects.exists()


def test_those_who_cannot_recruit_cannot_read_notes(
    client, customer, staff_user, recruiter, application
):
    application.add_note(recruiter, "Candid thought.")
    for user in (customer, staff_user):
        client.force_login(user)
        assert client.get(detail_url(application)).status_code == HTTPStatus.FORBIDDEN


def test_notes_never_reach_the_applicant(client, customer, recruiter, application):
    application.add_note(recruiter, "Candid thought.")
    client.force_login(customer)

    for url in (
        reverse("careers:applications"),
        application.job.get_absolute_url(),
    ):
        assert b"Candid thought." not in client.get(url).content


def test_a_recruiter_cannot_note_their_own_application(
    as_recruiter, make_application, make_job, recruiter
):
    application = make_application(make_job(), recruiter)

    response = as_recruiter.post(note_url(application), {"body": "Great hire."})

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not Note.objects.exists()


def test_notes_cannot_be_edited_or_deleted_by_any_path(as_recruiter, application):
    response = as_recruiter.get(note_url(application))

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert Note not in admin.site._registry
