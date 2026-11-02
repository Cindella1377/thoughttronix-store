"""Posting and browsing jobs — phase 1 of the careers plan."""

import datetime
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from .forms import JobForm
from .models import Job

JOB_DATA = {
    "title": "Thought Curator",
    "slug": "thought-curator",
    "department": "Curation",
    "location": "Remote",
    "employment_type": Job.EmploymentType.FULL_TIME,
    "description": "Curate thoughts.",
}


@pytest.fixture
def as_recruiter(client, recruiter):
    client.force_login(recruiter)
    return client


def manage_urls(job):
    return [
        reverse("careers:manage_jobs"),
        reverse("careers:job_create"),
        reverse("careers:job_edit", args=[job.pk]),
    ]


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({}, False),
        ({"is_staff": True}, False),
        # The flag means nothing without staff access.
        ({"is_recruiter": True}, False),
        ({"is_staff": True, "is_recruiter": True}, True),
        ({"is_superuser": True}, True),
    ],
)
def test_can_recruit(fields, expected):
    assert get_user_model()(**fields).can_recruit is expected


def test_visitors_are_sent_to_sign_in(client, make_job):
    for url in manage_urls(make_job()):
        response = client.get(url)
        assert response.status_code == HTTPStatus.FOUND
        assert reverse("accounts:login") in response.url


def test_customers_and_plain_staff_are_refused(client, customer, staff_user, make_job):
    job = make_job()
    for user in (customer, staff_user):
        client.force_login(user)
        for url in manage_urls(job):
            assert client.get(url).status_code == HTTPStatus.FORBIDDEN


def test_recruiters_and_superusers_are_admitted(client, recruiter, make_job):
    job = make_job()
    superuser = get_user_model().objects.create_superuser(
        username="admin", email="admin@example.com", password="admin123"
    )
    for user in (recruiter, superuser):
        client.force_login(user)
        for url in manage_urls(job):
            assert client.get(url).status_code == HTTPStatus.OK


def test_the_tab_shows_only_to_those_who_can_recruit(client, staff_user, recruiter):
    # Any back-office page will do; this one admits plain staff too.
    url = reverse("products:manage_products")
    tab = reverse("careers:manage_jobs").encode()

    client.force_login(staff_user)
    assert tab not in client.get(url).content

    client.force_login(recruiter)
    assert tab in client.get(url).content


def test_a_new_job_is_a_draft(as_recruiter):
    response = as_recruiter.post(reverse("careers:job_create"), JOB_DATA)

    assert response.status_code == HTTPStatus.FOUND
    job = Job.objects.get()
    assert job.status == Job.Status.DRAFT
    assert job.published_at is None


def test_a_new_job_cannot_skip_the_draft(as_recruiter):
    as_recruiter.post(
        reverse("careers:job_create"), {**JOB_DATA, "status": Job.Status.OPEN}
    )

    assert Job.objects.get().status == Job.Status.DRAFT


