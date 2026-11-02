"""The hiring workflows: the only code that changes an application's stage.

Each workflow crosses models, and later files and email too, so the rules
live here in one reviewable place and views stay thin. A broken rule
raises ``ApplicationError`` with a message fit to show the person.
"""

import datetime

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.files.uploadedfile import UploadedFile
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Application, Job, Stage, StageChange

# How long a closed application keeps its personal data.
RETENTION_DAYS = 365

# The email each closing kind sends, named for its templates.
CLOSING_EMAILS = {
    Stage.Kind.HIRED: "successful",
    Stage.Kind.REJECTED: "not_moving_forward",
    Stage.Kind.WITHDRAWN: "withdrawn",
}


class ApplicationError(Exception):
    """A hiring rule refused the request."""


def _email_applicant(application: Application, name: str) -> None:
    """Send the ``name`` email once the current transaction commits.

    An email can't be recalled, so it waits until the save has succeeded.
    ``robust`` logs a mail failure instead of raising it: by then the
    change is saved and must stand. The context holds the public label
    only, never a stage name or a note.
    """
    context = {
        "user": application.user,
        "job": application.job,
        "status": application.public_status,
        "careers_email": settings.CAREERS_EMAIL,
    }
    transaction.on_commit(
        lambda: send_mail(
            subject=render_to_string(
                f"careers/email/{name}_subject.txt", context
            ).strip(),
            message=render_to_string(f"careers/email/{name}_email.txt", context),
            from_email=None,
            recipient_list=[context["user"].email],
        ),
        robust=True,
    )


def _lock(application: Application) -> Application:
    """The saved row, locked for this transaction.

    Rules read this rather than the caller's copy, so a stale page can't
    act on an application that has since changed.
    """
    return (
        Application.objects.select_for_update(of=("self",))
        .select_related("stage")
        .get(pk=application.pk)
    )


def _record_move(
    application: Application,
    stage: Stage,
    by: AbstractBaseUser,
    note: str,
    now: datetime.datetime,
) -> None:
    """Change the stage and write its log row. Call inside a transaction."""
    from_stage = application.stage
    application.stage = stage
    application.closed_at = None if stage.is_open else now
    application.save(update_fields=["stage", "closed_at"])
    StageChange.objects.create(
        application=application,
        from_stage=from_stage,
        to_stage=stage,
        changed_by=by,
        note=note,
        created_at=now,
    )


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
    Emails the applicant once the application is saved.
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
            _email_applicant(application, "received")
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
    A move to Hired or Rejected emails the applicant after it commits.
    Nobody may move their own application. Returns the fresh application.
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
        current = _lock(application)
        if not current.is_open:
            raise ApplicationError("This application is closed.")
        if current.stage == stage:
            raise ApplicationError(f"This application is already in {stage.name}.")
        _record_move(current, stage, by, note, now)
        if stage.emails_applicant:
            _email_applicant(current, CLOSING_EMAILS[stage.kind])
    return current


def reopen_application(
    application: Application,
    stage: Stage,
    reason: str,
    by: AbstractBaseUser,
    now: datetime.datetime | None = None,
) -> Application:
    """Bring a closed application back to an In progress stage.

    The deliberate way to undo Hired, Rejected, or Withdrawn. ``reason``
    is required and kept on the log, for staff only. Sends no email: the
    recruiter contacts the applicant themselves. A Closed job doesn't
    block it, but an anonymized application can't return, because its
    résumé and owner are gone. Returns the fresh application.
    """
    now = now or timezone.now()
    reason = reason.strip()
    if not by.can_recruit:
        raise ApplicationError("Only the hiring team can reopen applications.")
    if application.user_id == by.pk:
        raise ApplicationError("You can't reopen your own application.")
    if not reason:
        raise ApplicationError("Give a reason for reopening.")
    if not stage.is_active:
        raise ApplicationError("That stage has been retired.")
    if stage.kind != Stage.Kind.IN_PROGRESS:
        raise ApplicationError("Reopen into an in-progress stage.")
    with transaction.atomic():
        current = _lock(application)
        if current.anonymized_at is not None:
            raise ApplicationError("An anonymized application can't be reopened.")
        if current.is_open:
            raise ApplicationError("This application is already open.")
        _record_move(current, stage, by, reason, now)
    return current


def withdraw_application(
    application: Application,
    by: AbstractBaseUser,
    now: datetime.datetime | None = None,
) -> Application:
    """Close an open application at its applicant's request.

    Only the applicant may do this. The log shows them as the actor, and
    they get a confirmation email after it commits. Staff can bring it
    back with ``reopen_application``. Returns the fresh application.
    """
    now = now or timezone.now()
    if application.user_id != by.pk:
        raise ApplicationError("Only the applicant can withdraw an application.")
    with transaction.atomic():
        current = _lock(application)
        if not current.is_open:
            raise ApplicationError("This application is closed.")
        stage = Stage.objects.withdrawn()
        _record_move(current, stage, by, "", now)
        _email_applicant(current, CLOSING_EMAILS[stage.kind])
    return current


def anonymize_application(
    application: Application,
    now: datetime.datetime | None = None,
) -> Application:
    """Remove an application's personal data, keeping an anonymous record.

    Deletes the résumé file first, since a database row going away would
    leave it on disk. Then clears the owner, cover letter, notes, and
    stage-change notes, and the applicant's name from the log. Staff
    actors stay, and so does the history, for reporting. An application
    still open closes, because it has nobody left to tell. Doing this
    twice is harmless. Returns the fresh application.
    """
    now = now or timezone.now()
    with transaction.atomic():
        current = _lock(application)
        if current.anonymized_at is not None:
            return current
        owner_id = current.user_id
        current.resume.delete(save=False)
        current.notes.all().delete()
        changes = current.stage_changes.all()
        changes.update(note="")
        if owner_id is not None:
            changes.filter(changed_by_id=owner_id).update(changed_by=None)
        current.user = None
        current.cover_letter = ""
        current.closed_at = current.closed_at or now
        current.anonymized_at = now
        current.save(
            update_fields=[
                "resume",
                "user",
                "cover_letter",
                "closed_at",
                "anonymized_at",
            ]
        )
    return current


def purge_applications(now: datetime.datetime | None = None) -> int:
    """Anonymize everything closed for ``RETENTION_DAYS`` or more.

    Reopening clears ``closed_at``, so the clock restarts if an
    application closes again. Returns how many were anonymized.
    """
    now = now or timezone.now()
    cutoff = now - datetime.timedelta(days=RETENTION_DAYS)
    due = Application.objects.filter(closed_at__lte=cutoff, anonymized_at__isnull=True)
    count = 0
    for application in due:
        anonymize_application(application, now=now)
        count += 1
    return count
