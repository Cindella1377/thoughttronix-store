from django.urls import path

from . import views

app_name = "careers"

urlpatterns = [
    path("careers/", views.JobListView.as_view(), name="jobs"),
    path(
        "careers/applications/",
        views.ApplicationListView.as_view(),
        name="applications",
    ),
    path(
        "careers/applications/<int:pk>/withdraw/",
        views.WithdrawView.as_view(),
        name="withdraw",
    ),
    path(
        "careers/applications/<int:pk>/resume/",
        views.ResumeDownloadView.as_view(),
        name="resume",
    ),
    path("careers/<slug:slug>/", views.JobDetailView.as_view(), name="job"),
    path("careers/<slug:slug>/apply/", views.ApplyView.as_view(), name="apply"),
    # Back office — recruiters only, pk URLs per the URL conventions.
    path("backoffice/careers/", views.ManageJobListView.as_view(), name="manage_jobs"),
    path(
        "backoffice/careers/jobs/new/",
        views.ManageJobCreateView.as_view(),
        name="job_create",
    ),
    path(
        "backoffice/careers/jobs/<int:pk>/edit/",
        views.ManageJobUpdateView.as_view(),
        name="job_edit",
    ),
    path(
        "backoffice/careers/jobs/<int:pk>/applications/",
        views.ManageApplicationListView.as_view(),
        name="manage_applications",
    ),
    path(
        "backoffice/careers/applications/<int:pk>/",
        views.ManageApplicationDetailView.as_view(),
        name="application",
    ),
    path(
        "backoffice/careers/applications/<int:pk>/move/",
        views.MoveApplicationView.as_view(),
        name="move",
    ),
    path(
        "backoffice/careers/applications/<int:pk>/reopen/",
        views.ReopenApplicationView.as_view(),
        name="reopen",
    ),
    path(
        "backoffice/careers/applications/<int:pk>/notes/",
        views.AddNoteView.as_view(),
        name="note",
    ),
]
