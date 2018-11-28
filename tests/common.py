try:
    from mock import Mock
except ImportError:
    from unittest.mock import Mock

from catpy.applications.relation_identifier import RelationIdentifier

import pytest


@pytest.fixture
def connectors_types():
    return [
        {
            'name': 'Presynaptic',
            'type': 'Synaptic',
            'relation': 'presynaptic_to',
            'relation_id': 0
        }, {
            'name': 'Postsynaptic',
            'type': 'Synaptic',
            'relation': 'postsynaptic_to',
            'relation_id': 1
        }, {
            'name': 'Abutting',
            'type': 'Abutting',
            'relation': 'abutting',
            'relation_id': 3
        }, {
            'name': 'Gap junction',
            'type': 'Gap junction',
            'relation': 'gapjunction_with',
            'relation_id': 2
        }, {
            'name': 'Attachment',
            'type': 'Attachment',
            'relation': 'attached_to',
            'relation_id': 4
        }, {
            'name': 'Close to',
            'type': 'Spatial',
            'relation': 'close_to',
            'relation_id': 5
        }
    ]


@pytest.fixture
def relation_identifier(connectors_types):
    catmaid = Mock()
    catmaid.project_id = 1
    relid = RelationIdentifier(catmaid)
    relid._fetch_mappings = Mock(return_value=connectors_types)
    return relid
