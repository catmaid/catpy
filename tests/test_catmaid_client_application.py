try:
    import mock
except ImportError:
    from unittest import mock

import pytest

from catpy.client import CatmaidClient
from catpy.applications.base import CatmaidClientApplication

PROJECT_ID = 10
BASE_URL = "http://not-catmaid.org"


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


def test_get_post_call_fetch(catmaid_mock, ConcreteApp):
    app = ConcreteApp(catmaid_mock)
    rel_url = "potato"

    app.get(rel_url, params=None, raw=False)
    catmaid_mock.fetch.assert_called_with(rel_url, method="GET", data=None, raw=False)

    app.post(rel_url, data=None, raw=False)
    catmaid_mock.fetch.assert_called_with(rel_url, method="POST", data=None, raw=False)


def test_fetch_passthrough(catmaid_mock, ConcreteApp):
    app = ConcreteApp(catmaid_mock)
    args = (1, 2)
    kwargs = {"a": 1}

    app.fetch(*args, **kwargs)
    catmaid_mock.fetch.assert_called_with(*args, **kwargs)


def test_from_json(ConcreteApp):
    cred_path = "cred/path.json"
    with mock.patch.object(CatmaidClient, "from_json") as from_json:
        ConcreteApp.from_json(cred_path)

    from_json.assert_called_with(cred_path)
