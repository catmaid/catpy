from catpy.client import ConnectorRelation

from tests.common import relation_identifier, connectors_types  # noqa


def test_from_id(relation_identifier):  # noqa
    assert relation_identifier.from_id(0) == ConnectorRelation.presynaptic_to


def test_to_id(relation_identifier):  # noqa
    assert relation_identifier.to_id(ConnectorRelation.presynaptic_to) == 0
