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
]
