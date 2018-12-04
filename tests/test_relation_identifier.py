from __future__ import absolute_import

import pytest

from catpy.client import ConnectorRelation, CatmaidClient
from catpy.applications import RelationIdentifier

from tests.common import relation_identifier, connectors_types  # noqa


def test_from_id(relation_identifier):  # noqa
    assert relation_identifier.from_id(0) == ConnectorRelation.presynaptic_to


def test_to_id(relation_identifier):  # noqa
    assert relation_identifier.to_id(ConnectorRelation.presynaptic_to) == 0


@pytest.fixture
def real_relation_identifier(credentials):
    return RelationIdentifier(CatmaidClient(**credentials))


def populate_relid(relation_identifier):
    relation_identifier._get_dict(False, None)
    relation_identifier._get_dict(True, None)


def test_from_id_real(real_relation_identifier):
    populate_relid(real_relation_identifier)
    assert real_relation_identifier.id_to_relation


def test_to_id_real(real_relation_identifier):
    populate_relid(real_relation_identifier)
    assert real_relation_identifier.relation_to_id
