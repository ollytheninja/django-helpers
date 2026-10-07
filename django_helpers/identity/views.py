"""Ready-to-mount passwordless login views."""

import json
import logging
from importlib.util import find_spec

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from django_helpers.http import safe_next_path

from .models import EmailOTPChallenge, PasskeyCredential
from .otp import (
    CHALLENGE_SESSION_KEY,
    AmbiguousEmailError,
    EmailOTPRateLimitError,
    SignupClosedError,
    apply_verified_email_change,
    consume_email_otp,
    issue_email_otp,
    verified_user_for_challenge,
)

logger = logging.getLogger(__name__)
PASSKEY_NEXT_SESSION_KEY = "django_helpers.identity.passkey_next"


def _home():
    return resolve_url(getattr(settings, "LOGIN_REDIRECT_URL", "/"))


def _passkeys_enabled() -> bool:
    return (
        bool(getattr(settings, "DJANGO_HELPERS_AUTHN_PASSKEYS", False))
        and find_spec("webauthn") is not None
    )


def _login_context(request, *, error=""):
    next_path = safe_next_path(
        request, request.POST.get("next") or request.GET.get("next"), default=_home()
    )
    return {"next": next_path, "error": error, "passkey_enabled": _passkeys_enabled()}


@login_not_required
@never_cache
@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def login_view(request):
    """Send an email code or render the passkey sign-in button."""

    context = _login_context(request)
    if request.user.is_authenticated:
        return redirect(context["next"])
    if request.method == "POST":
        try:
            issue_email_otp(request, request.POST.get("email", ""), next_path=context["next"])
        except ValidationError:
            context["error"] = "Enter a valid email address."
        except EmailOTPRateLimitError:
            context["error"] = "Too many codes were requested. Try again later."
        except Exception:
            logger.exception("Could not send email sign-in code")
            context["error"] = "The code could not be sent. Try again later."
        else:
            return redirect("identity:otp_verify")
    else:
        request.session[PASSKEY_NEXT_SESSION_KEY] = context["next"]
    return render(request, "django_helpers/identity/login.html", context)


@login_not_required
@never_cache
@require_http_methods(["GET", "POST"])
def otp_verify_view(request):
    challenge = EmailOTPChallenge.objects.filter(
        pk=request.session.get(CHALLENGE_SESSION_KEY)
    ).first()
    if challenge is None:
        return redirect("identity:login")
    context = {"email": challenge.email, "error": ""}
    if request.method == "GET":
        return render(request, "django_helpers/identity/otp_verify.html", context)
    code = request.POST.get("code", "").strip().replace(" ", "")
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        context["error"] = "Enter the six-digit code from your email."
        return render(request, "django_helpers/identity/otp_verify.html", context)
    challenge = consume_email_otp(request, code)
    if challenge is None:
        context["error"] = "The code is incorrect, expired, or has already been used."
        return render(request, "django_helpers/identity/otp_verify.html", context)
    try:
        if challenge.purpose == EmailOTPChallenge.Purpose.EMAIL_CHANGE:
            apply_verified_email_change(request, challenge)
        else:
            user = verified_user_for_challenge(challenge)
            login(
                request,
                user,
                backend=getattr(
                    settings,
                    "DJANGO_HELPERS_AUTHN_BACKEND",
                    "django.contrib.auth.backends.ModelBackend",
                ),
            )
    except (AmbiguousEmailError, SignupClosedError, ValueError, IntegrityError):
        logger.warning("Verified email could not be bound to an account", exc_info=True)
        context["error"] = "This email cannot be used automatically. Contact support."
        return render(request, "django_helpers/identity/otp_verify.html", context)
    return redirect(safe_next_path(request, challenge.next_path, default=_home()))


@login_not_required
@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect(getattr(settings, "LOGOUT_REDIRECT_URL", None) or reverse("identity:login"))


@login_required(login_url="identity:login")
@require_http_methods(["POST"])
def email_change_view(request):
    try:
        issue_email_otp(
            request,
            request.POST.get("email", ""),
            purpose=EmailOTPChallenge.Purpose.EMAIL_CHANGE,
            user=request.user,
            next_path=reverse("identity:passkeys"),
        )
    except (ValidationError, EmailOTPRateLimitError):
        return render(
            request,
            "django_helpers/identity/passkeys.html",
            {
                "passkeys": request.user.passkeys.all(),
                "error": "Unable to request an email change.",
            },
            status=400,
        )
    return redirect("identity:otp_verify")


@login_not_required
@require_http_methods(["GET"])
def passkey_authentication_options_view(request):
    if not _passkeys_enabled() or request.user.is_authenticated:
        return JsonResponse({"error": "Passkey sign-in is unavailable."}, status=400)
    from .passkeys import authentication_options

    return HttpResponse(authentication_options(request), content_type="application/json")


@login_not_required
@require_http_methods(["POST"])
def passkey_authentication_verify_view(request):
    if not _passkeys_enabled() or request.user.is_authenticated:
        return JsonResponse({"error": "Passkey sign-in is unavailable."}, status=400)
    try:
        from webauthn.helpers.exceptions import InvalidAuthenticationResponse

        from .passkeys import verify_authentication

        stored, _verification = verify_authentication(request, json.loads(request.body))
    except (
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        PasskeyCredential.DoesNotExist,
        InvalidAuthenticationResponse,
    ):
        logger.info("Passkey sign-in failed", exc_info=True)
        return JsonResponse({"error": "This passkey could not be verified."}, status=400)
    login(
        request,
        stored.user,
        backend=getattr(
            settings, "DJANGO_HELPERS_AUTHN_BACKEND", "django.contrib.auth.backends.ModelBackend"
        ),
    )
    next_path = request.session.pop(PASSKEY_NEXT_SESSION_KEY, _home())
    return JsonResponse({"redirect": safe_next_path(request, next_path, default=_home())})


@login_required(login_url="identity:login")
@ensure_csrf_cookie
@require_http_methods(["GET"])
def passkeys_view(request):
    return render(
        request,
        "django_helpers/identity/passkeys.html",
        {"passkeys": request.user.passkeys.all(), "passkey_enabled": _passkeys_enabled()},
    )


@login_required(login_url="identity:login")
@require_http_methods(["POST"])
def passkey_registration_options_view(request):
    if not _passkeys_enabled():
        return JsonResponse({"error": "Passkeys are unavailable."}, status=400)
    from .passkeys import registration_options

    return HttpResponse(
        registration_options(request, request.user), content_type="application/json"
    )


@login_required(login_url="identity:login")
@require_http_methods(["POST"])
def passkey_registration_verify_view(request):
    if not _passkeys_enabled():
        return JsonResponse({"error": "Passkeys are unavailable."}, status=400)
    try:
        from webauthn.helpers.exceptions import InvalidRegistrationResponse

        from .passkeys import verify_registration

        passkey = verify_registration(request, request.user, json.loads(request.body))
    except (
        json.JSONDecodeError,
        IntegrityError,
        KeyError,
        TypeError,
        ValueError,
        InvalidRegistrationResponse,
    ):
        logger.info("Passkey registration failed", exc_info=True)
        return JsonResponse({"error": "The passkey could not be registered."}, status=400)
    return JsonResponse({"id": passkey.pk, "name": passkey.name})


@login_required(login_url="identity:login")
@require_http_methods(["POST"])
def passkey_delete_view(request, passkey_id):
    get_object_or_404(PasskeyCredential, pk=passkey_id, user=request.user).delete()
    return redirect("identity:passkeys")
