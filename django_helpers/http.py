from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_path(request, candidate: str | None, *, default: str = "/") -> str:
    """Keep a user-supplied return URL on the current host."""

    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def htmx_redirect(path: str, *, status: int = 200) -> HttpResponse:
    """Tell HTMX to perform a full browser redirect."""

    return HttpResponse(headers={"HX-Redirect": path}, status=status)
