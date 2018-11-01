try:
    from mock import Mock
except ImportError:
    from unittest.mock import Mock

import pytest

from catpy.applications.nameresolver import (
    NameResolver,
    MultipleMatchingNamesException,
    NoMatchingNamesException,
)


PROJECT_ID = 1


@pytest.fixture
def stacks_response():
    return [
        {"title": "stack two", "id": 2},
        {"title": "stack five", "id": 5},
        {"title": "stack multi", "id": 10},
        {"title": "stack multi", "id": 11},
    ]


@pytest.fixture
def users_response():
    return [
        {"full_name": "User Three", "login": "user_three", "id": 3},
        {"full_name": "User Four", "login": "user_four", "id": 4},
    ]


@pytest.fixture
def name_resolver(stacks_response, users_response):
    catmaid = Mock()
    catmaid.project_id = PROJECT_ID

    def get_response(url, *args, **kwargs):
        if url == (PROJECT_ID, "stacks"):
            return stacks_response
        elif url == "user-list":
            return users_response
        else:
            return Mock()

    catmaid.fetch = Mock(side_effect=get_response)
    return NameResolver(catmaid)


def test_shortcircuit(name_resolver):
    assert name_resolver.get_stack_id(2) == 2
    name_resolver._catmaid.fetch.assert_not_called()


def test_nomatch(name_resolver):
    with pytest.raises(NoMatchingNamesException):
        name_resolver.get_stack_id("stack one million")


def test_multimatch(name_resolver):
    with pytest.raises(MultipleMatchingNamesException):
        name_resolver.get_stack_id("stack multi")


def test_cache(name_resolver):
    name_resolver.get_stack_id("stack two")
    name_resolver.get_stack_id("stack five")

    name_resolver._catmaid.fetch.assert_called_once()


def test_get_stack_id(name_resolver):
    assert name_resolver.get_stack_id("stack two") == 2


def test_get_user_id_name(name_resolver):
    assert name_resolver.get_user_id("User Three") == 3


def test_get_user_id_login(name_resolver):
    assert name_resolver.get_user_id("user_four") == 4
