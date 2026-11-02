"""Editing the stages — phase 7 of the careers plan."""

from http import HTTPStatus

import pytest
from django.core import mail
from django.db.models import ProtectedError
from django.urls import reverse

from .models import Stage
from .services import move_application, withdraw_application


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


def named(name):
    return Stage.objects.get(name=name)


def active_names():
    return list(Stage.objects.filter(is_active=True).values_list("name", flat=True))


def post_retire(client, stage):
    return client.post(reverse("careers:stage_retire", args=[stage.pk]), follow=True)


def post_shift(client, stage, direction):
    return client.post(
        reverse("careers:stage_shift", args=[stage.pk]), {"direction": direction}
    )


def test_only_those_who_can_recruit_reach_the_page(client, customer, staff_user, offer):
    urls = [
        reverse("careers:stages"),
        reverse("careers:stage_create"),
        reverse("careers:stage_edit", args=[offer.pk]),
    ]
    actions = [
        reverse("careers:stage_retire", args=[offer.pk]),
        reverse("careers:stage_restore", args=[offer.pk]),
        reverse("careers:stage_shift", args=[offer.pk]),
    ]
    for url in urls:
        assert client.get(url).status_code == HTTPStatus.FOUND
    for user in (customer, staff_user):
        client.force_login(user)
        for url in urls:
            assert client.get(url).status_code == HTTPStatus.FORBIDDEN
        for url in actions:
            assert client.post(url).status_code == HTTPStatus.FORBIDDEN
    offer.refresh_from_db()
    assert offer.is_active


def test_the_job_list_links_to_the_stages(as_recruiter):
    response = as_recruiter.get(reverse("careers:manage_jobs"))

    assert reverse("careers:stages").encode() in response.content


def test_the_page_lists_stages_with_kind_and_count(as_recruiter, application):
    response = as_recruiter.get(reverse("careers:stages"))

    stages = list(response.context["stages"])
    assert [s.name for s in stages][:2] == ["Applied", "Screening"]
    assert stages[0].application_count == 1
    assert stages[1].application_count == 0
    assert b"In progress" in response.content


@pytest.mark.parametrize(
    "kind", [Stage.Kind.IN_PROGRESS, Stage.Kind.HIRED, Stage.Kind.REJECTED]
)
def test_a_new_stage_may_take_some_kinds(as_recruiter, kind):
    response = as_recruiter.post(
        reverse("careers:stage_create"), {"name": "Take-home", "kind": kind}
    )

    assert response.url == reverse("careers:stages")
    stage = named("Take-home")
    assert stage.kind == kind
    assert stage.is_active
    assert (
        stage.position > Stage.objects.exclude(pk=stage.pk).latest("position").position
    )


@pytest.mark.parametrize("kind", [Stage.Kind.ENTRY, Stage.Kind.WITHDRAWN])
def test_a_new_stage_may_not_take_the_single_kinds(as_recruiter, kind):
    response = as_recruiter.post(
        reverse("careers:stage_create"), {"name": "Second", "kind": kind}
    )

    assert response.status_code == HTTPStatus.OK
    assert not Stage.objects.filter(name="Second").exists()


def test_renaming_keeps_the_kind(as_recruiter, offer):
    as_recruiter.post(
        reverse("careers:stage_edit", args=[offer.pk]),
        {"name": "Final chat", "kind": Stage.Kind.HIRED},
    )

    offer.refresh_from_db()
    assert offer.name == "Final chat"
    assert offer.kind == Stage.Kind.IN_PROGRESS


def test_the_edit_form_does_not_offer_the_kind(as_recruiter, offer):
    response = as_recruiter.get(reverse("careers:stage_edit", args=[offer.pk]))

    assert "kind" not in response.context["form"].fields


def test_shifting_reorders_active_stages(as_recruiter, offer):
    post_shift(as_recruiter, offer, "up")

    assert active_names()[:4] == ["Applied", "Screening", "Offer", "Interview"]

    post_shift(as_recruiter, offer, "down")

    assert active_names()[:4] == ["Applied", "Screening", "Interview", "Offer"]


def test_the_page_shows_the_new_order(as_recruiter, offer):
    post_shift(as_recruiter, offer, "up")

    response = as_recruiter.get(reverse("careers:stages"))

    names = [stage.name for stage in response.context["stages"]]
    assert names.index("Offer") < names.index("Interview")


