"""Data retention — phase 8 of the careers plan."""

import datetime
from http import HTTPStatus
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from .models import Application, Note, Stage, StageChange
from .services import (
    RETENTION_DAYS,
    ApplicationError,
    anonymize_application,
    move_application,
    purge_applications,
    withdraw_application,
)


@pytest.fixture
def application(make_application, make_job, customer):
    return make_application(make_job(), customer, cover_letter="Private words.")


@pytest.fixture
def rejected(application, recruiter, now):
    """Rejected at ``now``, with a move note and a standalone note."""
    closed = move_application(
        application,
        Stage.objects.get(kind=Stage.Kind.REJECTED),
        recruiter,
        note="Candid move note.",
        now=now,
    )
    closed.add_note(recruiter, "Candid note.")
    return closed


def test_anonymizing_removes_the_personal_data(rejected, now):
    path = Path(rejected.resume.path)
    assert path.exists()

    done = anonymize_application(rejected, now=now)

    assert not path.exists()
    assert not done.resume
    assert done.user is None
    assert done.cover_letter == ""
    assert done.anonymized_at == now
    assert not Note.objects.exists()
    assert not StageChange.objects.exclude(note="").exists()


def test_the_saved_row_is_clean(rejected):
    anonymize_application(rejected)

    row = Application.objects.get(pk=rejected.pk)
    assert row.user_id is None
    assert row.resume.name == ""


def test_the_history_survives_without_the_applicant(application, customer, recruiter):
    withdrawn = withdraw_application(application, customer)
    before = withdrawn.stage_changes.count()

    anonymize_application(withdrawn)

    assert withdrawn.stage_changes.count() == before
    assert not withdrawn.stage_changes.filter(changed_by=customer).exists()


def test_staff_actors_stay_on_the_log(rejected, recruiter):
    anonymize_application(rejected)

    assert rejected.stage_changes.filter(changed_by=recruiter).exists()


def test_anonymizing_twice_is_harmless(rejected, now):
    first = anonymize_application(rejected, now=now)
    later = now + datetime.timedelta(days=1)

    second = anonymize_application(first, now=later)

    assert second.anonymized_at == now


def test_an_open_application_closes_when_anonymized(application, now):
    done = anonymize_application(application, now=now)

    assert done.closed_at == now
    assert not done.is_open


def test_a_closed_date_is_kept(rejected, now):
    later = now + datetime.timedelta(days=1)

    done = anonymize_application(rejected, now=later)

    assert done.closed_at == now


def test_an_anonymized_application_cannot_be_moved(application, recruiter):
    done = anonymize_application(application)

    with pytest.raises(ApplicationError, match="closed"):
        move_application(done, Stage.objects.get(name="Offer"), recruiter)


def test_purge_uses_the_retention_boundary(rejected, now):
    edge = now + datetime.timedelta(days=RETENTION_DAYS)
    almost = edge - datetime.timedelta(seconds=1)

    assert purge_applications(now=almost) == 0
    rejected.refresh_from_db()
    assert rejected.anonymized_at is None

    assert purge_applications(now=edge) == 1
    rejected.refresh_from_db()
    assert rejected.anonymized_at == edge


def test_purge_leaves_open_applications_alone(application, now):
    far_future = now + datetime.timedelta(days=RETENTION_DAYS * 10)

    assert purge_applications(now=far_future) == 0
    application.refresh_from_db()
    assert application.user is not None


def test_purge_skips_what_it_has_already_done(rejected, now):
    edge = now + datetime.timedelta(days=RETENTION_DAYS)
    purge_applications(now=edge)

    assert purge_applications(now=edge) == 0


def test_the_command_reports_its_count(rejected):
    Application.objects.filter(pk=rejected.pk).update(
        closed_at=timezone.now() - datetime.timedelta(days=RETENTION_DAYS + 1)
    )
    out = StringIO()

    call_command("purge_applications", stdout=out)

    assert "Anonymized 1 application" in out.getvalue()
    rejected.refresh_from_db()
    assert rejected.user is None


def test_deleting_a_user_anonymizes_their_applications(rejected, customer):
    path = Path(rejected.resume.path)

    customer.delete()

    rejected.refresh_from_db()
    assert rejected.anonymized_at is not None
    assert rejected.user is None
    assert not path.exists()


def test_bulk_deleting_users_anonymizes_too(rejected, customer):
    get_user_model().objects.filter(pk=customer.pk).delete()

    rejected.refresh_from_db()
    assert rejected.anonymized_at is not None
    assert not Note.objects.exists()


def test_deleting_a_recruiter_keeps_the_application(rejected, recruiter):
    recruiter.delete()

    rejected.refresh_from_db()
    assert rejected.anonymized_at is None
    assert rejected.user is not None


def test_staff_screens_handle_an_anonymized_record(client, recruiter, rejected):
    done = anonymize_application(rejected)
    client.force_login(recruiter)

    detail = client.get(reverse("careers:application", args=[done.pk]))
    table = client.get(reverse("careers:manage_applications", args=[done.job_id]))

    assert detail.status_code == HTTPStatus.OK
    assert b"Former applicant" in detail.content
    assert b"Former applicant" in table.content
    assert b"Private words." not in detail.content
    assert b"Candid" not in detail.content
    assert reverse("careers:resume", args=[done.pk]).encode() not in detail.content
    assert reverse("careers:reopen", args=[done.pk]).encode() not in detail.content


def test_an_anonymized_resume_is_a_404(client, recruiter, rejected):
    done = anonymize_application(rejected)
    client.force_login(recruiter)

    response = client.get(reverse("careers:resume", args=[done.pk]))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_notes_cannot_be_added_to_an_anonymized_record(client, recruiter, rejected):
    done = anonymize_application(rejected)
    client.force_login(recruiter)
    url = reverse("careers:note", args=[done.pk])

    assert (
        url.encode()
        not in client.get(reverse("careers:application", args=[done.pk])).content
    )
    assert client.post(url, {"body": "Hi"}).status_code == HTTPStatus.NOT_FOUND
    assert not Note.objects.exists()


def test_an_anonymized_record_does_not_block_retiring_its_stage(application):
    offer = Stage.objects.get(name="Offer")
    Application.objects.filter(pk=application.pk).update(stage=offer)
    application.refresh_from_db()
    assert not offer.can_retire()

    anonymize_application(application)

    assert offer.can_retire()


def test_two_anonymized_records_do_not_conflict(
    make_application, make_job, customer, staff_user
):
    job = make_job()
    first = make_application(job, customer)
    second = make_application(job, staff_user)

    anonymize_application(first)
    anonymize_application(second)

    assert Application.objects.filter(job=job, user=None).count() == 2
