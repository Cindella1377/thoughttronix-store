"""The demo world — phase 11 of the careers plan."""

import importlib
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command

from products.management.commands.seed import (
    BACKGROUND_CUSTOMERS,
    CAREER_APPLICATIONS,
    CAREER_JOBS,
    DEFAULT_STAGES,
)

from .models import Application, Job, Note, Stage, StageChange


def stored_files():
    return sorted(
        p.name for p in Path(settings.PRIVATE_MEDIA_ROOT).rglob("*") if p.is_file()
    )


def test_the_seed_and_the_migration_agree_on_the_default_stages():
    migration = importlib.import_module("careers.migrations.0003_default_stages")

    assert DEFAULT_STAGES == migration.DEFAULT_STAGES


def test_sample_applicants_are_background_customers():
    known = {username for username, *_ in BACKGROUND_CUSTOMERS}

    assert {row[1] for row in CAREER_APPLICATIONS} <= known


def test_each_person_applies_to_a_job_once():
    pairs = [(row[0], row[1]) for row in CAREER_APPLICATIONS]

    assert len(pairs) == len(set(pairs))


def test_sample_applications_target_jobs_that_take_them():
    drafts = {row[0] for row in CAREER_JOBS if row[5] == Job.Status.DRAFT}
    titles = {row[0] for row in CAREER_JOBS}

    assert {row[0] for row in CAREER_APPLICATIONS} <= titles - drafts


def test_no_sample_happens_in_the_future():
    for _, _, days_ago, _, steps in CAREER_APPLICATIONS:
        assert all(step[2] < days_ago for step in steps)


@pytest.fixture
def seeded(db):
    call_command("seed")


def test_every_status_and_kind_appears(seeded):
    assert set(Job.objects.values_list("status", flat=True)) == set(Job.Status.values)
    held = set(Application.objects.values_list("stage__kind", flat=True))
    assert held == set(Stage.Kind.values)


def test_seeded_timelines_are_valid(seeded):
    assert Note.objects.exists()
    for application in Application.objects.all():
        changes = list(application.stage_changes.all())
        assert changes[0].from_stage is None
        assert changes[-1].to_stage == application.stage
        for before, after in zip(changes, changes[1:], strict=False):
            assert after.from_stage == before.to_stage
        assert (application.closed_at is None) == application.is_open


def test_one_seeded_application_shows_a_reopen_and_one_is_anonymized(seeded):
    assert StageChange.objects.filter(
        from_stage__kind=Stage.Kind.REJECTED, to_stage__kind=Stage.Kind.IN_PROGRESS
    ).exists()
    anonymized = Application.objects.get(anonymized_at__isnull=False)
    assert anonymized.user is None
    assert not anonymized.resume


def test_a_closed_job_keeps_its_applications(seeded):
    closed = Job.objects.get(status=Job.Status.CLOSED)

    assert closed.applications.exists()
    assert not Job.objects.filter(
        status=Job.Status.DRAFT, applications__isnull=False
    ).exists()


def test_the_recruiter_can_sign_in_to_the_careers_tab(client, seeded):
    recruiter = get_user_model().objects.get(username="recruiter")

    assert client.login(username="recruiter", password="recruiter123")
    assert recruiter.can_recruit


def test_the_employee_cannot_recruit_so_the_difference_shows(seeded):
    assert not get_user_model().objects.get(username="employee").can_recruit


def test_the_customer_has_no_applications(seeded):
    customer = get_user_model().objects.get(username="customer")

    assert not customer.applications.exists()


def test_stored_resumes_are_real_pdfs(seeded):
    for application in Application.objects.exclude(resume=""):
        with application.resume.open("rb") as resume:
            content = resume.read()
        assert content.startswith(b"%PDF-")
        assert content.rstrip().endswith(b"%%EOF")


def test_seeding_sends_no_mail(seeded):
    assert mail.outbox == []


def test_seeding_twice_gives_the_same_world(seeded):
    def snapshot():
        return (
            list(Stage.objects.values_list("name", "kind", "is_active")),
            sorted(Job.objects.values_list("slug", "status")),
            Application.objects.count(),
            StageChange.objects.count(),
            Note.objects.count(),
            len(stored_files()),
        )

    first = snapshot()

    call_command("seed")

    assert snapshot() == first


def test_seeding_restores_edited_stages(seeded):
    Stage.objects.filter(name="Screening").update(name="Vibe check")
    Stage.objects.create(name="Take-home", kind=Stage.Kind.IN_PROGRESS)

    call_command("seed")

    names = list(Stage.objects.values_list("name", flat=True))
    assert names == [name for name, _ in DEFAULT_STAGES]


def test_seeding_leaves_no_orphaned_files(seeded):
    call_command("seed")

    expected = Application.objects.exclude(resume="").count()
    assert len(stored_files()) == expected
