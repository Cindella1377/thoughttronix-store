import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from .storage import PrivateStorage

# Fixed paths that sit beside ``/careers/<slug>/``, so no job may take them.
RESERVED_SLUGS = {"applications"}


def validate_job_slug(value):
    """Keep a job's slug clear of the app's own fixed paths."""
    if value in RESERVED_SLUGS:
        raise ValidationError("This slug is reserved. Choose another.")


class JobQuerySet(models.QuerySet):
    def listed(self):
        """Open jobs, newest first: what the public list shows."""
        return self.filter(status=Job.Status.OPEN).order_by("-published_at")

    def public(self):
        """Jobs with a public page. A Draft does not exist for visitors."""
        return self.exclude(status=Job.Status.DRAFT)


class Job(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=200, unique=True, validators=[validate_job_slug])
    description = models.TextField()
    department = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    employment_type = models.CharField(
        max_length=20, choices=EmploymentType, default=EmploymentType.FULL_TIME
    )
    salary_range = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    # When the job first went Open; null while it has never been public.
    published_at = models.DateTimeField(null=True, blank=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("careers:job", kwargs={"slug": self.slug})

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED

    def next_statuses(self):
        """The statuses this job may move to from where it is now."""
        return STATUS_MOVES[self.status]

    def change_status(self, status, now=None):
        """Move the job to ``status``, refusing a move the rules don't allow.

        Staying put is allowed. The first move to Open records when the
        job was published. The caller saves the job.
        """
        if status == self.status:
            return
        if status not in self.next_statuses():
            raise ValueError(f"A {self.status} job cannot become {status}.")
        self.status = status
        if self.is_open and self.published_at is None:
            self.published_at = now or timezone.now()


STATUS_MOVES = {
    Job.Status.DRAFT: [Job.Status.OPEN],
    Job.Status.OPEN: [Job.Status.CLOSED],
    Job.Status.CLOSED: [Job.Status.OPEN],
}


class StageQuerySet(models.QuerySet):
    def entry(self):
        """The one active stage every new application starts in."""
        return self.get(kind=Stage.Kind.ENTRY, is_active=True)

    def movable(self):
        """Stages staff may move an application to. Withdrawing is the
        applicant's own act."""
        return self.filter(is_active=True).exclude(kind=Stage.Kind.WITHDRAWN)

    def reopenable(self):
        """Stages a closed application may come back to."""
        return self.filter(is_active=True, kind=Stage.Kind.IN_PROGRESS)

    def withdrawn(self):
        """The one active stage a withdrawal lands in."""
        return self.get(kind=Stage.Kind.WITHDRAWN, is_active=True)


class Stage(models.Model):
    """A hiring stage. Staff own the name; the code reads only ``kind``."""

    class Kind(models.TextChoices):
        ENTRY = "entry", "Entry"
        IN_PROGRESS = "in_progress", "In progress"
        HIRED = "hired", "Hired"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=Kind)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    objects = StageQuerySet.as_manager()

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.name

    @property
    def is_open(self):
        """Whether an application here is still in progress."""
        return self.kind in (self.Kind.ENTRY, self.Kind.IN_PROGRESS)

    @property
    def emails_applicant(self):
        """Whether a recruiter's move here sends an email. It can't be
        recalled, so staff are warned first."""
        return self.kind in (self.Kind.HIRED, self.Kind.REJECTED)

    @property
    def retire_blocker(self):
        """Why this stage can't be retired, or an empty string if it can.

        A stage with any application in it, open or closed, stays. So does
        the last active stage of a kind the app can't run without.
        """
        if self.applications.exists():
            return "Holds applications"
        others = Stage.objects.filter(kind=self.kind, is_active=True)
        if self.kind != self.Kind.IN_PROGRESS and not others.exclude(pk=self.pk):
            return "Required"
        return ""

    def can_retire(self):
        return not self.retire_blocker

    def retire(self):
        """Take the stage out of use. It stays in every timeline."""
        if not self.can_retire():
            raise ValueError(f"{self.name} cannot be retired.")
        self.is_active = False
        self.save(update_fields=["is_active"])

    def restore(self):
        """Put a retired stage back in use."""
        self.is_active = True
        self.save(update_fields=["is_active"])

    def shift(self, offset):
        """Swap places with an active neighbour; a no-op at either end.

        Renumbers every stage, active ones first, so positions stay
        distinct whatever they were before.
        """
        active = list(Stage.objects.filter(is_active=True))
        index = active.index(self)
        target = index + offset
        if not 0 <= target < len(active):
            return
        active[index], active[target] = active[target], active[index]
        stages = [*active, *Stage.objects.filter(is_active=False)]
        for position, stage in enumerate(stages):
            stage.position = position
        with transaction.atomic():
            Stage.objects.bulk_update(stages, ["position"])


