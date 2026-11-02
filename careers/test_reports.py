"""The hiring report — phase 10 of the careers plan."""

import datetime
from http import HTTPStatus

import pytest
from django.urls import reverse

from .models import Application, Stage
from .services import (
    anonymize_application,
    move_application,
    reopen_application,
    withdraw_application,
)

URL = "careers:reports"


@pytest.fixture
def as_recruiter(client, recruiter):
    client.force_login(recruiter)
    return client


@pytest.fixture
def job(make_job):
    return make_job()


@pytest.fixture
def make_user(django_user_model):
    def make(name):
        return django_user_model.objects.create_user(
            username=name, email=f"{name}@example.com", password="applicant123"
        )

    return make


@pytest.fixture
def application(make_application, job, customer):
    return make_application(job, customer)


def kind(value):
    return Stage.objects.get(kind=value)


def funnel_counts():
    return {row["label"]: row["count"] for row in Application.objects.funnel()}


def test_only_those_who_can_recruit_reach_the_report(client, customer, staff_user):
    url = reverse(URL)
    assert client.get(url).status_code == HTTPStatus.FOUND
    for user in (customer, staff_user):
        client.force_login(user)
        assert client.get(url).status_code == HTTPStatus.FORBIDDEN


def test_the_job_list_links_to_the_report(as_recruiter):
    response = as_recruiter.get(reverse("careers:manage_jobs"))

    assert reverse(URL).encode() in response.content


def test_hiring_data_stays_off_the_all_staff_dashboard(client, staff_user, application):
    client.force_login(staff_user)

    response = client.get(reverse("dashboard:index"))

    assert reverse(URL).encode() not in response.content
    assert b"days to hire" not in response.content


def test_the_funnel_counts_what_was_reached(
    recruiter, make_application, make_user, application, job
):
    second = make_application(job, make_user("second"))
    move_application(second, Stage.objects.get(name="Offer"), recruiter)

    counts = funnel_counts()

    assert counts["Entry"] == 2
    assert counts["In progress"] == 1
    assert counts["Hired"] == 0


def test_repeat_visits_count_once(recruiter, application):
    moved = move_application(application, Stage.objects.get(name="Offer"), recruiter)
    moved = move_application(moved, Stage.objects.get(name="Screening"), recruiter)

    assert funnel_counts()["In progress"] == 1


def test_the_funnel_counts_a_kind_left_behind(recruiter, application):
    closed = move_application(application, kind(Stage.Kind.REJECTED), recruiter)
    reopen_application(closed, Stage.objects.get(name="Offer"), "Why.", recruiter)

    assert funnel_counts()["Rejected"] == 1


def test_the_funnel_survives_renamed_and_retired_stages(recruiter, application):
    extra = Stage.objects.create(name="Take-home", kind=Stage.Kind.IN_PROGRESS)
    moved = move_application(application, extra, recruiter)
    moved = move_application(moved, Stage.objects.get(name="Offer"), recruiter)
    Stage.objects.filter(pk=extra.pk).update(is_active=False, name="Old")
    Stage.objects.filter(kind=Stage.Kind.ENTRY).update(name="Inbox")

    counts = funnel_counts()

    assert counts["In progress"] == 1
    assert counts["Entry"] == 1


def test_outcomes_separate_rejected_from_withdrawn(
    recruiter, customer, make_application, make_user, application, job
):
    withdraw_application(application, customer)
    move_application(
        make_application(job, make_user("second")),
        kind(Stage.Kind.REJECTED),
        recruiter,
    )
    move_application(
        make_application(job, make_user("third")),
        kind(Stage.Kind.REJECTED),
        recruiter,
    )

    outcomes = Application.objects.outcomes()

    assert outcomes == {"hired": 0, "rejected": 2, "withdrawn": 1}


def test_outcomes_follow_a_reopen(recruiter, application):
    closed = move_application(application, kind(Stage.Kind.REJECTED), recruiter)
    reopen_application(closed, Stage.objects.get(name="Offer"), "Why.", recruiter)

    assert Application.objects.outcomes()["rejected"] == 0


