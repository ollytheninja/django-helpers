import pytest
from django.core.exceptions import ValidationError

from django_helpers.organisations.checks import has_organisation_role, is_organisation_member
from django_helpers.organisations.models import Organisation, OrganisationMembership
from tests.testapp.models import CustomUser


@pytest.mark.django_db
def test_membership_and_role_checks():
    user = CustomUser.objects.create_user("member@example.com")
    organisation = Organisation.objects.create(name="Example", slug="example")
    OrganisationMembership.objects.create(
        user=user, organisation=organisation, role="administrator"
    )

    assert is_organisation_member(user, organisation) is True
    assert has_organisation_role(user, organisation, "administrator") is True
    assert has_organisation_role(user, organisation, ["owner", "administrator"]) is True
    assert has_organisation_role(user, organisation, "member") is False


@pytest.mark.django_db
def test_descendant_membership_can_be_included_explicitly():
    user = CustomUser.objects.create_user("member@example.com")
    parent = Organisation.objects.create(name="Parent", slug="parent")
    child = Organisation.objects.create(name="Child", slug="child", parent=parent)
    OrganisationMembership.objects.create(user=user, organisation=child)

    assert is_organisation_member(user, parent) is False
    assert is_organisation_member(user, parent, include_descendants=True) is True


@pytest.mark.django_db
def test_organisation_cannot_be_its_own_ancestor():
    parent = Organisation.objects.create(name="Parent", slug="parent")
    child = Organisation.objects.create(name="Child", slug="child", parent=parent)
    parent.parent = child

    with pytest.raises(ValidationError):
        parent.full_clean()
