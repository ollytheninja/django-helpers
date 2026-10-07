import pytest
from django.core.exceptions import FieldDoesNotExist

from tests.testapp.models import CustomUser


@pytest.mark.django_db
def test_email_user_has_no_username_and_normalises_email():
    user = CustomUser.objects.create_user(
        "Person@EXAMPLE.COM", first_name="Ada", last_name="Lovelace"
    )

    assert user.email == "person@example.com"
    with pytest.raises(FieldDoesNotExist):
        CustomUser._meta.get_field("username")
    assert user.display_name == "Ada Lovelace"
    assert str(user) == "Ada Lovelace"


@pytest.mark.django_db
def test_email_user_uses_email_as_display_name_when_name_is_blank():
    user = CustomUser.objects.create_user("person@example.com")

    assert user.display_name == "person@example.com"


@pytest.mark.django_db
def test_superuser_manager_enforces_privilege_flags():
    with pytest.raises(ValueError, match="is_staff"):
        CustomUser.objects.create_superuser("admin@example.com", is_staff=False)


@pytest.mark.django_db
def test_email_user_rejects_blank_addresses():
    with pytest.raises(ValueError, match="email"):
        CustomUser.objects.create_user("   ")
