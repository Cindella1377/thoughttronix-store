"""Applying with a private résumé — phase 2 of the careers plan."""

import datetime
from http import HTTPStatus
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse

from .forms import MAX_RESUME_BYTES
from .models import Application, Job, Stage, StageChange
from .services import ApplicationError, submit_application


@pytest.fixture
def signed_in(client, customer):
    client.force_login(customer)
    return client


def apply_url(job):
    return reverse("careers:apply", args=[job.slug])


def resume_url(application):
    return reverse("careers:resume", args=[application.pk])


def stored_files():
    return [p for p in Path(settings.PRIVATE_MEDIA_ROOT).rglob("*") if p.is_file()]


def test_migrations_create_the_default_stages(db):
    stages = Stage.objects.values_list("name", "kind")

    assert list(stages) == [
        ("Applied", Stage.Kind.ENTRY),
        ("Screening", Stage.Kind.IN_PROGRESS),
        ("Interview", Stage.Kind.IN_PROGRESS),
        ("Offer", Stage.Kind.IN_PROGRESS),
        ("Hired", Stage.Kind.HIRED),
        ("Rejected", Stage.Kind.REJECTED),
        ("Withdrawn", Stage.Kind.WITHDRAWN),
    ]


def test_an_application_starts_in_the_entry_stage(customer, make_job, resume, now):
    job = make_job()

    application = submit_application(job, customer, resume, "Hello.", now=now)

    assert application.stage.kind == Stage.Kind.ENTRY
    assert application.cover_letter == "Hello."
    assert application.created_at == now
    change = StageChange.objects.get()
    assert change.application == application
    assert change.from_stage is None
    assert change.to_stage == application.stage
    assert change.changed_by == customer
    assert change.created_at == now


