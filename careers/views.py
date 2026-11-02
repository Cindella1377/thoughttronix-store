from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from accounts.mixins import RecruiterRequiredMixin

from .forms import JobForm, MoveForm, NoteForm, ReopenForm, ResumeForm, StageForm
from .models import Application, Job, Stage, build_board
from .services import (
    ApplicationError,
    move_application,
    reopen_application,
    submit_application,
    withdraw_application,
)


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


class WithdrawView(LoginRequiredMixin, View):
    """An applicant withdraws, after a page saying what that means."""

    def get_application(self, request, pk):
        return get_object_or_404(Application.objects.for_applicant(request.user), pk=pk)

    def get(self, request, pk):
        return render(
            request,
            "careers/confirm_withdraw.html",
            {
                "application": self.get_application(request, pk),
                "careers_email": settings.CAREERS_EMAIL,
            },
        )

    def post(self, request, pk):
        try:
            withdraw_application(self.get_application(request, pk), request.user)
        except ApplicationError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Your application has been withdrawn.")
        return redirect("careers:applications")


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
            reopen_stages=Stage.objects.reopenable(),
            timeline=self.object.timeline(),
            note_form=NoteForm(),
            **kwargs,
        )


def board_context(job, user, error=None):
    """What the board partial needs, for the page and for a move."""
    return {
        "job": job,
        "board": build_board(job, user),
        "board_url": reverse("careers:board", args=[job.pk]),
        "stages": Stage.objects.movable(),
        "error": error,
    }


class BoardView(RecruiterRequiredMixin, TemplateView):
    """One job's applications as columns of cards."""

    template_name = "careers/board.html"
    extra_context = {"section": "careers"}

    def get_context_data(self, **kwargs):
        job = get_object_or_404(Job, pk=self.kwargs["pk"])
        return super().get_context_data(
            **board_context(job, self.request.user), **kwargs
        )


class MoveApplicationView(RecruiterRequiredMixin, View):
    """Move one application, from the table, the page, or the board.

    A move to Hired or Rejected asks first. A board move sends back the
    whole board, so its card and counts change together; any other move
    returns to where the recruiter came from.
    """

    def post(self, request, pk):
        application = get_object_or_404(
            Application.objects.visible_to(request.user), pk=pk
        )
        form = MoveForm(request.POST)
        is_htmx = "HX-Request" in request.headers
        on_board = is_htmx and "board" in request.POST
        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            next_url = reverse("careers:application", args=[pk])
        error = None
        success = None
        if form.is_valid():
            stage = form.cleaned_data["stage"]
            if stage.emails_applicant and "confirmed" not in request.POST:
                partial = "careers/partials/_confirm_move.html"
                return render(
                    request,
                    partial if is_htmx else "careers/confirm_move.html",
                    {
                        "application": application,
                        "stage": stage,
                        "note": form.cleaned_data["note"],
                        "back": next_url,
                        "on_board": on_board,
                        "section": "careers",
                    },
                )
            try:
                move_application(
                    application,
                    stage,
                    request.user,
                    note=form.cleaned_data["note"],
                )
            except ApplicationError as caught:
                error = str(caught)
            else:
                success = f"Moved to {stage.name}."
        else:
            error = "Choose a stage to move to."
        if on_board:
            response = render(
                request,
                "careers/partials/_board.html",
                board_context(application.job, request.user, error=error),
            )
            response["HX-Retarget"] = "#board"
            response["HX-Reswap"] = "outerHTML"
            return response
        if error:
            messages.error(request, error)
        else:
            messages.success(request, success)
        if is_htmx:
            return HttpResponse(headers={"HX-Redirect": next_url})
        return redirect(next_url)


class ReopenApplicationView(RecruiterRequiredMixin, View):
    """Bring a closed application back, with a written reason."""

    def post(self, request, pk):
        application = get_object_or_404(
            Application.objects.visible_to(request.user), pk=pk
        )
        form = ReopenForm(request.POST)
        if form.is_valid():
            try:
                reopen_application(
                    application,
                    form.cleaned_data["stage"],
                    form.cleaned_data["reason"],
                    request.user,
                )
            except ApplicationError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, "Application reopened.")
        else:
            messages.error(request, "Choose a stage and give a reason for reopening.")
        return redirect("careers:application", pk=pk)


class AddNoteView(RecruiterRequiredMixin, View):
    """Add a note, and send back the refreshed timeline."""

    def post(self, request, pk):
        # An anonymized record takes no notes: they would be new personal data.
        application = get_object_or_404(
            Application.objects.visible_to(request.user),
            pk=pk,
            anonymized_at__isnull=True,
        )
        form = NoteForm(request.POST)
        if form.is_valid():
            application.add_note(request.user, form.cleaned_data["body"])
            form = NoteForm()
        if "HX-Request" not in request.headers:
            if form.errors:
                messages.error(request, "Write a note of 2,000 characters or fewer.")
            return redirect("careers:application", pk=pk)
        return render(
            request,
            "careers/partials/_timeline.html",
            {
                "application": application,
                "timeline": application.timeline(),
                "note_form": form,
            },
        )


class ManageStageListView(RecruiterRequiredMixin, ListView):
    """The shared list of stages, active and retired."""

    template_name = "careers/manage_stages.html"
    context_object_name = "stages"
    extra_context = {"section": "careers"}

    def get_queryset(self):
        return Stage.objects.annotate(application_count=Count("applications"))


class ManageStageCreateView(RecruiterRequiredMixin, SuccessMessageMixin, CreateView):
    model = Stage
    form_class = StageForm
    template_name = "careers/manage_stage_form.html"
    success_url = reverse_lazy("careers:stages")
    success_message = "“%(name)s” added."
    extra_context = {"section": "careers"}


class ManageStageUpdateView(RecruiterRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Stage
    form_class = StageForm
    template_name = "careers/manage_stage_form.html"
    success_url = reverse_lazy("careers:stages")
    success_message = "“%(name)s” saved."
    extra_context = {"section": "careers"}


class StageShiftView(RecruiterRequiredMixin, View):
    """Move a stage one place up or down the list."""

    OFFSETS = {"up": -1, "down": 1}

    def post(self, request, pk):
        stage = get_object_or_404(Stage, pk=pk, is_active=True)
        offset = self.OFFSETS.get(request.POST.get("direction"))
        if offset:
            stage.shift(offset)
        return redirect("careers:stages")


class StageRetireView(RecruiterRequiredMixin, View):
    def post(self, request, pk):
        stage = get_object_or_404(Stage, pk=pk)
        try:
            stage.retire()
        except ValueError:
            messages.error(
                request,
                f"“{stage.name}” can't be retired: {stage.retire_blocker.lower()}.",
            )
        else:
            messages.success(request, f"“{stage.name}” retired.")
        return redirect("careers:stages")


class StageRestoreView(RecruiterRequiredMixin, View):
    def post(self, request, pk):
        stage = get_object_or_404(Stage, pk=pk)
        stage.restore()
        messages.success(request, f"“{stage.name}” restored.")
        return redirect("careers:stages")


class ReportView(RecruiterRequiredMixin, TemplateView):
    """Totals across hiring, with no names, and none of the viewer's own."""

    template_name = "careers/reports.html"
    extra_context = {"section": "careers"}

    def get_context_data(self, **kwargs):
        applications = Application.objects.visible_to(self.request.user)
        return super().get_context_data(
            jobs=applications.by_job(),
            funnel=applications.funnel(),
            outcomes=applications.outcomes(),
            average_days_to_hire=applications.average_days_to_hire(),
            **kwargs,
        )
