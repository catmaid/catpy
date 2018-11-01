from catpy.client import ConnectorRelation

try:
    from mock import Mock
except ImportError:
    from unittest.mock import Mock

from tests.common import relation_identifier, connectors_types


def test_from_id(relation_identifier):
    assert relation_identifier.from_id(0) == ConnectorRelation.presynaptic_to


def test_to_id(relation_identifier):
    assert relation_identifier.to_id(ConnectorRelation.presynaptic_to) == 0