# What an applicant sees. Stage names are for staff and never reach them.
PUBLIC_STATUSES = {
    Stage.Kind.ENTRY: "Received",
    Stage.Kind.IN_PROGRESS: "Under review",
    Stage.Kind.HIRED: "Application successful",
    Stage.Kind.REJECTED: "Not moving forward",
    Stage.Kind.WITHDRAWN: "Withdrawn",
}


def resume_path(application, filename):
    """A random name, so a stored file says nothing about its owner."""
    return f"resumes/{uuid.uuid4().hex}.pdf"


class ApplicationQuerySet(models.QuerySet):
    def for_applicant(self, user):
        """``user``'s own applications, newest first."""
        return self.filter(user=user).select_related("job", "stage")

    def visible_to(self, user):
        """What ``user`` may see from the staff side: everything but their
        own. An employee who applies is purely an applicant."""
        return self.exclude(user=user)


class Application(models.Model):
    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="applications")
    # Null once anonymized: the record stays for reporting, without its owner.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    stage = models.ForeignKey(
        Stage, on_delete=models.PROTECT, related_name="applications"
    )
    resume = models.FileField(
        storage=PrivateStorage(), upload_to=resume_path, max_length=255
    )
    cover_letter = models.TextField(max_length=5000, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    objects = ApplicationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "user"], name="careers_one_application_per_job"
            ),
        ]

    def __str__(self):
        return f"Application {self.pk} to {self.job}"

    @property
    def is_open(self):
        return self.stage.is_open

    @property
    def can_reopen(self):
        """Closed, and not anonymized: its résumé and owner must remain."""
        return not self.is_open and self.anonymized_at is None

    @property
    def applicant_name(self):
        """What staff call the applicant, once the record may have no owner."""
        return self.user.display_name if self.user else "Former applicant"

    @property
    def public_status(self):
        """The applicant's label for this application's stage."""
        return PUBLIC_STATUSES[self.stage.kind]

    def timeline(self):
        """Stage moves and notes together, oldest first."""
        entries = [
            *self.stage_changes.select_related("from_stage", "to_stage", "changed_by"),
            *self.notes.select_related("author"),
        ]
        return sorted(entries, key=lambda entry: entry.created_at)

    def add_note(self, author, body, now=None):
        """Add a recruiter's note. Notes are never edited or deleted."""
        return self.notes.create(
            author=author, body=body, created_at=now or timezone.now()
        )

    def can_download_resume(self, user):
        """True for the applicant and for anyone who can recruit."""
        if not self.resume or not user.is_authenticated:
            return False
        return self.user_id == user.pk or user.can_recruit


class StageChange(models.Model):
    """One line of an application's history. Rows are only ever added."""

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="stage_changes"
    )
    # Null on the first row: an application arrives from nowhere.
    from_stage = models.ForeignKey(
        Stage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    to_stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="+")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.application}: {self.to_stage}"


class Note(models.Model):
    """A recruiter's remark. Staff only, and rows are only ever added."""

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="notes"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"Note on {self.application}"
