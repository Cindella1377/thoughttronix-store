"""Withdrawing and reopening — phase 5 of the careers plan."""

from http import HTTPStatus

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from .models import Application, Job, Stage
from .services import (
    ApplicationError,
    move_application,
    reopen_application,
    withdraw_application,
)


@pytest.fixture
def application(make_application, make_job, customer):
    return make_application(make_job(), customer)


@pytest.fixture
def rejected(application, recruiter):
    return move_application(application, stage(Stage.Kind.REJECTED), recruiter)


@pytest.fixture
def interview(db):
    return Stage.objects.get(name="Interview")


def stage(kind):
    return Stage.objects.filter(kind=kind).first()


def withdraw_url(application):
    return reverse("careers:withdraw", args=[application.pk])


def reopen_url(application):
    return reverse("careers:reopen", args=[application.pk])


def detail_url(application):
    return reverse("careers:application", args=[application.pk])


def test_the_applicant_withdraws(application, customer, now):
    withdrawn = withdraw_application(application, customer, now=now)

    assert withdrawn.stage.kind == Stage.Kind.WITHDRAWN
    assert withdrawn.closed_at == now
    assert not withdrawn.is_open
    change = withdrawn.stage_changes.get(to_stage=withdrawn.stage)
    assert change.changed_by == customer


def test_nobody_else_can_withdraw(application, recruiter):
    with pytest.raises(ApplicationError, match="Only the applicant"):
        withdraw_application(application, recruiter)

    application.refresh_from_db()
    assert application.is_open


def test_a_closed_application_cannot_be_withdrawn(rejected, customer):
    with pytest.raises(ApplicationError, match="closed"):
        withdraw_application(rejected, customer)


