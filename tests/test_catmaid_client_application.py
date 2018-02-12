try:
    import mock
except ImportError:
    from unittest import mock

import pytest

from catpy.client import CatmaidClient, CatmaidClientApplication


PROJECT_ID = 10
BASE_URL = 'http://not-catmaid.org'


@pytest.fixture
def catmaid_mock():
    catmaid = mock.Mock()
    catmaid.project_id = PROJECT_ID
    catmaid.base_url = BASE_URL
    return catmaid


@pytest.fixture
def ConcreteApp():
    class Subclass(CatmaidClientApplication):
        pass

    return Subclass


def test_property_passthrough(catmaid_mock, ConcreteApp):
    app = ConcreteApp(catmaid_mock)
    assert app.project_id == catmaid_mock.project_id == PROJECT_ID
    assert app.base_url == catmaid_mock.base_url == BASE_URL


def test_method_passthrough(catmaid_mock, ConcreteApp):
    app = ConcreteApp(catmaid_mock)
    args = (1, 2)
    kwargs = {'a': 1}

    app.get(*args, **kwargs)
    catmaid_mock.get.assert_called_with(*args, **kwargs)

    app.post(*args, **kwargs)
    catmaid_mock.post.assert_called_with(*args, **kwargs)

    app.fetch(*args, **kwargs)
    catmaid_mock.fetch.assert_called_with(*args, **kwargs)


def test_from_json(ConcreteApp):
    cred_path = 'cred/path.json'
    with mock.patch.object(CatmaidClient, 'from_json') as from_json:
        ConcreteApp.from_json(cred_path)

    from_json.assert_called_with(cred_path)
