from django import forms

from products.forms import StyledModelForm

from .models import Job


class JobForm(StyledModelForm):
    """A job's details, plus its status once it exists.

    A new job is always a Draft, so the status field appears only when
    editing, and offers only the moves ``Job`` allows.
    """

    status = forms.ChoiceField()

    class Meta:
        model = Job
        fields = [
            "title",
            "slug",
            "department",
            "location",
            "employment_type",
            "salary_range",
            "description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        job = self.instance
        if job.pk:
            statuses = [Job.Status(job.status), *job.next_statuses()]
            self.fields["status"].choices = [(s.value, s.label) for s in statuses]
            self.fields["status"].initial = job.status
        else:
            del self.fields["status"]

    def save(self, commit=True):
        if "status" in self.cleaned_data:
            self.instance.change_status(self.cleaned_data["status"])
        return super().save(commit)
