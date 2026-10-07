from collections.abc import Callable
from functools import wraps
from typing import Any, Protocol, TypeVar

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpRequest, HttpResponse

User = TypeVar("User")
Object = TypeVar("Object")
View = TypeVar("View", bound=Callable[..., HttpResponse])


class Check(Protocol):
    def __call__(self, user: Any, *args: Any, **kwargs: Any) -> bool: ...


_checks: dict[str, Check] = {}


def register_check(check: Check | None = None, *, name: str | None = None):
    """Register a policy function for reuse, including from templates."""

    def decorator(function: Check) -> Check:
        check_name = name or function.__name__
        if check_name in _checks and _checks[check_name] is not function:
            raise ValueError(f"An authorization check named {check_name!r} is already registered")
        _checks[check_name] = function
        return function

    return decorator(check) if check is not None else decorator


def get_check(name: str) -> Check:
    try:
        return _checks[name]
    except KeyError as error:
        raise LookupError(f"Unknown authorization check: {name}") from error


def authenticated(check: Check) -> Check:
    """Make a policy fail closed for missing, anonymous, or inactive users."""

    @wraps(check)
    def wrapper(user: Any, *args: Any, **kwargs: Any) -> bool:
        if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
            return False
        return bool(check(user, *args, **kwargs))

    return wrapper


def any_check(*checks: Check) -> Check:
    return lambda user, *args, **kwargs: any(check(user, *args, **kwargs) for check in checks)


def all_checks(*checks: Check) -> Check:
    return lambda user, *args, **kwargs: all(check(user, *args, **kwargs) for check in checks)


def has_permission(permission: str) -> Check:
    @authenticated
    def check(user: Any, *_args: Any, **_kwargs: Any) -> bool:
        return bool(user.has_perm(permission))

    return check


def is_owner(*, attribute: str = "owner") -> Check:
    @authenticated
    def check(user: Any, obj: Any) -> bool:
        return getattr(obj, attribute, None) == user

    return check


def check_passes(
    check: Check,
    *,
    object_getter: Callable[..., Any] | None = None,
) -> Callable[[View], View]:
    """Enforce a policy on a function view and raise HTTP 403 when it fails."""

    def decorator(view: View) -> View:
        @wraps(view)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            check_args = ()
            if object_getter is not None:
                check_args = (object_getter(request, *args, **kwargs),)
            if not check(request.user, *check_args):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped  # type: ignore[return-value]

    return decorator


class AuthorizationRequiredMixin:
    """Enforce an `authorization_check` in a class-based view."""

    authorization_check: Check | None = None
    authorization_uses_object = False

    def get_authorization_object(self):
        if self.authorization_uses_object:
            get_object = getattr(self, "get_object", None)
            if not callable(get_object):
                raise ImproperlyConfigured("Object authorization requires get_object()")
            return get_object()
        return None

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        check = type(self).authorization_check
        if check is None:
            raise ImproperlyConfigured("authorization_check must be configured")
        obj = self.get_authorization_object()
        check_args = () if obj is None else (obj,)
        if not check(request.user, *check_args):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
