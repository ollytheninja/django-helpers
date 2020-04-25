from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, TemplateView


from .models import OwnerMixin, OwnerChildMixin


def authable_model(model):
    return (issubclass(model, OwnerMixin) or issubclass(model, OwnerChildMixin))


class Authzable:
    model = None

    def __init__(self, *args, **kwargs):
        if self.model and authable_model(self.model):
            super(Authzable, self).__init__(*args, **kwargs)
        else:
            raise NotImplementedError("Can't require access on a model that doesn't subclass OwnerMixin or OwnerChildMixin")


class AuthzCreateView(Authzable, LoginRequiredMixin, CreateView):
    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.owner = self.request.user
        self.object.save()
        return response

    template_name = "generic_form.html"


class AuthzUpdateView(Authzable, LoginRequiredMixin, UpdateView):
    def get_object(self, queryset=None):
        obj = super(AuthzUpdateView, self).get_object(queryset=queryset)
        if obj.owner != self.request.user:
            raise PermissionDenied()


class AuthzListView(Authzable, LoginRequiredMixin, ListView):
    def get_queryset(self):
        queryset = super(AuthzListView, self).get_queryset()

        # if self.request.user.is_staff:
        #     return queryset


        user = self.request.user

        parent_chain = []
        model = self.model
        for i in range(10):
            if issubclass(model, OwnerChildMixin):
                parent_str = self.model.parent
                parent_chain.append(parent_str)

                model = model._meta.get_field(parent_str).related_model
            else:
                break

        kwarg = {"__".join(parent_chain) + "__owner": user}
        queryset = queryset.filter(**kwarg)
        return queryset


class Logout(View):
    def post(self, request):
        logout(request)
        return redirect(reverse("home"))
