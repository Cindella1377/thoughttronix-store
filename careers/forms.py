from django import forms

from products.forms import StyledModelForm

from .models import Application, Job, Stage

# The largest résumé an applicant may upload.
MAX_RESUME_MB = 5
MAX_RESUME_BYTES = MAX_RESUME_MB * 1024 * 1024


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


class ResumeForm(StyledModelForm):
    """The application form. ``submit_application`` does the saving."""

    class Meta:
        model = Application
        fields = ["resume", "cover_letter"]
        help_texts = {"resume": f"A PDF of up to {MAX_RESUME_MB} MB."}

    def __init__(self, *args, job, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        self.user = user
        self.fields["resume"].widget.attrs["accept"] = ".pdf"

    def clean_resume(self):
        resume = self.cleaned_data["resume"]
        if not resume.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Upload your résumé as a PDF.")
        if resume.size > MAX_RESUME_BYTES:
            raise forms.ValidationError(f"Résumés can be at most {MAX_RESUME_MB} MB.")
        # A name proves nothing, so check how the file actually starts.
        header = resume.read(5)
        resume.seek(0)
        if header != b"%PDF-":
            raise forms.ValidationError("This file is not a PDF.")
        return resume

    def clean(self):
        cleaned_data = super().clean()
        if Application.objects.filter(job=self.job, user=self.user).exists():
            raise forms.ValidationError("You've already applied to this job.")
        return cleaned_data


class MoveForm(forms.Form):
    """Where to move an application. ``move_application`` keeps the rules."""

    stage = forms.ModelChoiceField(queryset=Stage.objects.movable())
    note = forms.CharField(required=False)


class ReopenForm(forms.Form):
    """Where a closed application returns to, and why."""

    stage = forms.ModelChoiceField(queryset=Stage.objects.reopenable())
    reason = forms.CharField()
