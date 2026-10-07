from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from django.views.generic import CreateView, ListView, UpdateView

from .models import OwnerChildMixin, OwnerMixin


@login_not_required
@never_cache
@require_safe
def healthz(_request):
    """Return liveness without depending on the database."""

    return JsonResponse({"status": "ok", "version": getattr(settings, "VERSION", "unknown")})


@login_not_required
@never_cache
@require_safe
def readyz(_request):
    """Report whether the default database can serve requests."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})


def authable_model(model):
    return issubclass(model, OwnerMixin) or issubclass(model, OwnerChildMixin)


class Authzable:
    """Legacy owner-based view support; prefer policy functions from `authz`."""

    model = None

    def __init__(self, *args, **kwargs):
        if not self.model or not authable_model(self.model):
            raise NotImplementedError("The model must inherit OwnerMixin or OwnerChildMixin")
        super().__init__(*args, **kwargs)


class AuthzCreateView(Authzable, LoginRequiredMixin, CreateView):
    template_name = "generic_form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class AuthzUpdateView(Authzable, LoginRequiredMixin, UpdateView):
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if obj.owner != self.request.user:
            raise PermissionDenied
        return obj


class AuthzListView(Authzable, LoginRequiredMixin, ListView):
    def get_queryset(self):
        queryset = super().get_queryset()
        if issubclass(self.model, OwnerMixin):
            return queryset.filter(owner=self.request.user)
        return queryset.filter(**{self.model.owner_path.replace(".", "__"): self.request.user})


class Logout(View):
    def post(self, request):
        logout(request)
        return redirect(reverse("home"))