def test_withdrawing_emails_on_commit(
    application, customer, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        withdraw_application(application, customer)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [customer.email]
    assert "Withdrawn" in mail.outbox[0].body


def test_the_withdraw_page_explains_itself(client, customer, application, settings):
    settings.CAREERS_EMAIL = "hiring@example.com"
    client.force_login(customer)

    response = client.get(withdraw_url(application))

    assert b"hiring@example.com" in response.content
    application.refresh_from_db()
    assert application.is_open


def test_withdrawing_from_the_page(client, customer, application):
    client.force_login(customer)

    response = client.post(withdraw_url(application), follow=True)

    assert b"Withdrawn" in response.content
    application.refresh_from_db()
    assert application.stage.kind == Stage.Kind.WITHDRAWN


def test_my_applications_offers_withdraw_only_while_open(
    client, customer, application, recruiter
):
    client.force_login(customer)
    url = reverse("careers:applications")
    assert withdraw_url(application).encode() in client.get(url).content

    move_application(application, stage(Stage.Kind.HIRED), recruiter)

    assert withdraw_url(application).encode() not in client.get(url).content


def test_a_closed_application_is_refused_on_the_page(client, customer, rejected):
    client.force_login(customer)

    response = client.post(withdraw_url(rejected), follow=True)

    assert b"closed" in response.content
    rejected.refresh_from_db()
    assert rejected.stage.kind == Stage.Kind.REJECTED


def test_someone_elses_application_is_a_404(client, staff_user, application):
    client.force_login(staff_user)

    assert client.get(withdraw_url(application)).status_code == HTTPStatus.NOT_FOUND
    assert client.post(withdraw_url(application)).status_code == HTTPStatus.NOT_FOUND


def test_a_visitor_must_sign_in_to_withdraw(client, application):
    response = client.post(withdraw_url(application))

    assert reverse("accounts:login") in response.url


def test_a_recruiter_reopens_with_a_reason(rejected, recruiter, interview, now):
    reopened = reopen_application(
        rejected, interview, "Rejected by mistake.", recruiter, now=now
    )

    assert reopened.stage == interview
    assert reopened.closed_at is None
    assert reopened.is_open
    change = reopened.stage_changes.get(to_stage=interview)
    assert change.note == "Rejected by mistake."
    assert change.changed_by == recruiter
    assert change.from_stage.kind == Stage.Kind.REJECTED


def test_a_withdrawn_application_can_be_reopened(
    application, customer, recruiter, interview
):
    withdrawn = withdraw_application(application, customer)

    reopened = reopen_application(withdrawn, interview, "They emailed us.", recruiter)

    assert reopened.is_open


@pytest.mark.parametrize("reason", ["", "   "])
def test_reopen_needs_a_reason(rejected, recruiter, interview, reason):
    with pytest.raises(ApplicationError, match="reason"):
        reopen_application(rejected, interview, reason, recruiter)


def test_reopen_needs_an_in_progress_stage(rejected, recruiter):
    with pytest.raises(ApplicationError, match="in-progress"):
        reopen_application(rejected, Stage.objects.entry(), "Why.", recruiter)


def test_reopen_refuses_a_retired_stage(rejected, recruiter, interview):
    Stage.objects.filter(pk=interview.pk).update(is_active=False)
    interview.refresh_from_db()

    with pytest.raises(ApplicationError, match="retired"):
        reopen_application(rejected, interview, "Why.", recruiter)


def test_an_open_application_cannot_be_reopened(application, recruiter, interview):
    with pytest.raises(ApplicationError, match="already open"):
        reopen_application(application, interview, "Why.", recruiter)


def test_reopen_works_on_a_closed_job(rejected, recruiter, interview):
    Job.objects.filter(pk=rejected.job_id).update(status=Job.Status.CLOSED)

    assert reopen_application(rejected, interview, "Why.", recruiter).is_open


def test_reopen_sends_no_email(
    rejected, recruiter, interview, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        reopen_application(rejected, interview, "Why.", recruiter)

    assert mail.outbox == []


def test_an_anonymized_application_cannot_be_reopened(rejected, recruiter, interview):
    Application.objects.filter(pk=rejected.pk).update(
        user=None, anonymized_at=timezone.now()
    )
    rejected.refresh_from_db()

    with pytest.raises(ApplicationError, match="anonymized"):
        reopen_application(rejected, interview, "Why.", recruiter)


def test_the_service_refuses_those_who_cannot_recruit(rejected, staff_user, interview):
    with pytest.raises(ApplicationError, match="hiring team"):
        reopen_application(rejected, interview, "Why.", staff_user)


def test_nobody_reopens_their_own_application(
    make_application, make_job, recruiter, interview
):
    application = make_application(make_job(), recruiter)
    withdrawn = withdraw_application(application, recruiter)

    with pytest.raises(ApplicationError, match="your own"):
        reopen_application(withdrawn, interview, "Why.", recruiter)


def test_a_reopen_can_be_moved_and_closed_again(rejected, recruiter, interview):
    reopened = reopen_application(rejected, interview, "Why.", recruiter)

    closed = move_application(reopened, stage(Stage.Kind.HIRED), recruiter)

    assert closed.closed_at is not None


def test_reopening_from_the_page(client, recruiter, rejected, interview):
    client.force_login(recruiter)

    response = client.post(
        reopen_url(rejected), {"stage": interview.pk, "reason": "My mistake."}
    )

    assert response.url == detail_url(rejected)
    rejected.refresh_from_db()
    assert rejected.stage == interview


def test_a_missing_reason_is_refused_on_the_page(
    client, recruiter, rejected, interview
):
    client.force_login(recruiter)

    response = client.post(
        reopen_url(rejected), {"stage": interview.pk, "reason": ""}, follow=True
    )

    assert b"reason" in response.content
    rejected.refresh_from_db()
    assert not rejected.is_open


def test_the_page_refuses_those_who_cannot_recruit(
    client, staff_user, rejected, interview
):
    client.force_login(staff_user)

    response = client.post(
        reopen_url(rejected), {"stage": interview.pk, "reason": "Why."}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_reopening_your_own_from_the_page_is_a_404(
    client, make_application, make_job, recruiter, interview
):
    application = make_application(make_job(), recruiter)
    withdrawn = withdraw_application(application, recruiter)
    client.force_login(recruiter)

    response = client.post(
        reopen_url(withdrawn), {"stage": interview.pk, "reason": "Why."}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_the_detail_page_offers_reopen_only_when_closed(client, recruiter, application):
    client.force_login(recruiter)
    assert (
        reopen_url(application).encode()
        not in client.get(detail_url(application)).content
    )

    move_application(application, stage(Stage.Kind.REJECTED), recruiter)

    response = client.get(detail_url(application))
    assert reopen_url(application).encode() in response.content
    offered = list(response.context["reopen_stages"])
    assert offered and all(s.kind == Stage.Kind.IN_PROGRESS for s in offered)


def test_the_detail_page_hides_reopen_once_anonymized(client, recruiter, rejected):
    Application.objects.filter(pk=rejected.pk).update(
        user=None, anonymized_at=timezone.now()
    )
    client.force_login(recruiter)

    response = client.get(detail_url(rejected))

    assert reopen_url(rejected).encode() not in response.content


def test_recruiters_see_the_reason_and_who_withdrew(
    client, recruiter, customer, application, interview
):
    withdrawn = withdraw_application(application, customer)
    reopen_application(withdrawn, interview, "They emailed us.", recruiter)
    client.force_login(recruiter)

    response = client.get(detail_url(application))

    assert b"They emailed us." in response.content
    assert customer.display_name.encode() in response.content


def test_the_reason_never_reaches_the_applicant(
    client, customer, rejected, recruiter, interview
):
    reopen_application(rejected, interview, "They emailed us.", recruiter)
    client.force_login(customer)

    response = client.get(reverse("careers:applications"))

    assert b"They emailed us." not in response.content
    assert b"Under review" in response.content
