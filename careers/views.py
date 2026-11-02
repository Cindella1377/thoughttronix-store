from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import RecruiterRequiredMixin

from .forms import JobForm
from .models import Job


class JobListView(ListView):
    """The public careers page: every Open job."""

    template_name = "careers/jobs.html"
    context_object_name = "jobs"

    def get_queryset(self):
        return Job.objects.listed()


class JobDetailView(DetailView):
    """One job. A Closed job keeps its page; a Draft is a 404."""

    template_name = "careers/job_detail.html"
    context_object_name = "job"

    def get_queryset(self):
        return Job.objects.public()


class ManageJobListView(RecruiterRequiredMixin, ListView):
    """Every job, whatever its status, newest first."""

    model = Job
    template_name = "careers/manage_jobs.html"
    context_object_name = "jobs"
    extra_context = {"section": "careers"}


class ManageJobCreateView(RecruiterRequiredMixin, SuccessMessageMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = "careers/manage_job_form.html"
    success_url = reverse_lazy("careers:manage_jobs")
    success_message = "“%(title)s” created as a draft."
    extra_context = {"section": "careers"}


class ManageJobUpdateView(RecruiterRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = "careers/manage_job_form.html"
    success_url = reverse_lazy("careers:manage_jobs")
    success_message = "“%(title)s” saved."
    extra_context = {"section": "careers"}
