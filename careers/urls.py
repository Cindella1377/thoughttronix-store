from django.urls import path

from . import views

app_name = "careers"

urlpatterns = [
    path("careers/", views.JobListView.as_view(), name="jobs"),
    path("careers/<slug:slug>/", views.JobDetailView.as_view(), name="job"),
    # Back office — recruiters only, pk URLs per the URL conventions.
    path("manage/careers/", views.ManageJobListView.as_view(), name="manage_jobs"),
    path(
        "manage/careers/jobs/new/",
        views.ManageJobCreateView.as_view(),
        name="job_create",
    ),
    path(
        "manage/careers/jobs/<int:pk>/edit/",
        views.ManageJobUpdateView.as_view(),
        name="job_edit",
    ),
]
