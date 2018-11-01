import pytest

try:
    from unittest import mock
except ImportError:
    import mock

from catpy.client import CatmaidUrl

BASE_URL = "https://not.catmaid.org/"
PROJECT_ID = 1
STACK_GROUP_ID = 1
STACK_ID = 2
SCALE = 3.0
X = 10.0
Y = 20.0
Z = 30.0
TOOL = "tracingtool"
ACTIVE_SKELETON_ID = 100
ACTIVE_NODE_ID = 200


@pytest.fixture
def catmaid_mock():
    return mock.Mock(base_url=BASE_URL, project_id=PROJECT_ID)


@pytest.fixture
def default_kwargs():
    return {
        "base_url": BASE_URL,
        "project_id": PROJECT_ID,
        "stack_group_id": STACK_GROUP_ID,
        "stack_id": STACK_ID,
        "scale": SCALE,
        "x": X,
        "y": Y,
        "z": Z,
        "tool": TOOL,
        "active_skeleton_id": ACTIVE_SKELETON_ID,
        "active_node_id": ACTIVE_NODE_ID,
    }


@pytest.fixture
def default_url(default_kwargs):
    return CatmaidUrl(**default_kwargs)


def test_instantiate(default_url):
    """Test that the object can be instantiated"""
    catmaid_url = CatmaidUrl(
        BASE_URL,
        PROJECT_ID,
        STACK_GROUP_ID,
        STACK_ID,
        SCALE,
        X,
        Y,
        Z,
        TOOL,
        ACTIVE_SKELETON_ID,
        ACTIVE_NODE_ID,
    )
    assert str(catmaid_url) == str(default_url)


def test_str(default_kwargs, default_url):
    """Test that __str__ behaves as expected"""
    expected_response = (
        "{base_url}?pid={project_id}"
        + "&xp={x}&yp={y}&zp={z}"
        + "&tool={tool}&active_node_id={active_node_id}&active_skeleton_id={active_skeleton_id}"
        + "&sg={stack_group_id}&sgs={scale}"
        + "&sid0={stack_id}&s0={scale}"
    ).format(**default_kwargs)
    assert str(default_url) == expected_response


def test_ignores_unfilled_coords(default_kwargs):
    """Test that if any of the 3 coords are missing, all are ignored, and a warning is raised"""
    kwargs = dict(default_kwargs)
    del kwargs["x"]
    with pytest.warns(UserWarning, match="ignoring"):
        url_str = str(CatmaidUrl(**kwargs))
    for dim in "xyz":
        assert dim + "p" not in url_str


def test_add_stacks(default_url):
    """Test that new stacks can be added after instantiation"""
    new_stack_id = 5
    new_stack_scale = -1

    default_url.add_stack(new_stack_id, new_stack_scale)
    assert "sid1={}&s1={}".format(new_stack_id, new_stack_scale) in str(default_url)


def test_add_stacks_fills_scale(default_url):
    """Test that a stack's scale is populated with a default when not explicitly given"""
    new_stack_id = 5

    default_url.add_stack(new_stack_id)
    assert "sid1={}&s1={}".format(new_stack_id, SCALE) in str(default_url)


def test_set_stack_group(default_url):
    """Test that a stack group can be set after instantiation"""
    new_stack_group = 5
    new_stack_group_scale = -1

    default_url.set_stack_group(new_stack_group, new_stack_group_scale)
    assert "sg={}&sgs={}".format(new_stack_group, new_stack_group_scale) in str(
        default_url
    )


def test_set_stack_group_fills_scale(default_kwargs):
    """Test that a stack group's scale is populated with a default when not explicitly given"""
    new_stack_group = 5

    kwargs = dict(default_kwargs)
    del kwargs["stack_group_id"]
    catmaid_url = CatmaidUrl(**default_kwargs)
    catmaid_url.set_stack_group(new_stack_group)

    assert "sg={}&sgs={}".format(new_stack_group, SCALE) in str(catmaid_url)


def test_different_tool_ignores_active(default_kwargs):
    """Test that tool-specific arguments are ignored when using a different tool"""
    kwargs = dict(default_kwargs)
    kwargs["tool"] = "not_tracingtool"

    url_str = str(CatmaidUrl(**kwargs))
    assert "active" not in url_str


def test_from_catmaid(catmaid_mock, default_kwargs, default_url):
    """Test that a CatmaidUrl object instantiated from a CatmaidClient-like object is the same as using args"""
    kwargs = dict(default_kwargs)
    del kwargs["base_url"]
    del kwargs["project_id"]

    catmaid_url = CatmaidUrl.from_catmaid(catmaid_mock, **kwargs)
    assert str(catmaid_url) == str(default_url)


def test_from_url(default_url):
    """Test that a CatmaidUrl object instantiated using from_str is the same as using the args"""
    from_str = CatmaidUrl.from_url(str(default_url))
    assert str(default_url) == str(from_str)
