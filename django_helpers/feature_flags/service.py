from functools import wraps

from django.core.cache import cache
from django.core.exceptions import PermissionDenied

CACHE_KEY = "django_helpers.feature_flags"
CACHE_TIMEOUT = 300


def _all_flags() -> dict[str, dict[str, str | bool]]:
    flags = cache.get(CACHE_KEY)
    if flags is None:
        from .models import FeatureFlag

        flags = {
            flag["name"]: {"is_active": flag["is_active"], "value": flag["value"]}
            for flag in FeatureFlag.objects.values("name", "is_active", "value")
        }
        cache.set(CACHE_KEY, flags, CACHE_TIMEOUT)
    return flags


def is_active(name: str, *, default: bool = False) -> bool:
    flag = _all_flags().get(name)
    return bool(flag["is_active"]) if flag is not None else default


def get_value(name: str, *, default: str = "") -> str:
    flag = _all_flags().get(name)
    return str(flag["value"]) if flag is not None else default


def clear_cache() -> None:
    cache.delete(CACHE_KEY)


def feature_required(name: str):
    """Gate a function view on a global feature flag."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not is_active(name):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
