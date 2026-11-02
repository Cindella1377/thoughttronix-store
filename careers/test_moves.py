"""Reviewing and moving applications — phase 3 of the careers plan."""

import datetime
from http import HTTPStatus

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Application, Job, Stage, StageChange
from .services import ApplicationError, move_application


@pytest.fixture
def as_recruiter(client, recruiter):
    client.force_login(recruiter)
    return client


@pytest.fixture
def application(make_application, make_job, customer):
    return make_application(make_job(), customer)


def stage(kind):
    return Stage.objects.filter(kind=kind).first()


def table_url(job):
    return reverse("careers:manage_applications", args=[job.pk])


def detail_url(application):
    return reverse("careers:application", args=[application.pk])


def move_url(application):
    return reverse("careers:move", args=[application.pk])


def staff_urls(application):
    return [detail_url(application), table_url(application.job)]


def test_only_those_who_can_recruit_reach_the_screens(
    client, customer, staff_user, application
):
    for url in staff_urls(application):
        assert client.get(url).status_code == HTTPStatus.FOUND
    for user in (customer, staff_user):
        client.force_login(user)
        for url in staff_urls(application):
            assert client.get(url).status_code == HTTPStatus.FORBIDDEN
        response = client.post(
            move_url(application), {"stage": stage(Stage.Kind.HIRED).pk}
        )
        assert response.status_code == HTTPStatus.FORBIDDEN


def test_the_job_list_links_to_the_applications(as_recruiter, application):
    response = as_recruiter.get(reverse("careers:manage_jobs"))

    assert table_url(application.job).encode() in response.content


def test_the_table_lists_a_jobs_applications(
    as_recruiter, make_application, make_job, application, staff_user
):
    make_application(make_job(slug="other"), staff_user)

    response = as_recruiter.get(table_url(application.job))

    assert list(response.context["applications"]) == [application]
    assert application.user.email.encode() in response.content


def test_the_table_filters_by_stage(
    as_recruiter, recruiter, make_application, application, staff_user
):
    screening = Stage.objects.get(name="Screening")
    moved = make_application(application.job, staff_user)
    move_application(moved, screening, recruiter)
    url = table_url(application.job)

    response = as_recruiter.get(url, {"stage": screening.pk})

    assert list(response.context["applications"]) == [moved]


@pytest.mark.parametrize("value", ["", "banana", "999999999"])
def test_a_bad_filter_does_not_break_the_table(as_recruiter, application, value):
    response = as_recruiter.get(table_url(application.job), {"stage": value})

    assert response.status_code == HTTPStatus.OK


def test_the_table_has_empty_states(as_recruiter, make_job, application):
    empty = as_recruiter.get(table_url(make_job(slug="empty")))
    assert b"No applications yet" in empty.content

    filtered = as_recruiter.get(
        table_url(application.job), {"stage": stage(Stage.Kind.HIRED).pk}
    )
    assert b"Nobody in this stage" in filtered.content


def test_the_detail_page_shows_the_application(
    as_recruiter, make_application, make_job, customer
):
    application = make_application(make_job(), customer, cover_letter="Hire me.")

    response = as_recruiter.get(detail_url(application))

    assert b"Hire me." in response.content
    assert reverse("careers:resume", args=[application.pk]).encode() in response.content
    assert b"Applied" in response.content


def test_the_history_keeps_a_retired_stages_name(as_recruiter, recruiter, application):
    screening = Stage.objects.get(name="Screening")
    move_application(application, screening, recruiter)
    application.refresh_from_db()
    move_application(application, Stage.objects.get(name="Interview"), recruiter)
    Stage.objects.filter(pk=screening.pk).update(is_active=False)

    response = as_recruiter.get(detail_url(application))

    assert b"Screening" in response.content


def test_a_cover_letter_cannot_inject_html(
    as_recruiter, make_application, make_job, customer
):
    application = make_application(
        make_job(), customer, cover_letter="<script>alert(1)</script>"
    )

    response = as_recruiter.get(detail_url(application))

    assert b"<script>alert(1)" not in response.content


