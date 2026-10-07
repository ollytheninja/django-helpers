from django import template

from django_helpers.authz import get_check

register = template.Library()


@register.filter
def can(user, check_name: str) -> bool:
    """Evaluate a registered user-only authorization check."""

    try:
        return bool(get_check(check_name)(user))
    except LookupError:
        return False


@register.simple_tag
def can_object(user, check_name: str, obj) -> bool:
    """Evaluate a registered object authorization check."""

    try:
        return bool(get_check(check_name)(user, obj))
    except LookupError:
        return False
