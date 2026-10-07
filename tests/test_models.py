import pytest

from tests.testapp.models import ChildThing, CustomUser, OwnedThing


@pytest.mark.django_db
def test_owner_child_resolves_owner_value():
    user = CustomUser.objects.create_user("owner@example.com")
    parent = OwnedThing.objects.create(owner=user, name="parent")
    child = ChildThing.objects.create(parent=parent)

    assert child.owner == user