def test_a_move_changes_the_stage_and_writes_the_log(recruiter, application, now):
    interview = Stage.objects.get(name="Interview")
    entry = application.stage

    moved = move_application(application, interview, recruiter, note="Sharp.", now=now)

    assert moved.stage == interview
    assert moved.closed_at is None
    change = application.stage_changes.get(to_stage=interview)
    assert (change.from_stage, change.to_stage) == (entry, interview)
    assert change.changed_by == recruiter
    assert change.note == "Sharp."
    assert change.created_at == now


def test_moves_can_go_backward_and_skip_ahead(recruiter, application):
    offer = Stage.objects.get(name="Offer")
    screening = Stage.objects.get(name="Screening")

    moved = move_application(application, offer, recruiter)
    moved = move_application(moved, screening, recruiter)

    assert moved.stage == screening


@pytest.mark.parametrize("kind", [Stage.Kind.HIRED, Stage.Kind.REJECTED])
def test_a_final_stage_closes_the_application(recruiter, application, now, kind):
    moved = move_application(application, stage(kind), recruiter, now=now)

    assert moved.closed_at == now
    assert not moved.is_open


def test_a_closed_application_cannot_move(recruiter, application):
    closed = move_application(application, stage(Stage.Kind.REJECTED), recruiter)
    before = StageChange.objects.count()

    with pytest.raises(ApplicationError, match="closed"):
        move_application(closed, Stage.objects.get(name="Offer"), recruiter)

    assert StageChange.objects.count() == before


def test_a_stale_copy_cannot_reopen_by_moving(recruiter, application):
    """Two recruiters on one page: the rule reads the saved stage."""
    move_application(application, stage(Stage.Kind.REJECTED), recruiter)

    with pytest.raises(ApplicationError, match="closed"):
        move_application(application, Stage.objects.get(name="Offer"), recruiter)


def test_a_retired_stage_is_refused(recruiter, application):
    offer = Stage.objects.get(name="Offer")
    Stage.objects.filter(pk=offer.pk).update(is_active=False)
    offer.refresh_from_db()

    with pytest.raises(ApplicationError, match="retired"):
        move_application(application, offer, recruiter)

    assert application.stage_changes.count() == 1


def test_withdrawn_is_refused(recruiter, application):
    with pytest.raises(ApplicationError, match="withdraw"):
        move_application(application, stage(Stage.Kind.WITHDRAWN), recruiter)

    assert application.stage_changes.count() == 1


def test_moving_to_the_same_stage_is_refused(recruiter, application):
    with pytest.raises(ApplicationError, match="already"):
        move_application(application, application.stage, recruiter)


def test_the_service_refuses_those_who_cannot_recruit(staff_user, application):
    with pytest.raises(ApplicationError, match="hiring team"):
        move_application(application, stage(Stage.Kind.HIRED), staff_user)


def test_a_recruiter_cannot_move_their_own_application(
    recruiter, make_application, make_job
):
    application = make_application(make_job(), recruiter)

    with pytest.raises(ApplicationError, match="your own"):
        move_application(application, stage(Stage.Kind.HIRED), recruiter)


def test_hiring_changes_nothing_else(
    recruiter, make_application, application, staff_user
):
    other = make_application(application.job, staff_user)
    entry = other.stage

    move_application(application, stage(Stage.Kind.HIRED), recruiter)

    application.job.refresh_from_db()
    application.user.refresh_from_db()
    other.refresh_from_db()
    assert application.job.status == Job.Status.OPEN
    assert other.stage == entry
    assert not application.user.is_staff
    assert not application.user.job_title


def test_moving_from_the_page_returns_to_the_detail(as_recruiter, application):
    interview = Stage.objects.get(name="Interview")

    response = as_recruiter.post(
        move_url(application), {"stage": interview.pk, "note": "Sharp."}
    )

    assert response.url == detail_url(application)
    application.refresh_from_db()
    assert application.stage == interview
    assert application.stage_changes.last().note == "Sharp."


