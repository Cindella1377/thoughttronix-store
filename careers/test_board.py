"""The board — phase 9 of the careers plan."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from .models import Stage
from .services import anonymize_application, move_application

HTMX = {"HX-Request": "true"}


@pytest.fixture
def as_recruiter(client, recruiter):
    client.force_login(recruiter)
    return client


@pytest.fixture
def application(make_application, make_job, customer):
    return make_application(make_job(), customer)


@pytest.fixture
def offer(db):
    return Stage.objects.get(name="Offer")


def board_url(job):
    return reverse("careers:board", args=[job.pk])


def move(client, application, stage, **data):
    return client.post(
        reverse("careers:move", args=[application.pk]),
        {"stage": stage.pk, "board": "1", "next": board_url(application.job), **data},
        headers=HTMX,
    )


def column(response, name):
    columns = response.context["board"]["columns"]
    return next(c for c in columns if c["stage"].name == name)


def test_only_those_who_can_recruit_reach_the_board(
    client, customer, staff_user, application
):
    url = board_url(application.job)
    assert client.get(url).status_code == HTTPStatus.FOUND
    for user in (customer, staff_user):
        client.force_login(user)
        assert client.get(url).status_code == HTTPStatus.FORBIDDEN


def test_there_is_one_column_per_active_stage_in_order(as_recruiter, application):
    Stage.objects.filter(name="Screening").update(is_active=False)

    response = as_recruiter.get(board_url(application.job))

    names = [c["stage"].name for c in response.context["board"]["columns"]]
    assert names == list(
        Stage.objects.filter(is_active=True).values_list("name", flat=True)
    )
    assert "Screening" not in names


def test_columns_follow_a_reorder(as_recruiter, application, offer):
    offer.shift(-1)

    response = as_recruiter.get(board_url(application.job))

    names = [c["stage"].name for c in response.context["board"]["columns"]]
    assert names.index("Offer") < names.index("Interview")


def test_open_applications_sit_in_their_columns(
    as_recruiter, recruiter, make_application, application, staff_user, offer
):
    moved = make_application(application.job, staff_user)
    move_application(moved, offer, recruiter)

    response = as_recruiter.get(board_url(application.job))

    assert column(response, "Applied")["applications"] == [application]
    assert column(response, "Offer")["applications"] == [moved]
    assert column(response, "Applied")["count"] == 1
    assert application.applicant_name.encode() in response.content


def test_closed_applications_are_only_a_count(
    as_recruiter, recruiter, make_application, application, staff_user
):
    closed = make_application(application.job, staff_user)
    rejected = Stage.objects.get(kind=Stage.Kind.REJECTED)
    move_application(closed, rejected, recruiter)

    response = as_recruiter.get(board_url(application.job))

    assert response.context["board"]["closed"] == 1
    assert column(response, "Rejected")["applications"] == []
    assert column(response, "Rejected")["count"] == 1
    assert closed.applicant_name.encode() not in response.content


def test_an_anonymized_record_counts_as_closed(as_recruiter, application):
    anonymize_application(application)

    response = as_recruiter.get(board_url(application.job))

    assert response.context["board"]["closed"] == 1
    assert column(response, "Applied")["count"] == 0
    assert b"Former applicant" not in response.content


def test_a_board_move_returns_the_updated_board(as_recruiter, application, offer):
    response = move(as_recruiter, application, offer)

    assert response.status_code == HTTPStatus.OK
    assert b"<html" not in response.content
    assert b'id="board"' in response.content
    assert response["HX-Retarget"] == "#board"
    assert response["HX-Reswap"] == "outerHTML"
    assert column(response, "Applied")["count"] == 0
    assert column(response, "Offer")["applications"] == [application]


def test_a_refused_move_explains_itself_and_changes_nothing(
    as_recruiter, recruiter, application, offer
):
    move_application(
        application, Stage.objects.get(kind=Stage.Kind.REJECTED), recruiter
    )

    response = move(as_recruiter, application, offer)

    assert b"closed" in response.content
    assert response["HX-Retarget"] == "#board"
    application.refresh_from_db()
    assert application.stage.kind == Stage.Kind.REJECTED


def test_a_final_move_warns_on_the_card_first(as_recruiter, application):
    hired = Stage.objects.get(kind=Stage.Kind.HIRED)

    response = move(as_recruiter, application, hired)

    assert b"This will email the applicant" in response.content
    assert b'id="board"' not in response.content
    assert "HX-Retarget" not in response
    assert b'name="board"' in response.content
    application.refresh_from_db()
    assert application.is_open


def test_confirming_on_the_board_updates_it_in_place(as_recruiter, application):
    hired = Stage.objects.get(kind=Stage.Kind.HIRED)

    response = move(as_recruiter, application, hired, confirmed="1")

    assert b'id="board"' in response.content
    assert response.context["board"]["closed"] == 1
    assert column(response, "Hired")["count"] == 1


def test_the_viewers_own_application_does_not_appear(
    as_recruiter, make_application, make_job, recruiter
):
    application = make_application(make_job(), recruiter)

    response = as_recruiter.get(board_url(application.job))

    assert response.context["board"]["total"] == 0
    assert b"No applications yet" in response.content


def test_the_board_has_an_empty_state(as_recruiter, make_job):
    response = as_recruiter.get(board_url(make_job()))

    assert b"No applications yet" in response.content


def test_the_board_scrolls_inside_itself_on_a_phone(as_recruiter, application):
    response = as_recruiter.get(board_url(application.job))

    assert b"overflow-x-auto" in response.content


def test_table_and_board_link_to_each_other(as_recruiter, application):
    job = application.job
    table = reverse("careers:manage_applications", args=[job.pk])

    assert board_url(job).encode() in as_recruiter.get(table).content
    assert table.encode() in as_recruiter.get(board_url(job)).content


def test_the_query_count_does_not_grow_with_applications(
    as_recruiter,
    make_application,
    application,
    django_user_model,
    django_assert_max_num_queries,
):
    url = board_url(application.job)
    with django_assert_max_num_queries(12):
        as_recruiter.get(url)

    for number in range(5):
        user = django_user_model.objects.create_user(
            username=f"applicant{number}",
            email=f"applicant{number}@example.com",
            password="applicant123",
        )
        make_application(application.job, user)

    with django_assert_max_num_queries(12):
        as_recruiter.get(url)
