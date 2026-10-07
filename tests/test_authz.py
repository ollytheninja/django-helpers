from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.views.generic import DetailView

from django_helpers.authz import (
    AuthorizationRequiredMixin,
    all_checks,
    any_check,
    authenticated,
    check_passes,
    get_check,
    is_owner,
    register_check,
)


def test_authenticated_check_fails_closed():
    check = authenticated(lambda user: user.allowed)

    assert check(AnonymousUser()) is False
    assert check(SimpleNamespace(is_authenticated=True, is_active=False, allowed=True)) is False
    assert check(SimpleNamespace(is_authenticated=True, is_active=True, allowed=True)) is True


def test_checks_can_be_composed():
    def yes(_user):
        return True

    def no(_user):
        return False

    assert any_check(no, yes)(object()) is True
    assert all_checks(yes, yes)(object()) is True
    assert all_checks(yes, no)(object()) is False


def test_registered_check_can_be_looked_up():
    @register_check(name="test_registered_check")
    def check(_user):
        return True

    assert get_check("test_registered_check") is check


def test_owner_check_compares_the_configured_attribute():
    user = SimpleNamespace(is_authenticated=True, is_active=True)

    assert is_owner()(user, SimpleNamespace(owner=user)) is True
    assert is_owner(attribute="created_by")(user, SimpleNamespace(created_by=object())) is False


def test_view_decorator_enforces_object_policy(rf):
    owner = SimpleNamespace(is_authenticated=True, is_active=True)
    request = rf.get("/")
    request.user = owner
    resource = SimpleNamespace(owner=owner)

    @check_passes(is_owner(), object_getter=lambda _request, resource_id: resource)
    def view(_request, resource_id):
        return HttpResponse(resource_id)

    assert view(request, "42").content == b"42"
    resource.owner = object()
    with pytest.raises(PermissionDenied):
        view(request, "42")


@pytest.mark.django_db
def test_class_view_loads_object_before_checking_ownership(rf):
    from tests.testapp.models import CustomUser, OwnedThing

    owner = CustomUser.objects.create_user("owner@example.com")
    stranger = CustomUser.objects.create_user("stranger@example.com")
    thing = OwnedThing.objects.create(owner=owner, name="private")

    class OwnedDetail(AuthorizationRequiredMixin, DetailView):
        model = OwnedThing
        authorization_check = is_owner()
        authorization_uses_object = True

        def render_to_response(self, context, **response_kwargs):
            return HttpResponse(context["object"].name)

    request = rf.get("/")
    request.user = owner
    assert OwnedDetail.as_view()(request, pk=thing.pk).content == b"private"

    request.user = stranger
    with pytest.raises(PermissionDenied):
        OwnedDetail.as_view()(request, pk=thing.pk)
