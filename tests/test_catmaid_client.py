import json

import pytest
import requests

try:
    import mock
except ImportError:
    from unittest import mock

from catpy.client import CatmaidClient, make_url, WrappedCatmaidException


BASE_URL = 'http://not-catmaid.org'
TOKEN = 'abc123'


@pytest.fixture
def credentials_dict():
    return {
        'base_url': BASE_URL,
        'token': TOKEN
    }


@pytest.fixture
def credentials_file(credentials_dict, tmpdir):
    p = tmpdir.join('credentials.json')
    p.write(json.dumps(credentials_dict))
    return str(p)


@pytest.fixture
def valid_response_dict():
    return {'msg': 'This response is OK'}


@pytest.fixture
def error_response_dict():
    return {'traceback': 'a long traceback', 'error': 'an error occurred', 'type': 'a bad one'}


@pytest.fixture
def session_mock():
    session = mock.Mock()
    session.auth = None
    return session


@pytest.fixture
def response_mock():
    response = mock.Mock()
    response.headers = {'content-type': 'application/json'}
    response.status_code = 200

    return response


def test_instantiate_creates_session():
    c = CatmaidClient(BASE_URL)
    assert isinstance(c._session, requests.Session)


def test_can_set_auth():
    c = CatmaidClient(BASE_URL)
    assert c._session.auth is None
    c.set_http_auth('username', 'password')
    assert c._session.auth == ('username', 'password')


def check_correct_token(catmaid_client, token=TOKEN):
    assert catmaid_client._session.headers['X-Authorization'] == 'Token ' + token


def test_can_set_token():
    c = CatmaidClient(BASE_URL)
    assert 'X-Authorization' not in c._session.headers
    c.set_api_token(TOKEN)
    check_correct_token(c)


def test_from_json_pathstr(credentials_file):
    c = CatmaidClient.from_json(credentials_file)
    assert c.base_url == BASE_URL
    check_correct_token(c)


def test_from_json_dict(credentials_dict):
    c = CatmaidClient.from_json(credentials_dict)
    assert c.base_url == BASE_URL
    check_correct_token(c)


class DummyPath(object):
    def __init__(self, s):
        self.s = s

    def __str__(self):
        return str(self.s)


def test_from_json_pathlib(credentials_file):
    """Test that this would work even on a pathlib/pathlib2 Path instead of a str"""
    path = DummyPath(credentials_file)
    c = CatmaidClient.from_json(path)
    assert c.base_url == BASE_URL
    check_correct_token(c)


def test_get_calls_fetch():
    params = {'a': 1}
    with mock.patch.object(CatmaidClient, 'fetch') as fetch:
        c = CatmaidClient(BASE_URL)
        c.get('relative', params=params)

    fetch.assert_called_with('relative', method='GET', data=params, raw=False)


def test_post_calls_fetch():
    data = {'a': 1}
    with mock.patch.object(CatmaidClient, 'fetch') as fetch:
        c = CatmaidClient(BASE_URL)
        c.post('relative', data=data)

    fetch.assert_called_with('relative', method='POST', data=data, raw=False)


def test_fetch_uses_session(response_mock):
    url = make_url(BASE_URL, 'relative')
    with mock.patch.object(requests.Session, 'get', return_value=response_mock) as get:
        c = CatmaidClient(BASE_URL)
        c.fetch('relative', 'GET')

    get.assert_called_with(url, params={})

    with mock.patch.object(requests.Session, 'post', return_value=response_mock) as post:
        c = CatmaidClient(BASE_URL)
        c.fetch('relative', 'POST')

    post.assert_called_with(url, data={})


def test_raises_for_status(response_mock):
    with mock.patch.object(requests.Session, 'get', return_value=response_mock):
        c = CatmaidClient(BASE_URL)
        c.fetch('relative', 'GET')

    response_mock.raise_for_status.assert_called()


def test_raises_on_wrapped_error(response_mock):
    with mock.patch.object(requests.Session, 'get', return_value=response_mock), \
          mock.patch.object(WrappedCatmaidException, 'raise_on_error') as raise_on_error:
        c = CatmaidClient(BASE_URL)
        c.fetch('relative', 'GET')

    raise_on_error.assert_called_with(response_mock)


def test_response_json(response_mock, valid_response_dict):
    response_mock.json.return_value = valid_response_dict
    with mock.patch.object(requests.Session, 'get', return_value=response_mock):
        c = CatmaidClient(BASE_URL)
        ret = c.fetch('relative', 'GET')

    assert ret == valid_response_dict


def test_response_raw_no_deserialise(response_mock):
    response_mock.text = 'text'
    with mock.patch.object(requests.Session, 'get', return_value=response_mock):
        c1 = CatmaidClient(BASE_URL)
        c1.fetch('relative', 'GET', raw=False)
        count_not_raw = response_mock.json.call_count
        response_mock.json.reset_mock()
        ret = c1.fetch('relative', 'GET', raw=True)
        count_raw = response_mock.json.call_count

    assert count_not_raw == count_raw + 1
    assert ret == 'text'