def test_moving_from_the_table_returns_to_the_filtered_table(as_recruiter, application):
    back = f"{table_url(application.job)}?stage={application.stage_id}"

    response = as_recruiter.post(
        move_url(application),
        {"stage": Stage.objects.get(name="Offer").pk, "next": back},
    )

    assert response.url == back


def test_next_cannot_leave_the_site(as_recruiter, application):
    response = as_recruiter.post(
        move_url(application),
        {
            "stage": Stage.objects.get(name="Offer").pk,
            "next": "https://evil.example/",
        },
    )

    assert response.url == detail_url(application)


def test_a_refused_move_explains_itself(as_recruiter, recruiter, application):
    move_application(application, stage(Stage.Kind.REJECTED), recruiter)

    response = as_recruiter.post(
        move_url(application),
        {"stage": Stage.objects.get(name="Offer").pk},
        follow=True,
    )

    assert b"closed" in response.content
    application.refresh_from_db()
    assert application.stage.kind == Stage.Kind.REJECTED


@pytest.mark.parametrize("name", ["Withdrawn", "retired"])
def test_the_form_refuses_a_stage_it_does_not_offer(as_recruiter, application, name):
    target = (
        Stage.objects.create(name=name, kind=Stage.Kind.IN_PROGRESS, is_active=False)
        if name == "retired"
        else Stage.objects.get(name=name)
    )

    response = as_recruiter.post(move_url(application), {"stage": target.pk})

    assert response.url == detail_url(application)
    assert application.stage_changes.count() == 1


def test_a_closed_application_offers_no_move(as_recruiter, recruiter, application):
    move_application(application, stage(Stage.Kind.HIRED), recruiter)

    detail = as_recruiter.get(detail_url(application))
    table = as_recruiter.get(table_url(application.job))

    assert move_url(application).encode() not in detail.content
    assert move_url(application).encode() not in table.content


def test_retired_and_withdrawn_stages_are_not_offered(as_recruiter, application):
    Stage.objects.filter(name="Offer").update(is_active=False)

    response = as_recruiter.get(detail_url(application))

    offered = list(response.context["stages"])
    assert Stage.objects.get(name="Offer") not in offered
    assert stage(Stage.Kind.WITHDRAWN) not in offered


@pytest.fixture
def recruiters_own(make_application, make_job, recruiter):
    return make_application(make_job(), recruiter)


def test_a_recruiters_own_application_is_a_404(as_recruiter, recruiters_own):
    response = as_recruiter.get(detail_url(recruiters_own))
    assert response.status_code == HTTPStatus.NOT_FOUND

    response = as_recruiter.post(
        move_url(recruiters_own), {"stage": stage(Stage.Kind.HIRED).pk}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_a_recruiters_own_application_is_not_listed(as_recruiter, recruiters_own):
    response = as_recruiter.get(table_url(recruiters_own.job))

    assert list(response.context["applications"]) == []


def test_a_superuser_is_held_to_the_same_rule(client, make_application, make_job):
    superuser = get_user_model().objects.create_superuser(
        username="admin", email="admin@example.com", password="admin123"
    )
    application = make_application(make_job(), superuser)
    client.force_login(superuser)

    assert client.get(detail_url(application)).status_code == HTTPStatus.NOT_FOUND


def test_an_anonymized_record_shows_a_former_applicant(
    as_recruiter, make_application, make_job, customer
):
    application = make_application(make_job(), customer)
    Application.objects.filter(pk=application.pk).update(
        user=None, anonymized_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    )

    response = as_recruiter.get(detail_url(application))

    assert b"Former applicant" in response.content


def test_applications_are_read_only_in_django_admin(rf, recruiter):
    model_admin = admin.site._registry[Application]
    request = rf.get("/")
    request.user = recruiter

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)
