from django.urls import path

from . import views

app_name = "identity"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("code/verify/", views.otp_verify_view, name="otp_verify"),
    path("logout/", views.logout_view, name="logout"),
    path("email/change/", views.email_change_view, name="email_change"),
    path("passkeys/", views.passkeys_view, name="passkeys"),
    path(
        "passkeys/auth/options/",
        views.passkey_authentication_options_view,
        name="passkey_auth_options",
    ),
    path(
        "passkeys/auth/verify/",
        views.passkey_authentication_verify_view,
        name="passkey_auth_verify",
    ),
    path(
        "passkeys/register/options/",
        views.passkey_registration_options_view,
        name="passkey_register_options",
    ),
    path(
        "passkeys/register/verify/",
        views.passkey_registration_verify_view,
        name="passkey_register_verify",
    ),
    path("passkeys/<int:passkey_id>/delete/", views.passkey_delete_view, name="passkey_delete"),
]
