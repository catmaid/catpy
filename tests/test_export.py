"""These tests dogfood really hard."""
import json
import os

import networkx as nx
from networkx.readwrite import json_graph

import pytest

from catpy.export import ExportWidget, convert_nodelink_data

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

from tests.constants import FIXTURE_ROOT


nx_version = tuple(int(i) for i in nx.__version__.split('.'))


def assert_same_graph(g1, g2):
    d1 = json_graph.node_link_data(g1)
    d2 = json_graph.node_link_data(g2)
    assert d1 == d2


def get_json(version):
    fpath = os.path.join(FIXTURE_ROOT, "nodelink-nx{}.json".format(version))
    with open(fpath) as f:
        return json.load(f)


@pytest.fixture(params=["1-11"])  # , "2-2"])  # only need what CATMAID emits
def nodelink_json(request):
    return get_json(request.param)


@pytest.fixture
def expected_graph():
    version = '1-11' if nx_version < (2, 0) else '2-2'

    fpath = os.path.join(FIXTURE_ROOT, "nodelink-nx{}.json".format(version))
    with open(fpath) as f:
        return json_graph.node_link_graph(json.load(f))


@pytest.fixture
def export_widget():
    catmaid = Mock()
    catmaid.project_id = 1
    return ExportWidget(catmaid)


def test_reads_nodelinks(nodelink_json, export_widget, expected_graph):
    """Check nodelink data is converted for nx2, not nx1"""
    export_widget.get_networkx_dict = Mock(return_value=nodelink_json)
    g = export_widget.get_networkx(10, 20, 30)
    assert_same_graph(g, expected_graph)


def test_converts():
    v1, v2 = [get_json(v) for v in ['1-11', '2-2']]
    assert convert_nodelink_data(v1) == v2


def test_fails_to_convert():
    v2 = get_json("2-2")
    with pytest.raises(RuntimeError):
        convert_nodelink_data(v2)


@pytest.mark.skipif(nx_version < (2, 0), reason="Don't need to run this on networkx 1")
def test_nx2_convert_nowarn(nodelink_json, expected_graph):
    with pytest.warns(None) as record:
        d = convert_nodelink_data(nodelink_json)
    assert len(record) == 0
    assert_same_graph(json_graph.node_link_graph(d), expected_graph)


@pytest.mark.skipif(nx_version >= (2, 0), reason="Don't need to run this on networkx 2+")
def test_nx1_convert_warn(nodelink_json):
    # with pytest.warns(UserWarning):  # this assertion fails even though the warning is raised!
    d = convert_nodelink_data(nodelink_json)

    with pytest.raises(Exception):
        json_graph.node_link_graph(d)


def requirement_to_op_ver(s):
    op = s[:2]
    assert set('<>=').issuperset(op)
    ver = s[2:]
    assert set('0123456789.').issuperset(ver)
    return op, ver


@pytest.mark.skipif(not os.environ.get("CATPY_NX"), reason="No hard networkx version")
def test_correct_nx():
    op, ver = requirement_to_op_ver(os.environ["CATPY_NX"])
    assert eval(nx.__version__ + op + ver)
