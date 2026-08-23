"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path(
        "",
        RedirectView.as_view(url="/dashboard/", permanent=False)
    ),
    path(
        "admin/",
        admin.site.urls
    ),
    path(
        "dashboard/",
        include("dashboard.urls")
    ),
    path(
        "api/",
        include("api.urls")
    ),
]
