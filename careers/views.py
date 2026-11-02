from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)

from accounts.mixins import RecruiterRequiredMixin

from .forms import JobForm, MoveForm, ResumeForm
from .models import Application, Job, Stage
from .services import ApplicationError, move_application, submit_application


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["careers_email"] = settings.CAREERS_EMAIL
        user = self.request.user
        if user.is_authenticated:
            application = self.object.applications.filter(user=user).first()
            context["application"] = application
            if self.object.is_open and application is None:
                context["form"] = ResumeForm(job=self.object, user=user)
        return context


class ApplyView(LoginRequiredMixin, FormView):
    """Take an application. A form with errors re-renders the job page."""

    form_class = ResumeForm
    template_name = "careers/job_detail.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.job = get_object_or_404(Job.objects.public(), slug=kwargs["slug"])

    def get(self, request, *args, **kwargs):
        return redirect(self.job)

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "job": self.job,
            "user": self.request.user,
        }

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            job=self.job, careers_email=settings.CAREERS_EMAIL, **kwargs
        )

    def form_valid(self, form):
        try:
            submit_application(
                self.job,
                self.request.user,
                form.cleaned_data["resume"],
                form.cleaned_data["cover_letter"],
            )
        except ApplicationError as error:
            messages.error(self.request, str(error))
            return redirect(self.job)
        messages.success(self.request, f"Application sent for {self.job.title}.")
        return redirect("careers:applications")


class ApplicationListView(LoginRequiredMixin, ListView):
    """An applicant's own applications."""

    template_name = "careers/applications.html"
    context_object_name = "applications"

    def get_queryset(self):
        return Application.objects.for_applicant(self.request.user)

    def get_context_data(self, **kwargs):
        return super().get_context_data(careers_email=settings.CAREERS_EMAIL, **kwargs)


class ResumeDownloadView(View):
    """Send a résumé to the people allowed to read it; a 404 for all others."""

    def get(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        if not application.can_download_resume(request.user):
            raise Http404
        response = FileResponse(
            application.resume.open("rb"),
            as_attachment=True,
            filename=f"resume-{application.pk}.pdf",
            content_type="application/pdf",
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response


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


class ManageApplicationListView(RecruiterRequiredMixin, ListView):
    """One job's applications, optionally narrowed to a stage."""

    template_name = "careers/manage_applications.html"
    context_object_name = "applications"
    extra_context = {"section": "careers"}

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.job = get_object_or_404(Job, pk=kwargs["pk"])
        stage = request.GET.get("stage", "")
        self.current_stage = int(stage) if stage.isdecimal() else None

    def get_queryset(self):
        applications = (
            self.job.applications.visible_to(self.request.user)
            .select_related("user", "stage")
            .order_by("-created_at")
        )
        if self.current_stage:
            applications = applications.filter(stage_id=self.current_stage)
        return applications

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            job=self.job,
            current_stage=self.current_stage,
            # Retired stages stay filterable: closed applications sit in them.
            filter_stages=Stage.objects.all(),
            stages=Stage.objects.movable(),
            **kwargs,
        )


class ManageApplicationDetailView(RecruiterRequiredMixin, DetailView):
    """One application: the résumé link, cover letter, and history."""

    template_name = "careers/manage_application.html"
    context_object_name = "application"
    extra_context = {"section": "careers"}

    def get_queryset(self):
        return Application.objects.visible_to(self.request.user).select_related(
            "job", "stage", "user"
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            stages=Stage.objects.movable(),
            stage_changes=self.object.stage_changes.select_related(
                "from_stage", "to_stage", "changed_by"
            ),
            **kwargs,
        )


class MoveApplicationView(RecruiterRequiredMixin, View):
    """Move one application, then go back where the recruiter came from."""

    def post(self, request, pk):
        application = get_object_or_404(
            Application.objects.visible_to(request.user), pk=pk
        )
        form = MoveForm(request.POST)
        if form.is_valid():
            try:
                move_application(
                    application,
                    form.cleaned_data["stage"],
                    request.user,
                    note=form.cleaned_data["note"],
                )
            except ApplicationError as error:
                messages.error(request, str(error))
            else:
                messages.success(
                    request, f"Moved to {form.cleaned_data['stage'].name}."
                )
        else:
            messages.error(request, "Choose a stage to move to.")
        next_url = request.POST.get("next", "")
        if url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            return redirect(next_url)
        return redirect(reverse("careers:application", args=[pk]))
