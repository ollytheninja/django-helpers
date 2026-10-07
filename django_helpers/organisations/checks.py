from collections.abc import Iterable
from typing import Any

from .models import Organisation


def _memberships(user: Any, organisation: Organisation, *, include_descendants: bool):
    organisations = [organisation]
    if include_descendants:
        pending = [organisation]
        while pending:
            children = list(Organisation.objects.filter(parent__in=pending, is_active=True))
            organisations.extend(children)
            pending = children
    return user.organisation_memberships.filter(
        organisation__in=organisations,
        organisation__is_active=True,
        is_active=True,
    )


def is_organisation_member(
    user: Any,
    organisation: Organisation,
    *,
    include_descendants: bool = False,
) -> bool:
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    return _memberships(user, organisation, include_descendants=include_descendants).exists()


def has_organisation_role(
    user: Any,
    organisation: Organisation,
    roles: str | Iterable[str],
    *,
    include_descendants: bool = False,
) -> bool:
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    roles = [roles] if isinstance(roles, str) else list(roles)
    return (
        _memberships(user, organisation, include_descendants=include_descendants)
        .filter(role__in=roles)
        .exists()
    )
