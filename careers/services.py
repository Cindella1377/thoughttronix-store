"""The hiring workflows: the only code that changes an application's stage.

Each workflow crosses models, and later files and email too, so the rules
live here in one reviewable place and views stay thin. A broken rule
raises ``ApplicationError`` with a message fit to show the person.
"""

import datetime

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Application, Job, Stage, StageChange


class ApplicationError(Exception):
    """A hiring rule refused the request."""


def submit_application(
    job: Job,
    user: AbstractBaseUser,
    resume: UploadedFile,
    cover_letter: str = "",
    now: datetime.datetime | None = None,
) -> Application:
    """Create ``user``'s application to ``job`` in the Entry stage.

    Writes the first ``StageChange``, which has no from-stage, so every
    timeline starts here. The job must be Open. A second application to
    the same job, such as from a double-click, is caught by the database
    constraint and reported as already applied, and its file is removed.
    """
    if not job.is_open:
        raise ApplicationError("This job is no longer accepting applications.")
    now = now or timezone.now()
    stage = Stage.objects.entry()
    application = Application(
        job=job,
        user=user,
        stage=stage,
        resume=resume,
        cover_letter=cover_letter,
        created_at=now,
    )
    try:
        with transaction.atomic():
            application.save()
            StageChange.objects.create(
                application=application,
                to_stage=stage,
                changed_by=user,
                created_at=now,
            )
    except IntegrityError as error:
        application.resume.delete(save=False)
        raise ApplicationError("You've already applied to this job.") from error
    return application


def move_application(
    application: Application,
    stage: Stage,
    by: AbstractBaseUser,
    note: str = "",
    now: datetime.datetime | None = None,
) -> Application:
    """Move an open application to ``stage`` and log who did it.

    Staff may go forward, backward, or skip ahead, to any active stage
    but Withdrawn. A stage that isn't open closes the application, and
    only that: the job, other applications, and the user are untouched.
    Nobody may move their own application. The rules read the saved row,
    locked, so a stale page can't move what has since closed. Returns the
    fresh application.
    """
    now = now or timezone.now()
    if not by.can_recruit:
        raise ApplicationError("Only the hiring team can move applications.")
    if application.user_id == by.pk:
        raise ApplicationError("You can't move your own application.")
    if not stage.is_active:
        raise ApplicationError("That stage has been retired.")
    if stage.kind == Stage.Kind.WITHDRAWN:
        raise ApplicationError("Only the applicant can withdraw an application.")
    with transaction.atomic():
        current = (
            Application.objects.select_for_update(of=("self",))
            .select_related("stage")
            .get(pk=application.pk)
        )
        if not current.is_open:
            raise ApplicationError("This application is closed.")
        if current.stage == stage:
            raise ApplicationError(f"This application is already in {stage.name}.")
        from_stage = current.stage
        current.stage = stage
        if not stage.is_open:
            current.closed_at = now
        current.save(update_fields=["stage", "closed_at"])
        StageChange.objects.create(
            application=current,
            from_stage=from_stage,
            to_stage=stage,
            changed_by=by,
            note=note,
            created_at=now,
        )
    return current
