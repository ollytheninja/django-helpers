from django.urls import include, path

from django_helpers.views import healthz, readyz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("auth/", include("django_helpers.identity.urls")),
]