def test_a_recruiter_edits_a_job(as_recruiter, make_job):
    job = make_job(status=Job.Status.DRAFT)

    as_recruiter.post(
        reverse("careers:job_edit", args=[job.pk]),
        {**JOB_DATA, "title": "Senior Curator", "status": Job.Status.DRAFT},
    )

    job.refresh_from_db()
    assert job.title == "Senior Curator"
    assert job.status == Job.Status.DRAFT


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (Job.Status.DRAFT, Job.Status.OPEN),
        (Job.Status.OPEN, Job.Status.CLOSED),
        (Job.Status.CLOSED, Job.Status.OPEN),
    ],
)
def test_allowed_status_moves(as_recruiter, make_job, start, end):
    job = make_job(status=start)

    response = as_recruiter.post(
        reverse("careers:job_edit", args=[job.pk]), {**JOB_DATA, "status": end}
    )

    assert response.status_code == HTTPStatus.FOUND
    job.refresh_from_db()
    assert job.status == end


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (Job.Status.DRAFT, Job.Status.CLOSED),
        (Job.Status.OPEN, Job.Status.DRAFT),
        (Job.Status.CLOSED, Job.Status.DRAFT),
    ],
)
def test_other_status_moves_are_refused(as_recruiter, make_job, start, end):
    job = make_job(status=start)

    response = as_recruiter.post(
        reverse("careers:job_edit", args=[job.pk]), {**JOB_DATA, "status": end}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["status"]
    job.refresh_from_db()
    assert job.status == start


def test_change_status_refuses_a_disallowed_move(make_job):
    job = make_job(status=Job.Status.DRAFT)

    with pytest.raises(ValueError, match="cannot become"):
        job.change_status(Job.Status.CLOSED)


def test_the_first_publish_is_recorded_and_kept(make_job, now):
    job = make_job(status=Job.Status.DRAFT)

    job.change_status(Job.Status.OPEN, now=now)
    assert job.published_at == now

    job.change_status(Job.Status.CLOSED)
    job.change_status(Job.Status.OPEN, now=now + datetime.timedelta(days=1))
    assert job.published_at == now


def test_applications_cannot_be_a_job_slug(db):
    form = JobForm({**JOB_DATA, "slug": "applications"})

    assert not form.is_valid()
    assert "slug" in form.errors


def test_the_public_list_shows_open_jobs_newest_first(client, make_job, now):
    older = make_job(title="Older", slug="older", published_at=now)
    newer = make_job(
        title="Newer",
        slug="newer",
        published_at=now + datetime.timedelta(days=1),
    )
    make_job(title="Secret", slug="secret", status=Job.Status.DRAFT)
    make_job(title="Filled", slug="filled", status=Job.Status.CLOSED)

    response = client.get(reverse("careers:jobs"))

    assert list(response.context["jobs"]) == [newer, older]
    assert b"Secret" not in response.content
    assert b"Filled" not in response.content


def test_the_public_list_shows_the_jobs_facts(client, make_job):
    make_job(salary_range="$90k-$110k")

    content = client.get(reverse("careers:jobs")).content.decode()

    for fact in ("Curation", "Remote", "Full-time", "$90k-$110k"):
        assert fact in content


def test_salary_is_left_out_when_not_given(client, make_job):
    job = make_job(salary_range="")

    response = client.get(job.get_absolute_url())

    assert b"Salary range" not in response.content


def test_an_open_job_asks_visitors_to_sign_in(client, make_job):
    job = make_job()

    content = client.get(job.get_absolute_url()).content.decode()

    assert job.description in content
    assert f"{reverse('accounts:login')}?next={job.get_absolute_url()}" in content


def test_a_closed_job_says_so(client, make_job):
    job = make_job(status=Job.Status.CLOSED)

    response = client.get(job.get_absolute_url())

    assert response.status_code == HTTPStatus.OK
    assert b"no longer accepting applications" in response.content
    assert b"Sign in to apply" not in response.content


def test_a_draft_does_not_exist_publicly(client, recruiter, make_job):
    job = make_job(status=Job.Status.DRAFT)

    assert client.get(job.get_absolute_url()).status_code == HTTPStatus.NOT_FOUND
    client.force_login(recruiter)
    assert client.get(job.get_absolute_url()).status_code == HTTPStatus.NOT_FOUND


def test_a_description_cannot_inject_html(client, make_job):
    job = make_job(description="<script>alert(1)</script>")

    response = client.get(job.get_absolute_url())

    assert b"<script>alert(1)" not in response.content


def test_every_page_links_to_careers(client, db):
    assert reverse("careers:jobs").encode() in client.get("/").content


def test_the_public_list_has_an_empty_state(client, db):
    response = client.get(reverse("careers:jobs"))

    assert b"No open roles" in response.content


def test_the_back_office_list_has_an_empty_state(as_recruiter):
    response = as_recruiter.get(reverse("careers:manage_jobs"))

    assert b"No jobs yet" in response.content


def test_the_back_office_list_shows_every_status(as_recruiter, make_job):
    for status in Job.Status.values:
        make_job(title=f"Job {status}", slug=status, status=status)

    response = as_recruiter.get(reverse("careers:manage_jobs"))

    assert len(response.context["jobs"]) == len(Job.Status.values)
