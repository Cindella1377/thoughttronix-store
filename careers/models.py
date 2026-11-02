from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

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