def test_average_days_to_hire(
    recruiter, make_application, make_user, application, job, now
):
    second = make_application(job, make_user("second"))
    Application.objects.update(created_at=now)
    application.refresh_from_db()
    second.refresh_from_db()
    hired = kind(Stage.Kind.HIRED)
    move_application(
        application, hired, recruiter, now=now + datetime.timedelta(days=10)
    )
    move_application(second, hired, recruiter, now=now + datetime.timedelta(days=20))

    assert Application.objects.average_days_to_hire() == 15


def test_days_to_hire_uses_the_latest_hire_after_a_reopen(recruiter, application, now):
    Application.objects.update(created_at=now)
    application.refresh_from_db()
    hired = kind(Stage.Kind.HIRED)
    closed = move_application(
        application, hired, recruiter, now=now + datetime.timedelta(days=2)
    )
    reopened = reopen_application(
        closed,
        Stage.objects.get(name="Offer"),
        "Why.",
        recruiter,
        now=now + datetime.timedelta(days=3),
    )
    move_application(reopened, hired, recruiter, now=now + datetime.timedelta(days=9))

    assert Application.objects.average_days_to_hire() == 9


def test_someone_no_longer_hired_does_not_count(recruiter, application):
    closed = move_application(application, kind(Stage.Kind.HIRED), recruiter)
    reopen_application(closed, Stage.objects.get(name="Offer"), "Why.", recruiter)

    assert Application.objects.average_days_to_hire() is None


def test_no_hires_gives_no_average(application):
    assert Application.objects.average_days_to_hire() is None


def test_anonymized_applications_are_counted(recruiter, application, now):
    Application.objects.update(created_at=now)
    application.refresh_from_db()
    closed = move_application(
        application,
        kind(Stage.Kind.HIRED),
        recruiter,
        now=now + datetime.timedelta(days=4),
    )
    anonymize_application(closed)

    assert funnel_counts()["Hired"] == 1
    assert Application.objects.outcomes()["hired"] == 1
    assert Application.objects.average_days_to_hire() == 4
    assert Application.objects.by_job()[0]["total"] == 1


def test_totals_per_job(
    recruiter, make_application, make_job, make_user, application, job
):
    other = make_job(title="Other", slug="other")
    make_application(other, make_user("second"))
    move_application(application, kind(Stage.Kind.HIRED), recruiter)

    rows = {row["job__title"]: row for row in Application.objects.by_job()}

    assert rows[job.title]["total"] == 1
    assert rows[job.title]["hired"] == 1
    assert rows[job.title]["open"] == 0
    assert rows["Other"]["open"] == 1


def test_the_viewers_own_application_is_left_out(
    as_recruiter, recruiter, make_application, job, application
):
    make_application(job, recruiter)

    response = as_recruiter.get(reverse(URL))

    assert response.context["jobs"][0]["total"] == 1
    entry = next(r for r in response.context["funnel"] if r["label"] == "Entry")
    assert entry["count"] == 1


def test_the_page_shows_no_names(as_recruiter, customer, application, recruiter):
    move_application(application, kind(Stage.Kind.HIRED), recruiter)

    response = as_recruiter.get(reverse(URL))

    assert b'href="/backoffice/careers/applications/' not in response.content
    assert customer.email.encode() not in response.content
    assert application.applicant_name.encode() not in response.content


def test_the_page_has_an_empty_state(as_recruiter):
    response = as_recruiter.get(reverse(URL))

    assert b"Nothing to report yet" in response.content


def test_the_query_count_does_not_grow_with_applications(
    as_recruiter,
    make_application,
    make_user,
    application,
    job,
    django_assert_max_num_queries,
):
    with django_assert_max_num_queries(12):
        as_recruiter.get(reverse(URL))

    for number in range(5):
        make_application(job, make_user(f"applicant{number}"))

    with django_assert_max_num_queries(12):
        as_recruiter.get(reverse(URL))