def test_shifting_skips_over_retired_stages(as_recruiter, offer):
    Stage.objects.filter(name="Interview").update(is_active=False)

    post_shift(as_recruiter, offer, "up")

    assert active_names()[:3] == ["Applied", "Offer", "Screening"]


def test_shifting_stops_at_the_ends(as_recruiter):
    before = active_names()

    post_shift(as_recruiter, named("Applied"), "up")
    post_shift(as_recruiter, named("Withdrawn"), "down")

    assert active_names() == before


def test_a_bad_direction_changes_nothing(as_recruiter, offer):
    before = active_names()

    response = post_shift(as_recruiter, offer, "sideways")

    assert response.url == reverse("careers:stages")
    assert active_names() == before


def test_an_empty_stage_can_be_retired(as_recruiter, offer):
    response = post_retire(as_recruiter, offer)

    assert b"retired" in response.content
    offer.refresh_from_db()
    assert not offer.is_active


def test_a_stage_holding_an_open_application_cannot_be_retired(
    as_recruiter, recruiter, application, offer
):
    move_application(application, offer, recruiter)

    response = post_retire(as_recruiter, offer)

    assert b"applications" in response.content
    offer.refresh_from_db()
    assert offer.is_active


def test_a_stage_holding_a_closed_application_cannot_be_retired(recruiter, application):
    extra = Stage.objects.create(name="No thanks", kind=Stage.Kind.REJECTED)
    move_application(application, extra, recruiter)

    assert not extra.can_retire()


@pytest.mark.parametrize("name", ["Applied", "Hired", "Rejected", "Withdrawn"])
def test_a_required_kind_keeps_an_active_stage(as_recruiter, name):
    stage = named(name)
    assert not stage.can_retire()

    post_retire(as_recruiter, stage)

    stage.refresh_from_db()
    assert stage.is_active


def test_a_spare_final_stage_can_be_retired(db):
    spare = Stage.objects.create(name="Hired part-time", kind=Stage.Kind.HIRED)

    assert spare.can_retire()
    assert named("Hired").can_retire()
    spare.retire()
    assert not named("Hired").can_retire()


def test_the_page_says_why_a_stage_cannot_retire(as_recruiter):
    response = as_recruiter.get(reverse("careers:stages"))

    assert b"Required" in response.content


def test_a_retired_stage_can_be_restored(as_recruiter, offer):
    post_retire(as_recruiter, offer)

    as_recruiter.post(reverse("careers:stage_restore", args=[offer.pk]))

    offer.refresh_from_db()
    assert offer.is_active
    assert "Offer" in active_names()


def test_a_retired_stage_leaves_the_choices_and_keeps_its_history(
    as_recruiter, recruiter, application, offer
):
    moved = move_application(application, offer, recruiter)
    moved = move_application(moved, named("Interview"), recruiter)
    post_retire(as_recruiter, offer)

    response = as_recruiter.get(reverse("careers:application", args=[moved.pk]))

    assert offer not in response.context["stages"]
    assert offer not in response.context["reopen_stages"]
    assert b"Offer" in response.content


def test_stages_cannot_be_deleted_while_in_use(application):
    with pytest.raises(ProtectedError):
        application.stage.delete()


def test_the_rules_survive_renaming_every_stage(
    client,
    customer,
    recruiter,
    application,
    django_capture_on_commit_callbacks,
):
    for stage in Stage.objects.all():
        stage.name = f"Secret {stage.pk}"
        stage.save()
    application.refresh_from_db()

    hired = Stage.objects.filter(kind=Stage.Kind.HIRED).get()
    with django_capture_on_commit_callbacks(execute=True):
        moved = move_application(application, hired, recruiter)

    assert not moved.is_open
    assert "Application successful" in mail.outbox[0].body
    assert "Secret" not in mail.outbox[0].body
    client.force_login(customer)
    response = client.get(reverse("careers:applications"))
    assert b"Application successful" in response.content
    assert b"Secret" not in response.content


def test_withdrawing_survives_renaming(application, customer):
    Stage.objects.filter(kind=Stage.Kind.WITHDRAWN).update(name="Gone")

    withdrawn = withdraw_application(application, customer)

    assert withdrawn.stage.kind == Stage.Kind.WITHDRAWN
