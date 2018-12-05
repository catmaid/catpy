import pytest
import networkx as nx

from catpy.util import interpolate_treenodes, get_virtual_treenodes

Z_DEPTH = 10


@pytest.mark.parametrize(
    ("parent_xyz", "child_xyz", "expected"),
    [
        ((0, 0, 0), (10, 10, 20), [(5, 5, 10)]),
        ((10, 10, 20), (0, 0, 0), [(5, 5, 10)]),
        ((0, 0, 0), (1000, 1000, 0), []),
        ((0, 0, 0), (30, 30, 30), [(10, 10, 10), (20, 20, 20)])
    ]
)
def test_interpolate_nodes(parent_xyz, child_xyz, expected):
    locs = list(interpolate_treenodes(parent_xyz, child_xyz, Z_DEPTH))
    assert locs == expected


def nx_to_treenodes(g):
    children = set()
    parents = set()
    for parent, child in g.edges():
        yield [child, parent, None, 0, 0, Z_DEPTH * child]
        children.add(child)
        parents.add(parent)
    root = (parents - children).pop()
    yield [root, None, None, 0, 0, Z_DEPTH * root]


@pytest.fixture
def treenode_response():
    g = nx.DiGraph()
    g.add_path([1, 2, 3, 4, 5, 10])
    g.add_path([4, 11, 12, 13, 14, 15, 20])
    return nx_to_treenodes(g)


def test_get_virtual_treenodes(treenode_response):
    vnodes = dict(get_virtual_treenodes(treenode_response, Z_DEPTH))
    expected = {
        (4, 11): [(0, 0, 50), (0, 0, 60), (0, 0, 70), (0, 0, 80), (0, 0, 90), (0, 0, 100)],
        (5, 10): [(0, 0, 60), (0, 0, 70), (0, 0, 80), (0, 0, 90)],
        (15, 20): [(0, 0, 160), (0, 0, 170), (0, 0, 180), (0, 0, 190)]
    }

    assert vnodes == expected