def test_a_signed_in_user_applies(signed_in, customer, make_job, resume):
    job = make_job()

    response = signed_in.post(
        apply_url(job), {"resume": resume, "cover_letter": "Pick me."}
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("careers:applications")
    application = Application.objects.get()
    assert (application.job, application.user) == (job, customer)
    assert application.cover_letter == "Pick me."


def test_the_cover_letter_is_optional(signed_in, make_job, resume):
    signed_in.post(apply_url(make_job()), {"resume": resume})

    assert Application.objects.get().cover_letter == ""


def test_a_visitor_must_sign_in_to_apply(client, make_job, resume):
    job = make_job()

    response = client.post(apply_url(job), {"resume": resume})

    assert reverse("accounts:login") in response.url
    assert not Application.objects.exists()


def test_visiting_the_apply_url_returns_to_the_job(signed_in, make_job):
    job = make_job()

    response = signed_in.get(apply_url(job))

    assert response.url == job.get_absolute_url()


def test_a_closed_job_refuses_applications(signed_in, make_job, resume):
    job = make_job(status=Job.Status.CLOSED)

    response = signed_in.post(apply_url(job), {"resume": resume})

    assert response.url == job.get_absolute_url()
    assert not Application.objects.exists()
    assert not stored_files()


def test_a_draft_job_cannot_be_applied_to(signed_in, make_job, resume):
    job = make_job(status=Job.Status.DRAFT)

    response = signed_in.post(apply_url(job), {"resume": resume})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_the_form_refuses_a_second_application(
    signed_in, make_application, make_job, customer, resume
):
    job = make_job()
    make_application(job, customer)

    response = signed_in.post(apply_url(job), {"resume": resume})

    assert response.status_code == HTTPStatus.OK
    assert b"already applied" in response.content
    assert Application.objects.count() == 1


def test_a_double_submit_keeps_one_application_and_one_file(
    customer, make_job, resume, pdf_bytes
):
    job = make_job()
    submit_application(job, customer, resume)

    with pytest.raises(ApplicationError, match="already applied"):
        submit_application(job, customer, SimpleUploadedFile("again.pdf", pdf_bytes))

    assert Application.objects.count() == 1
    assert len(stored_files()) == 1


def test_the_database_allows_one_application_per_job(
    make_application, make_job, customer
):
    application = make_application(make_job(), customer)

    with pytest.raises(IntegrityError), transaction.atomic():
        Application.objects.create(
            job=application.job, user=customer, stage=application.stage
        )


def test_different_people_and_jobs_do_not_conflict(
    make_application, make_job, customer, staff_user
):
    job = make_job()
    other_job = make_job(slug="other")

    make_application(job, customer)
    make_application(job, staff_user)
    make_application(other_job, customer)

    assert Application.objects.count() == 3


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("resume.pdf", b"not a pdf at all", b"not a PDF"),
        ("resume.exe", b"%PDF-1.4 hidden", b"PDF"),
    ],
)
def test_a_bad_file_is_refused_and_the_letter_survives(
    signed_in, make_job, name, content, message
):
    response = signed_in.post(
        apply_url(make_job()),
        {
            "resume": SimpleUploadedFile(name, content),
            "cover_letter": "Words I wrote.",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert message in response.content
    assert b"Words I wrote." in response.content
    assert not Application.objects.exists()


def test_a_missing_resume_is_refused(signed_in, make_job):
    response = signed_in.post(apply_url(make_job()), {"cover_letter": "Words I wrote."})

    assert response.status_code == HTTPStatus.OK
    assert b"Words I wrote." in response.content
    assert not Application.objects.exists()


def test_a_large_resume_is_refused(signed_in, make_job):
    too_big = b"%PDF-" + b"0" * MAX_RESUME_BYTES

    response = signed_in.post(
        apply_url(make_job()), {"resume": SimpleUploadedFile("cv.pdf", too_big)}
    )

    assert b"5 MB" in response.content
    assert not Application.objects.exists()


def test_a_resume_at_the_limit_is_accepted(signed_in, make_job):
    just_fits = b"%PDF-" + b"0" * (MAX_RESUME_BYTES - 5)

    signed_in.post(
        apply_url(make_job()), {"resume": SimpleUploadedFile("cv.pdf", just_fits)}
    )

    assert Application.objects.count() == 1


def test_the_stored_file_is_private(make_application, make_job, customer):
    application = make_application(make_job(), customer)

    path = Path(application.resume.path)
    assert path.is_relative_to(settings.PRIVATE_MEDIA_ROOT)
    assert not path.is_relative_to(settings.MEDIA_ROOT)
    with pytest.raises(ValueError, match="no public URL"):
        _ = application.resume.url


def test_the_stored_name_is_random(signed_in, make_job, pdf_bytes):
    signed_in.post(
        apply_url(make_job()),
        {"resume": SimpleUploadedFile("my-home-address.pdf", pdf_bytes)},
    )

    assert "my-home-address" not in Application.objects.get().resume.name


def test_the_owner_downloads_their_resume(
    signed_in, make_application, make_job, customer, pdf_bytes
):
    application = make_application(make_job(), customer)

    response = signed_in.get(resume_url(application))

    assert response.status_code == HTTPStatus.OK
    assert b"".join(response.streaming_content) == pdf_bytes
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].startswith("attachment")
    assert response["X-Content-Type-Options"] == "nosniff"


def test_a_recruiter_downloads_a_resume(
    client, recruiter, make_application, make_job, customer
):
    application = make_application(make_job(), customer)
    client.force_login(recruiter)

    assert client.get(resume_url(application)).status_code == HTTPStatus.OK


def test_a_recruiter_who_applied_is_treated_as_the_owner(
    client, recruiter, make_application, make_job
):
    application = make_application(make_job(), recruiter)
    client.force_login(recruiter)

    assert client.get(resume_url(application)).status_code == HTTPStatus.OK


def test_nobody_else_can_download_a_resume(
    client, make_application, make_job, customer, staff_user, django_user_model
):
    application = make_application(make_job(), customer)
    other = django_user_model.objects.create_user(
        username="other", email="other@example.com", password="other123"
    )

    assert client.get(resume_url(application)).status_code == HTTPStatus.NOT_FOUND
    for user in (other, staff_user):
        client.force_login(user)
        assert client.get(resume_url(application)).status_code == HTTPStatus.NOT_FOUND


def test_a_job_with_applications_cannot_be_deleted(
    make_application, make_job, customer
):
    job = make_job()
    make_application(job, customer)

    with pytest.raises(ProtectedError):
        job.delete()


def test_my_applications_lists_only_mine_newest_first(
    signed_in, make_application, make_job, customer, staff_user, now
):
    older = make_application(make_job(slug="older"), customer)
    newer = make_application(make_job(slug="newer"), customer)
    Application.objects.filter(pk=older.pk).update(created_at=now)
    Application.objects.filter(pk=newer.pk).update(
        created_at=now + datetime.timedelta(days=1)
    )
    make_application(make_job(slug="theirs"), staff_user)

    response = signed_in.get(reverse("careers:applications"))

    assert list(response.context["applications"]) == [newer, older]


def test_my_applications_shows_a_status_not_a_stage_name(
    signed_in, make_application, make_job, customer
):
    application = make_application(make_job(), customer)
    Stage.objects.filter(pk=application.stage_id).update(name="Maybe pile")

    response = signed_in.get(reverse("careers:applications"))

    assert b"Received" in response.content
    assert b"Maybe pile" not in response.content


def test_my_applications_requires_sign_in(client, db):
    response = client.get(reverse("careers:applications"))

    assert reverse("accounts:login") in response.url


def test_my_applications_has_an_empty_state(signed_in):
    response = signed_in.get(reverse("careers:applications"))

    assert b"No applications yet" in response.content
    assert reverse("careers:jobs").encode() in response.content


def test_the_job_page_offers_the_form_when_signed_in(signed_in, make_job):
    job = make_job()

    response = signed_in.get(job.get_absolute_url())

    assert b'name="resume"' in response.content
    assert b'enctype="multipart/form-data"' in response.content


def test_the_job_page_links_to_my_applications_after_applying(
    signed_in, make_application, make_job, customer
):
    job = make_job()
    make_application(job, customer)

    response = signed_in.get(job.get_absolute_url())

    assert b'name="resume"' not in response.content
    assert reverse("careers:applications").encode() in response.content


def test_a_closed_job_still_links_an_applicant_to_their_application(
    signed_in, make_application, make_job, customer
):
    job = make_job()
    make_application(job, customer)
    Job.objects.filter(pk=job.pk).update(status=Job.Status.CLOSED)

    response = signed_in.get(job.get_absolute_url())

    assert reverse("careers:applications").encode() in response.content


def test_the_careers_address_is_shown(signed_in, make_job, settings):
    settings.CAREERS_EMAIL = "hiring@example.com"
    job = make_job()

    assert b"hiring@example.com" in signed_in.get(job.get_absolute_url()).content
    assert (
        b"hiring@example.com" in signed_in.get(reverse("careers:applications")).content
    )


def test_the_account_page_links_to_my_applications(signed_in):
    response = signed_in.get(reverse("accounts:account"))

    assert reverse("careers:applications").encode() in response.content
